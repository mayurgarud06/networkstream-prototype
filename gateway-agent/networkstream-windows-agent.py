#!/usr/bin/env python3
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
TEST = "https://www.google.com/generate_204"
PREFIX = "NetworkStream-Client-"
CLIENT_RE = re.compile(r"^192\.168\.137\.(\d{1,3})$")


def run(command):
    return subprocess.run(command, text=True, capture_output=True, check=False)


def admin():
    r = run(["powershell", "-NoProfile", "-Command",
             "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"])
    return r.returncode == 0 and r.stdout.strip().lower() == "true"


def post(url, payload):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode()
        return json.loads(body) if body else None


def get(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode()
        return json.loads(body) if body else None


def online():
    try:
        with urllib.request.urlopen(TEST, timeout=5) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


def upstream_ssid():
    """Return the SSID of the laptop's active infrastructure Wi-Fi connection."""
    result = run(["netsh", "wlan", "show", "interfaces"])
    if result.returncode:
        return None
    for line in result.stdout.splitlines():
        match = re.match(r"\s*SSID\s*:\s*(.*)$", line, re.I)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


def downstream_ssid():
    # Windows Mobile Hotspot uses newer Wi-Fi Direct/WDI plumbing; legacy
    # `show hostednetwork` may not expose it. Keep the explicit configured
    # hosted-network value when available and otherwise use a stable label.
    result = run(["netsh", "wlan", "show", "hostednetwork"])
    if not result.returncode:
        for line in result.stdout.splitlines():
            match = re.search(r"SSID name\s*:\s*(.*)$", line, re.I)
            if match and match.group(1).strip():
                return match.group(1).strip()
    return "Windows Mobile Hotspot"


def scan():
    result = run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Wi-Fi scan failed")
    networks, ssid, current = [], None, None
    auth, enc = "OPEN", None
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"SSID\s+\d+\s*:\s*(.*)$", line, re.I)
        if match:
            ssid = match.group(1).strip() or "<hidden>"
            current, auth, enc = None, "OPEN", None
            continue
        match = re.match(r"Authentication\s*:\s*(.*)$", line, re.I)
        if match:
            auth = match.group(1).strip() or "OPEN"
            continue
        match = re.match(r"Encryption\s*:\s*(.*)$", line, re.I)
        if match:
            enc = match.group(1).strip()
            continue
        match = re.match(r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]+)", line, re.I)
        if match and ssid is not None:
            current = {"ssid": ssid, "bssid": match.group(1).lower(), "signalDbm": None,
                       "signalPercent": None, "frequency": None,
                       "security": auth if not enc or enc.lower() == "none" else f"{auth}/{enc}"}
            networks.append(current)
            continue
        if current is None:
            continue
        match = re.match(r"Signal\s*:\s*(\d+)%", line, re.I)
        if match:
            current["signalPercent"] = int(match.group(1))
        match = re.match(r"Channel\s*:\s*(\d+)", line, re.I)
        if match:
            channel = int(match.group(1))
            current["frequency"] = (f"{2407 + channel * 5} MHz" if 1 <= channel <= 13 else
                                     "2484 MHz" if channel == 14 else
                                     f"{5000 + channel * 5} MHz" if 36 <= channel <= 177 else None)
    return networks


def clients():
    result = run(["arp", "-a"])
    if result.returncode:
        return []
    found = []
    for line in result.stdout.splitlines():
        match = re.search(r"^\s*(192\.168\.137\.\d+)\s+([0-9a-fA-F-]{17})\s+\w+", line)
        if match:
            last = int(match.group(1).rsplit(".", 1)[1])
            if 2 <= last <= 254:
                found.append({"ipAddress": match.group(1),
                              "macAddress": match.group(2).lower().replace("-", ":"),
                              "hostname": None})
    return list({item["ipAddress"]: item for item in found}.values())


def valid_client(ip):
    match = CLIENT_RE.fullmatch(ip or "")
    if not match or not 2 <= int(match.group(1)) <= 254:
        raise ValueError("Only 192.168.137.2-254 clients can be controlled")


def rule_names(ip):
    value = ip.replace(".", "-")
    return f"{PREFIX}{value}-Block", f"{PREFIX}{value}-Portal"


def firewall(ip, allow):
    valid_client(ip)
    block_name, portal_name = rule_names(ip)
    run(["powershell", "-NoProfile", "-Command",
         f"Remove-NetFirewallRule -DisplayName '{block_name}' -ErrorAction SilentlyContinue; "
         f"Remove-NetFirewallRule -DisplayName '{portal_name}' -ErrorAction SilentlyContinue"])
    if allow:
        return
    command = (
        f"New-NetFirewallRule -DisplayName '{block_name}' -Direction Inbound -RemoteAddress {ip} -Action Block -Profile Any; "
        f"New-NetFirewallRule -DisplayName '{portal_name}' -Direction Inbound -RemoteAddress {ip} "
        f"-Protocol TCP -LocalPort 3000,8081 -Action Allow -Profile Any -OverrideBlockRules $true"
    )
    result = run(["powershell", "-NoProfile", "-Command", command])
    if result.returncode:
        error = result.stderr.strip() or result.stdout.strip() or "Firewall update failed"
        if "Access is denied" in error or "System Error 5" in error:
            raise RuntimeError("Windows Firewall access denied. Run PowerShell as Administrator.")
        raise RuntimeError(error)


def nat_sessions(ips):
    if not ips:
        return {}
    result = run(["powershell", "-NoProfile", "-Command",
                  "Get-NetNatSession -ErrorAction Stop | Select-Object InternalSourceAddress,CreationTime | ConvertTo-Json -Compress"])
    if result.returncode or not result.stdout.strip():
        return {}
    try:
        data = json.loads(result.stdout)
    except Exception:
        return {}
    if isinstance(data, dict):
        data = [data]
    grouped = {ip: [] for ip in ips}
    for item in data or []:
        ip = str(item.get("InternalSourceAddress") or "")
        if ip in grouped:
            grouped[ip].append(item)
    return grouped


def register(api, gateway, hotspot=None):
    return post(f"{api}/api/gateways/{gateway}/register", {
        "gatewayId": gateway, "hotspotId": hotspot, "version": VERSION,
        "hostname": socket.gethostname(), "platform": platform.platform()})


def heartbeat(api, gateway):
    return post(f"{api}/api/gateways/{gateway}/heartbeat", {
        "gatewayId": gateway, "version": VERSION, "status": "ONLINE", "hostname": socket.gethostname()})


def report_scan(api, gateway, networks):
    observed_at = datetime.now(timezone.utc).isoformat()
    return post(f"{api}/api/gateways/{gateway}/scan", {
        "gatewayId": gateway, "observedAt": observed_at,
        "hotspots": [{"gatewayId": gateway, "ssid": n["ssid"], "bssid": n["bssid"],
                      "signalDbm": n.get("signalDbm"), "signalPercent": n.get("signalPercent"),
                      "frequency": n.get("frequency"), "security": n.get("security", "OPEN"),
                      "observedAt": observed_at} for n in networks]})


def report_telemetry(api, gateway, connected_clients, internet_up, upstream_name, downstream_name, authorized, sessions):
    clients_out = []
    for client in connected_clients:
        ip = client["ipAddress"]
        active = sessions.get(ip, [])
        allowed = ip in authorized
        state = ("BLOCKED" if not allowed else
                 "UPSTREAM_OFFLINE" if not internet_up else
                 "FLOWING" if active else "ALLOWED_NO_FLOW")
        traffic_times = [x.get("CreationTime") for x in active if x.get("CreationTime")]
        clients_out.append({
            **client,
            "authorized": allowed,
            "internetStatus": state,
            "activeNatSessions": len(active),
            "lastTrafficAt": max(traffic_times, default=None),
        })
    return post(f"{api}/api/gateways/{gateway}/telemetry", {
        "gatewayId": gateway,
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "internetOnline": internet_up,
        "upstreamInterface": "Wi-Fi",
        "upstreamAddress": None,
        "upstreamSsid": upstream_name,
        "downstreamInterface": "Windows Mobile Hotspot",
        "downstreamAddress": "192.168.137.1",
        "downstreamSsid": downstream_name,
        "clients": clients_out,
    })


def commands(api, gateway):
    return get(f"{api}/api/gateways/{gateway}/commands")


def acknowledge(api, gateway, command_id):
    return post(f"{api}/api/gateways/{gateway}/commands/{command_id}/ack", {})


def process_commands(api, gateway, authorized):
    for command in commands(api, gateway) or []:
        try:
            ip = command.get("value")
            if command.get("type") == "ALLOW_CLIENT":
                firewall(ip, True)
                authorized.add(ip)
            elif command.get("type") == "BLOCK_CLIENT":
                firewall(ip, False)
                authorized.discard(ip)
            else:
                raise ValueError(command.get("type"))
            acknowledge(api, gateway, command["id"])
            print("command applied:", command)
        except Exception as error:
            print("command failed:", command, "error:", error)


def local_endpoint(port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/client", "/health"):
                self.send_response(404); self.end_headers(); return
            body = (b'{"status":"OK"}' if self.path == "/health" else
                    json.dumps({"clientIp": self.client_address[0], "gatewayAddress": "192.168.137.1",
                                "frontendPort": 3000}).encode())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8080")
    parser.add_argument("--gateway-id", default=f"WIN-{socket.gethostname()}")
    parser.add_argument("--hotspot-id", default=None)
    parser.add_argument("--no-scan", action="store_true")
    parser.add_argument("--data-plane", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--portal-port", type=int, default=8081)
    args = parser.parse_args()

    if args.data_plane and not admin():
        raise SystemExit("NetworkStream data-plane requires an elevated PowerShell window. Run PowerShell as Administrator.")

    authorized = set()
    managed_clients = set()
    print("NetworkStream Windows Gateway Agent", VERSION)
    print("gateway:", args.gateway_id)
    print("host:", socket.gethostname())
    print("data-plane:", "ENABLED" if args.data_plane else "observation-only")
    endpoint = local_endpoint(args.portal_port)

    try:
        print("register:", register(args.api, args.gateway_id, args.hotspot_id))
        while True:
            try:
                print("heartbeat:", heartbeat(args.api, args.gateway_id))
                internet_up = online()
                print("internet:", "ONLINE" if internet_up else "OFFLINE")
                connected = clients()
                managed_clients.update(c["ipAddress"] for c in connected)
                upstream_name = upstream_ssid()
                downstream_name = downstream_ssid()

                if args.data_plane:
                    process_commands(args.api, args.gateway_id, authorized)
                    for client in connected:
                        firewall(client["ipAddress"], client["ipAddress"] in authorized)

                if not args.no_scan:
                    networks = scan()
                    print(f"nearby Wi-Fi networks: {len(networks)}")
                    print("scan report:", report_scan(args.api, args.gateway_id, networks))

                sessions = nat_sessions([c["ipAddress"] for c in connected])
                print("upstream Wi-Fi:", upstream_name or "not connected")
                print("downstream hotspot:", downstream_name)
                print("downstream clients:", connected)
                print("telemetry:", report_telemetry(args.api, args.gateway_id, connected, internet_up,
                                                        upstream_name, downstream_name, authorized, sessions))
                print("authorized clients:", sorted(authorized))
                print("commands:", json.dumps(commands(args.api, args.gateway_id), indent=2))
            except Exception as error:
                print("gateway communication failed:", error)

            if args.once:
                break
            time.sleep(max(5.0, args.interval))
    except KeyboardInterrupt:
        print("stopping Windows gateway agent")
    finally:
        if args.data_plane:
            for ip in managed_clients:
                try:
                    firewall(ip, True)
                except Exception as error:
                    print("firewall cleanup failed:", ip, error)
        endpoint.shutdown()


if __name__ == "__main__":
    main()
