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
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.8.0-packet-dataplane"
TEST = "https://www.google.com/generate_204"
CLIENT_RE = re.compile(r"^192\.168\.137\.(\d{1,3})$")

try:
    import pydivert
except ImportError:
    pydivert = None


class TrafficState:
    def __init__(self):
        self.lock = threading.RLock()
        self.authorized = set()
        self.clients = {}
        self.forwarded_packets = defaultdict(int)
        self.forwarded_bytes = defaultdict(int)
        self.dropped_packets = defaultdict(int)
        self.dropped_bytes = defaultdict(int)
        self.last_traffic = {}
        self.stop = threading.Event()

    def set_authorized(self, ip, allowed):
        with self.lock:
            if allowed:
                self.authorized.add(ip)
            else:
                self.authorized.discard(ip)

    def is_authorized(self, ip):
        with self.lock:
            return ip in self.authorized

    def snapshot_traffic(self, ip):
        with self.lock:
            return {
                "forwardedPackets": self.forwarded_packets.get(ip, 0),
                "forwardedBytes": self.forwarded_bytes.get(ip, 0),
                "droppedPackets": self.dropped_packets.get(ip, 0),
                "droppedBytes": self.dropped_bytes.get(ip, 0),
                "lastTrafficAt": self.last_traffic.get(ip),
            }

    def record(self, ip, allowed, size):
        now = datetime.now(timezone.utc).isoformat()
        with self.lock:
            if allowed:
                self.forwarded_packets[ip] += 1
                self.forwarded_bytes[ip] += size
            else:
                self.dropped_packets[ip] += 1
                self.dropped_bytes[ip] += size
            self.last_traffic[ip] = now


def run(command):
    return subprocess.run(command, text=True, capture_output=True, check=False)


def admin():
    r = run(["powershell", "-NoProfile", "-Command", "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"])
    return r.returncode == 0 and r.stdout.strip().lower() == "true"


def post(url, payload):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
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
    result = run(["netsh", "wlan", "show", "interfaces"])
    if result.returncode:
        return None
    for line in result.stdout.splitlines():
        match = re.match(r"\s*SSID\s*:\s*(.*)$", line, re.I)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


def downstream_ssid():
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
            current = {"ssid": ssid, "bssid": match.group(1).lower(), "signalDbm": None, "signalPercent": None, "frequency": None, "security": auth if not enc or enc.lower() == "none" else f"{auth}/{enc}"}
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
            current["frequency"] = f"{2407 + channel * 5} MHz" if 1 <= channel <= 13 else "2484 MHz" if channel == 14 else f"{5000 + channel * 5} MHz" if 36 <= channel <= 177 else None
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
                found.append({"ipAddress": match.group(1), "macAddress": match.group(2).lower().replace("-", ":"), "hostname": None})
    return list({item["ipAddress"]: item for item in found}.values())


def valid_client(ip):
    match = CLIENT_RE.fullmatch(ip or "")
    if not match or not 2 <= int(match.group(1)) <= 254:
        raise ValueError("Only 192.168.137.2-254 clients can be controlled")


def cleanup_legacy_firewall_rules():
    result = run(["powershell", "-NoProfile", "-Command", "Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object {$_.DisplayName -like 'NetworkStream-Client-*'} | Remove-NetFirewallRule -ErrorAction SilentlyContinue"])
    if result.returncode and result.stderr.strip():
        print("legacy firewall cleanup warning:", result.stderr.strip())


def start_packet_dataplane(state):
    if pydivert is None:
        raise RuntimeError("PyDivert is required. Run: python -m pip install -r gateway-agent/requirements.txt")

    # NETWORK_FORWARD sees packets that are passing through the laptop rather than
    # sockets owned by the laptop. NetworkStream therefore makes the policy decision
    # at the forwarding point, before Windows forwards the packet to the upstream.
    divert = pydivert.WinDivert("forward and (ip or ipv6)", priority=1000)
    divert.open()

    def loop():
        print("packet dataplane: ONLINE (WinDivert NETWORK_FORWARD)")
        try:
            for packet in divert:
                if state.stop.is_set():
                    break
                src = str(getattr(packet, "src_addr", ""))
                dst = str(getattr(packet, "dst_addr", ""))
                client_ip = src if CLIENT_RE.fullmatch(src) else None
                if client_ip:
                    size = len(packet.raw)
                    allowed = state.is_authorized(client_ip)
                    state.record(client_ip, allowed, size)
                    if not allowed:
                        # Drop: do not reinject. This is the actual access-control
                        # decision and is independent of Windows Firewall rules.
                        continue
                divert.send(packet)
        except Exception as error:
            if not state.stop.is_set():
                print("packet dataplane failed:", error)
        finally:
            try:
                divert.close()
            except Exception:
                pass
            print("packet dataplane: OFFLINE")

    thread = threading.Thread(target=loop, name="networkstream-packet-dataplane", daemon=True)
    thread.start()
    return thread


def register(api, gateway, hotspot=None):
    return post(f"{api}/api/gateways/{gateway}/register", {"gatewayId": gateway, "hotspotId": hotspot, "version": VERSION, "hostname": socket.gethostname(), "platform": platform.platform()})


def heartbeat(api, gateway):
    return post(f"{api}/api/gateways/{gateway}/heartbeat", {"gatewayId": gateway, "version": VERSION, "status": "ONLINE", "hostname": socket.gethostname()})


def report_scan(api, gateway, networks):
    observed_at = datetime.now(timezone.utc).isoformat()
    return post(f"{api}/api/gateways/{gateway}/scan", {"gatewayId": gateway, "observedAt": observed_at, "hotspots": [{"gatewayId": gateway, "ssid": n["ssid"], "bssid": n["bssid"], "signalDbm": n.get("signalDbm"), "signalPercent": n.get("signalPercent"), "frequency": n.get("frequency"), "security": n.get("security", "OPEN"), "observedAt": observed_at} for n in networks]})


def report_telemetry(api, gateway, connected_clients, internet_up, upstream_name, downstream_name, state):
    clients_out = []
    for client in connected_clients:
        ip = client["ipAddress"]
        allowed = state.is_authorized(ip)
        traffic = state.snapshot_traffic(ip)
        if not allowed:
            status = "BLOCKED"
        elif not internet_up:
            status = "UPSTREAM_OFFLINE"
        elif traffic["forwardedPackets"] > 0:
            status = "FLOWING"
        else:
            status = "ALLOWED_NO_FLOW"
        clients_out.append({**client, "authorized": allowed, "internetStatus": status, **traffic})
    return post(f"{api}/api/gateways/{gateway}/telemetry", {"gatewayId": gateway, "observedAt": datetime.now(timezone.utc).isoformat(), "internetOnline": internet_up, "upstreamInterface": "Wi-Fi", "upstreamAddress": None, "upstreamSsid": upstream_name, "downstreamInterface": "Windows Mobile Hotspot", "downstreamAddress": "192.168.137.1", "downstreamSsid": downstream_name, "clients": clients_out})


def commands(api, gateway):
    return get(f"{api}/api/gateways/{gateway}/commands")


def acknowledge(api, gateway, command_id):
    return post(f"{api}/api/gateways/{gateway}/commands/{command_id}/ack", {})


def process_commands(api, gateway, state):
    for command in commands(api, gateway) or []:
        try:
            ip = command.get("value")
            valid_client(ip)
            if command.get("type") == "ALLOW_CLIENT":
                state.set_authorized(ip, True)
            elif command.get("type") == "BLOCK_CLIENT":
                state.set_authorized(ip, False)
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
            body = b'{"status":"OK"}' if self.path == "/health" else json.dumps({"clientIp": self.client_address[0], "gatewayAddress": "192.168.137.1", "frontendPort": 3000}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
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
    if args.data_plane:
        cleanup_legacy_firewall_rules()
    state = TrafficState()
    packet_thread = None
    print("NetworkStream Windows Gateway Agent", VERSION)
    print("gateway:", args.gateway_id)
    print("host:", socket.gethostname())
    print("data-plane:", "ENABLED" if args.data_plane else "observation-only")
    endpoint = local_endpoint(args.portal_port)
    try:
        print("register:", register(args.api, args.gateway_id, args.hotspot_id))
        if args.data_plane:
            packet_thread = start_packet_dataplane(state)
        while True:
            try:
                print("heartbeat:", heartbeat(args.api, args.gateway_id)); internet_up = online(); print("internet:", "ONLINE" if internet_up else "OFFLINE")
                connected = clients(); upstream_name = upstream_ssid(); downstream_name = downstream_ssid()
                if args.data_plane:
                    # New clients are denied by default because authorized starts empty.
                    # An explicit ALLOW_CLIENT command is required before forwarding.
                    process_commands(args.api, args.gateway_id, state)
                if not args.no_scan:
                    networks = scan(); print(f"nearby Wi-Fi networks: {len(networks)}"); print("scan report:", report_scan(args.api, args.gateway_id, networks))
                print("upstream Wi-Fi:", upstream_name or "not connected"); print("downstream hotspot:", downstream_name); print("downstream clients:", connected)
                print("telemetry:", report_telemetry(args.api, args.gateway_id, connected, internet_up, upstream_name, downstream_name, state)); print("authorized clients:", sorted(state.authorized)); print("commands:", json.dumps(commands(args.api, args.gateway_id), indent=2))
            except Exception as error:
                print("gateway communication failed:", error)
            if args.once: break
            time.sleep(max(5.0, args.interval))
    except KeyboardInterrupt:
        print("stopping Windows gateway agent")
    finally:
        state.stop.set()
        if packet_thread and packet_thread.is_alive():
            packet_thread.join(timeout=2)
        endpoint.shutdown()


if __name__ == "__main__":
    main()
