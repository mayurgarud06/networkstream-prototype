#!/usr/bin/env python3
"""NetworkStream Windows gateway agent.

Safe by default: observes Wi-Fi and downstream clients. With --data-plane,
new Windows Mobile Hotspot clients are blocked until NetworkStream authorizes
them. Telemetry separates policy from observed Internet flow.
"""
import argparse
import json
import platform
import re
import socket
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.7.0-windows-agent"
INTERNET_TEST_URL = "https://www.google.com/generate_204"
FIREWALL_PREFIX = "NetworkStream-Client-"
DOWNSTREAM_RE = re.compile(r"^192\.168\.137\.(\d{1,3})$")

def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True, check=False)

def is_admin():
    result = run(["powershell", "-NoProfile", "-Command", "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"])
    return result.returncode == 0 and result.stdout.strip().lower() == "true"

def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else None

def get_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else None

def internet_reachable():
    try:
        with urllib.request.urlopen(INTERNET_TEST_URL, timeout=5) as response:
            return 200 <= response.status < 400
    except Exception:
        return False

def channel_to_frequency(channel):
    try: channel = int(channel)
    except (TypeError, ValueError): return None
    if 1 <= channel <= 13: return f"{2407 + channel * 5} MHz"
    if channel == 14: return "2484 MHz"
    if 36 <= channel <= 177: return f"{5000 + channel * 5} MHz"
    return None

def scan_wifi():
    result = run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    if result.returncode != 0: raise RuntimeError(result.stderr.strip() or "netsh Wi-Fi scan failed")
    networks, current_ssid, current, auth, encryption = [], None, None, "OPEN", None
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line: continue
        match = re.match(r"SSID\s+\d+\s*:\s*(.*)$", line, re.I)
        if match:
            current_ssid, current, auth, encryption = match.group(1).strip() or "<hidden>", None, "OPEN", None; continue
        match = re.match(r"Authentication\s*:\s*(.*)$", line, re.I)
        if match: auth = match.group(1).strip() or "OPEN"; continue
        match = re.match(r"Encryption\s*:\s*(.*)$", line, re.I)
        if match: encryption = match.group(1).strip(); continue
        match = re.match(r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]+)", line, re.I)
        if match and current_ssid is not None:
            security = auth if not encryption or encryption.lower() == "none" else f"{auth}/{encryption}"
            current = {"ssid": current_ssid, "bssid": match.group(1).lower(), "signalDbm": None, "signalPercent": None, "frequency": None, "security": security}
            networks.append(current); continue
        if current is None: continue
        match = re.match(r"Signal\s*:\s*(\d+)%", line, re.I)
        if match: current["signalPercent"] = int(match.group(1))
        match = re.match(r"Channel\s*:\s*(\d+)", line, re.I)
        if match: current["frequency"] = channel_to_frequency(match.group(1)); current["channel"] = int(match.group(1))
    return networks

def discover_clients():
    result = run(["arp", "-a"])
    if result.returncode != 0: return []
    clients = []
    for line in result.stdout.splitlines():
        match = re.search(r"^\s*(192\.168\.137\.\d+)\s+([0-9a-fA-F-]{17})\s+\w+", line)
        if not match: continue
        ip = match.group(1); last = int(ip.rsplit(".", 1)[1])
        if 2 <= last <= 254: clients.append({"ipAddress": ip, "macAddress": match.group(2).lower().replace("-", ":"), "hostname": None})
    return list({c["ipAddress"]: c for c in clients}.values())

def validate_client_ip(ip):
    match = DOWNSTREAM_RE.fullmatch(ip or "")
    if not match or not 2 <= int(match.group(1)) <= 254: raise ValueError("Only Windows Mobile Hotspot clients in 192.168.137.0/24 can be controlled")

def firewall_rule_names(ip):
    safe = ip.replace(".", "-"); return f"{FIREWALL_PREFIX}{safe}-Block", f"{FIREWALL_PREFIX}{safe}-Portal"

def apply_firewall(ip, allow):
    validate_client_ip(ip)
    block_name, portal_name = firewall_rule_names(ip)
    cleanup = f"Remove-NetFirewallRule -DisplayName '{block_name}' -ErrorAction SilentlyContinue; Remove-NetFirewallRule -DisplayName '{portal_name}' -ErrorAction SilentlyContinue"
    run(["powershell", "-NoProfile", "-Command", cleanup])
    if allow: return
    command = (f"New-NetFirewallRule -DisplayName '{block_name}' -Direction Inbound -RemoteAddress {ip} -Action Block -Profile Any; "
               f"New-NetFirewallRule -DisplayName '{portal_name}' -Direction Inbound -RemoteAddress {ip} -Protocol TCP -LocalPort 3000,8081 -Action Allow -Profile Any -OverrideBlockRules $true")
    result = run(["powershell", "-NoProfile", "-Command", command])
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip() or "Windows Firewall update failed"
        if "Access is denied" in error or "System Error 5" in error: raise RuntimeError("Windows Firewall access denied. Restart PowerShell as Administrator and run the gateway agent again.")
        raise RuntimeError(error)

def downstream_ssid():
    result = run(["netsh", "wlan", "show", "hostednetwork"])
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            match = re.search(r"SSID name\s*:\s*(.*)$", line, re.I)
            if match and match.group(1).strip(): return match.group(1).strip()
    return "Windows Mobile Hotspot"

def nat_sessions_for_clients(client_ips):
    if not client_ips: return {}
    result = run(["powershell", "-NoProfile", "-Command", "Get-NetNatSession -ErrorAction Stop | Select-Object InternalSourceAddress,CreationTime | ConvertTo-Json -Compress"])
    if result.returncode != 0 or not result.stdout.strip(): return {}
    try: data = json.loads(result.stdout)
    except json.JSONDecodeError: return {}
    if isinstance(data, dict): data = [data]
    grouped = {ip: [] for ip in client_ips}
    for item in data or []:
        ip = str(item.get("InternalSourceAddress") or "")
        if ip in grouped: grouped[ip].append(item)
    return grouped

def client_internet_state(authorized, upstream_online, nat_sessions):
    if not authorized: return "BLOCKED"
    if not upstream_online: return "UPSTREAM_OFFLINE"
    return "FLOWING" if nat_sessions > 0 else "ALLOWED_NO_FLOW"

def register(api, gateway_id, hotspot_id=None): return post_json(f"{api}/api/gateways/{gateway_id}/register", {"gatewayId": gateway_id, "hotspotId": hotspot_id or None, "version": VERSION, "hostname": socket.gethostname(), "platform": platform.platform()})
def heartbeat(api, gateway_id): return post_json(f"{api}/api/gateways/{gateway_id}/heartbeat", {"gatewayId": gateway_id, "version": VERSION, "status": "ONLINE", "hostname": socket.gethostname()})
def report_scan(api, gateway_id, networks):
    observed = datetime.now(timezone.utc).isoformat()
    payload = {"gatewayId": gateway_id, "observedAt": observed, "hotspots": [{"gatewayId": gateway_id, "ssid": n["ssid"], "bssid": n["bssid"], "signalDbm": n.get("signalDbm"), "signalPercent": n.get("signalPercent"), "frequency": n.get("frequency"), "security": n.get("security", "OPEN"), "observedAt": observed} for n in networks]}
    return post_json(f"{api}/api/gateways/{gateway_id}/scan", payload)
def report_telemetry(api, gateway_id, clients, internet_online, downstream_name, authorized_ips, nat_sessions):
    observed = datetime.now(timezone.utc); enriched = []
    for client in clients:
        ip = client["ipAddress"]; sessions = nat_sessions.get(ip, []); authorized = ip in authorized_ips
        enriched.append({**client, "ssid": downstream_name, "authorized": authorized, "internetStatus": client_internet_state(authorized, internet_online, len(sessions)), "activeNatSessions": len(sessions), "lastTrafficAt": max((s.get("CreationTime") for s in sessions if s.get("CreationTime")), default=None)})
    payload = {"gatewayId": gateway_id, "observedAt": observed.isoformat(), "internetOnline": internet_online, "upstreamInterface": "Wi-Fi", "upstreamAddress": None, "downstreamInterface": "Windows Mobile Hotspot", "downstreamAddress": "192.168.137.1", "downstreamSsid": downstream_name, "clients": enriched}
    return post_json(f"{api}/api/gateways/{gateway_id}/telemetry", payload)
def get_policy(api, gateway_id): return get_json(f"{api}/api/gateways/{gateway_id}/policy")
def get_commands(api, gateway_id): return get_json(f"{api}/api/gateways/{gateway_id}/commands")
def ack_command(api, gateway_id, command_id): return post_json(f"{api}/api/gateways/{gateway_id}/commands/{command_id}/ack", {})

def process_commands(api, gateway_id, authorized_ips):
    for command in get_commands(api, gateway_id) or []:
        try:
            ip = command.get("value")
            if command.get("type") == "ALLOW_CLIENT": apply_firewall(ip, True); authorized_ips.add(ip)
            elif command.get("type") == "BLOCK_CLIENT": apply_firewall(ip, False); authorized_ips.discard(ip)
            else: raise ValueError(f"Unsupported command: {command.get('type')}")
            ack_command(api, gateway_id, command["id"]); print("command applied:", command)
        except Exception as error: print("command failed:", command, "error:", error)

def start_client_endpoint(port):
    class ClientHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/client", "/health"): self.send_response(404); self.end_headers(); return
            body = b'{"status":"OK"}' if self.path == "/health" else json.dumps({"clientIp": self.client_address[0], "gatewayAddress": "192.168.137.1", "frontendPort": 3000}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, format, *args): return
    server = ThreadingHTTPServer(("0.0.0.0", port), ClientHandler); threading.Thread(target=server.serve_forever, daemon=True).start(); return server

def cleanup_firewall(managed_ips):
    for ip in sorted(managed_ips):
        try: apply_firewall(ip, True)
        except Exception as error: print("firewall cleanup failed:", ip, error)

def main():
    parser = argparse.ArgumentParser(description="NetworkStream Windows gateway agent")
    parser.add_argument("--api", default="http://127.0.0.1:8080"); parser.add_argument("--gateway-id", default=f"WIN-{socket.gethostname()}"); parser.add_argument("--hotspot-id", default=None); parser.add_argument("--no-scan", action="store_true"); parser.add_argument("--data-plane", action="store_true"); parser.add_argument("--once", action="store_true"); parser.add_argument("--interval", type=float, default=15.0, help="gateway control loop interval in seconds"); parser.add_argument("--portal-port", type=int, default=8081)
    args = parser.parse_args()
    if args.data_plane and not is_admin(): raise SystemExit("NetworkStream data-plane requires an elevated PowerShell window. Right-click PowerShell -> Run as administrator, then start the agent again.")
    scan_enabled = not args.no_scan; authorized_ips, managed_ips = set(), set()
    print("NetworkStream Windows Gateway Agent", VERSION); print("gateway:", args.gateway_id); print("host:", socket.gethostname()); print("data-plane:", "ENABLED" if args.data_plane else "observation-only")
    if args.data_plane: print("local frontend: http://192.168.137.1:3000"); print("client identity: http://192.168.137.1:%d/client" % args.portal_port)
    portal = start_client_endpoint(args.portal_port)
    try:
        print("register:", register(args.api, args.gateway_id, args.hotspot_id))
        while True:
            try:
                print("heartbeat:", heartbeat(args.api, args.gateway_id)); online = internet_reachable(); print("internet:", "ONLINE" if online else "OFFLINE")
                clients = discover_clients(); managed_ips.update(c["ipAddress"] for c in clients); downstream_name = downstream_ssid()
                if args.data_plane:
                    process_commands(args.api, args.gateway_id, authorized_ips)
                    for client in clients: apply_firewall(client["ipAddress"], client["ipAddress"] in authorized_ips)
                if scan_enabled:
                    networks = scan_wifi(); print(f"nearby Wi-Fi networks: {len(networks)}"); print("scan report:", report_scan(args.api, args.gateway_id, networks))
                nat_sessions = nat_sessions_for_clients([c["ipAddress"] for c in clients]); print("downstream clients:", clients); print("telemetry:", report_telemetry(args.api, args.gateway_id, clients, online, downstream_name, authorized_ips, nat_sessions)); print("authorized clients:", sorted(authorized_ips)); print("policy:", json.dumps(get_policy(args.api, args.gateway_id), indent=2)); print("commands:", json.dumps(get_commands(args.api, args.gateway_id), indent=2))
            except Exception as error: print("gateway communication failed:", error)
            if args.once: break
            time.sleep(max(5.0, args.interval))
    except KeyboardInterrupt: print("stopping Windows gateway agent")
    finally:
        if args.data_plane: cleanup_firewall(managed_ips)
        portal.shutdown()
    return 0

if __name__ == "__main__": raise SystemExit(main())