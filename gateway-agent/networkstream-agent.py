#!/usr/bin/env python3

import argparse
import json
import platform
import re
import socket
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

VERSION = "0.4.0-linux-agent"


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def post_json(url, payload):
    data = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode()
        return json.loads(body) if body else None


def get_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode()
        return json.loads(body) if body else None


def discover_interfaces():
    result = run(["ip", "-j", "addr"])
    try:
        return json.loads(result.stdout) if result.returncode == 0 else []
    except json.JSONDecodeError:
        return []


def discover_routes():
    result = run(["ip", "-j", "route"])
    try:
        return json.loads(result.stdout) if result.returncode == 0 else []
    except json.JSONDecodeError:
        return []


def discover_network():
    return {"interfaces": discover_interfaces(), "routes": discover_routes()}


def split_nmcli(line):
    fields, current, escaped = [], [], False
    for char in line.rstrip("\n"):
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def scan_wifi():
    """Scan nearby Wi-Fi without associating with any network."""
    result = run([
        "nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,FREQ,SECURITY",
        "device", "wifi", "list", "--rescan", "yes"
    ])
    if result.returncode != 0:
        # Fallback for Linux hosts without NetworkManager.
        return scan_wifi_iw()

    networks = []
    for line in result.stdout.splitlines():
        fields = split_nmcli(line)
        if len(fields) < 5 or not fields[1]:
            continue
        try:
            signal = int(fields[2]) if fields[2] else None
        except ValueError:
            signal = None
        networks.append({
            "ssid": fields[0] or "<hidden>",
            "bssid": fields[1],
            "signalDbm": signal,
            "frequency": fields[3] or None,
            "security": fields[4] or "OPEN"
        })
    return networks


def scan_wifi_iw():
    result = run(["iw", "dev"])
    if result.returncode != 0:
        return []
    interfaces = re.findall(r"Interface (\S+)", result.stdout)
    for iface in interfaces:
        scan = run(["iw", "dev", iface, "scan"])
        if scan.returncode != 0:
            continue
        networks = []
        current = None
        for line in scan.stdout.splitlines():
            line = line.strip()
            if line.startswith("BSS "):
                if current:
                    networks.append(current)
                current = {"bssid": line.split()[1].split("(")[0], "ssid": "<hidden>",
                           "signalDbm": None, "frequency": None, "security": "OPEN"}
            elif current and line.startswith("freq:"):
                current["frequency"] = line.split(":", 1)[1].strip()
            elif current and line.startswith("signal:"):
                try:
                    current["signalDbm"] = int(float(line.split(":", 1)[1].split()[0]))
                except ValueError:
                    pass
            elif current and line.startswith("SSID:"):
                current["ssid"] = line.split(":", 1)[1].strip() or "<hidden>"
            elif current and ("WPA" in line or "RSN:" in line):
                current["security"] = "WPA"
        if current:
            networks.append(current)
        return networks
    return []


def register(api, gateway_id, hotspot_id):
    return post_json(f"{api}/api/gateways/{gateway_id}/register", {
        "gatewayId": gateway_id, "hotspotId": hotspot_id, "version": VERSION,
        "hostname": socket.gethostname(), "platform": platform.platform()
    })


def heartbeat(api, gateway_id):
    return post_json(f"{api}/api/gateways/{gateway_id}/heartbeat", {
        "gatewayId": gateway_id, "version": VERSION, "status": "ONLINE",
        "hostname": socket.gethostname()
    })


def report_scan(api, gateway_id, networks):
    return post_json(f"{api}/api/gateways/{gateway_id}/scan", {
        "gatewayId": gateway_id,
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "hotspots": networks
    })


def get_policy(api, gateway_id):
    return get_json(f"{api}/api/gateways/{gateway_id}/policy")


def get_commands(api, gateway_id):
    return get_json(f"{api}/api/gateways/{gateway_id}/commands")


def print_network():
    print(json.dumps(discover_network(), indent=2))


def apply_lab_gateway(uplink, downlink, cidr, rate):
    """Enable a deliberately explicit isolated-LAB NAT dataplane."""
    if not uplink or not downlink or uplink == downlink:
        raise ValueError("--apply requires two different --uplink-iface and --downlink-iface values")
    if not cidr:
        raise ValueError("--apply requires --lab-cidr")

    subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], check=True)
    nft = [
        "add", "table", "ip", "networkstream", ";",
        "add", "chain", "ip", "networkstream", "forward", "{", "type", "filter", "hook", "forward", "priority", "0", ";", "policy", "drop", ";", "}", ";",
        "add", "chain", "ip", "networkstream", "postrouting", "{", "type", "nat", "hook", "postrouting", "priority", "100", ";", "}", ";",
        "add", "rule", "ip", "networkstream", "forward", "iifname", downlink, "oifname", uplink, "accept", ";",
        "add", "rule", "ip", "networkstream", "forward", "iifname", uplink, "oifname", downlink, "ct", "state", "established,related", "accept", ";",
        "add", "rule", "ip", "networkstream", "postrouting", "oifname", uplink, "ip", "saddr", cidr, "masquerade", ";"
    ]
    subprocess.run(["nft", "-f", "-"] , input=" ".join(nft), text=True, check=True)
    subprocess.run(["tc", "qdisc", "replace", "dev", downlink, "root", "tbf", "rate", rate,
                    "burst", "64kbit", "latency", "50ms"], check=True)
    print(f"LAB dataplane applied: {downlink} -> {uplink}, NAT {cidr}, aggregate rate {rate}")


def main():
    parser = argparse.ArgumentParser(description="NetworkStream Linux software gateway")
    parser.add_argument("--api", default="http://127.0.0.1:8080")
    parser.add_argument("--gateway-id", default=socket.gethostname())
    parser.add_argument("--hotspot-id", default="HS-A")
    parser.add_argument("--dry-run", action="store_true", help="inspect only; never changes routing/firewall")
    parser.add_argument("--apply", action="store_true", help="enable dataplane; requires --lab-mode")
    parser.add_argument("--lab-mode", action="store_true", help="explicit acknowledgement for isolated lab networking")
    parser.add_argument("--uplink-iface")
    parser.add_argument("--downlink-iface")
    parser.add_argument("--lab-cidr", default="10.77.0.0/24")
    parser.add_argument("--rate", default="20mbit")
    parser.add_argument("--scan", action="store_true", help="scan nearby Wi-Fi and report observations")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.apply and (not args.lab_mode or args.dry_run):
        parser.error("--apply requires --lab-mode and cannot be combined with --dry-run")

    print("NetworkStream Linux Gateway Agent", VERSION)
    print("gateway:", args.gateway_id)
    if args.dry_run:
        print("DRY RUN: no routing/firewall changes will be made")
        print_network()
    if args.apply:
        apply_lab_gateway(args.uplink_iface, args.downlink_iface, args.lab_cidr, args.rate)

    try:
        print("register:", register(args.api, args.gateway_id, args.hotspot_id))
    except Exception as error:
        print("registration failed:", error)

    while True:
        try:
            print("heartbeat:", heartbeat(args.api, args.gateway_id))
            if args.scan or args.dry_run:
                networks = scan_wifi()
                print(f"nearby Wi-Fi networks: {len(networks)}")
                for network in networks:
                    print("  ", network)
                if networks:
                    print("scan report:", report_scan(args.api, args.gateway_id, networks))
            print("policy:", json.dumps(get_policy(args.api, args.gateway_id), indent=2))
            print("commands:", json.dumps(get_commands(args.api, args.gateway_id), indent=2))
        except Exception as error:
            print("gateway communication failed:", error)
        if args.once:
            break
        time.sleep(10)


if __name__ == "__main__":
    main()
