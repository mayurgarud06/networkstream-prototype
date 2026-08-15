#!/usr/bin/env python3
"""NetworkStream Windows gateway/observation agent.

This agent is intentionally limited to Windows Wi-Fi discovery plus the
NetworkStream gateway control-plane protocol. It does not change Windows
routing, firewall, Internet Connection Sharing, or adapter configuration.
Use the Linux agent for the isolated-lab forwarding/NAT dataplane.
"""

import argparse
import json
import platform
import re
import socket
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

VERSION = "0.5.0-windows-agent"


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else None


def get_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else None


def channel_to_frequency(channel):
    try:
        channel = int(channel)
    except (TypeError, ValueError):
        return None
    if 1 <= channel <= 13:
        return f"{2407 + channel * 5} MHz"
    if channel == 14:
        return "2484 MHz"
    if 36 <= channel <= 177:
        return f"{5000 + channel * 5} MHz"
    return None


def scan_wifi():
    """Discover nearby Wi-Fi using the Windows WLAN API exposed by netsh.

    This only observes networks. It does not connect to or modify them.
    """
    result = run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "netsh Wi-Fi scan failed")

    networks = []
    current_ssid = None
    current = None
    current_auth = "OPEN"
    current_encryption = None

    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue

        match = re.match(r"SSID\s+\d+\s*:\s*(.*)$", line, re.IGNORECASE)
        if match:
            current_ssid = match.group(1).strip() or "<hidden>"
            current = None
            current_auth = "OPEN"
            current_encryption = None
            continue

        match = re.match(r"Authentication\s*:\s*(.*)$", line, re.IGNORECASE)
        if match:
            current_auth = match.group(1).strip() or "OPEN"
            if current is not None:
                current["security"] = current_auth
            continue

        match = re.match(r"Encryption\s*:\s*(.*)$", line, re.IGNORECASE)
        if match:
            current_encryption = match.group(1).strip()
            if current is not None and current_encryption.lower() != "none":
                current["security"] = f"{current_auth}/{current_encryption}"
            continue

        match = re.match(r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]+)", line, re.IGNORECASE)
        if match and current_ssid is not None:
            security = current_auth
            if current_encryption and current_encryption.lower() != "none":
                security = f"{current_auth}/{current_encryption}"
            current = {
                "ssid": current_ssid,
                "bssid": match.group(1).lower(),
                "signalDbm": None,
                "signalPercent": None,
                "frequency": None,
                "security": security,
            }
            networks.append(current)
            continue

        if current is None:
            continue

        match = re.match(r"Signal\s*:\s*(\d+)%", line, re.IGNORECASE)
        if match:
            # netsh reports percentage, not dBm. Keep the value explicit as
            # a percentage so the backend never mistakes it for dBm.
            current["signalDbm"] = None
            current["signalPercent"] = int(match.group(1))
            continue

        match = re.match(r"Channel\s*:\s*(\d+)", line, re.IGNORECASE)
        if match:
            current["frequency"] = channel_to_frequency(match.group(1))
            current["channel"] = int(match.group(1))

    return networks


def register(api, gateway_id, hotspot_id=None):
    return post_json(
        f"{api}/api/gateways/{gateway_id}/register",
        {
            "gatewayId": gateway_id,
            "hotspotId": hotspot_id or None,
            "version": VERSION,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
        },
    )


def heartbeat(api, gateway_id):
    return post_json(
        f"{api}/api/gateways/{gateway_id}/heartbeat",
        {
            "gatewayId": gateway_id,
            "version": VERSION,
            "status": "ONLINE",
            "hostname": socket.gethostname(),
        },
    )


def report_scan(api, gateway_id, networks):
    observed_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "gatewayId": gateway_id,
        "observedAt": observed_at,
        "hotspots": [
            {
                "gatewayId": gateway_id,
                "ssid": network["ssid"],
                "bssid": network["bssid"],
                "signalDbm": network.get("signalDbm"),
                "frequency": network.get("frequency"),
                "security": network.get("security", "OPEN"),
                "observedAt": observed_at,
            }
            for network in networks
        ],
    }
    return post_json(f"{api}/api/gateways/{gateway_id}/scan", payload)


def get_policy(api, gateway_id):
    return get_json(f"{api}/api/gateways/{gateway_id}/policy")


def get_commands(api, gateway_id):
    return get_json(f"{api}/api/gateways/{gateway_id}/commands")
