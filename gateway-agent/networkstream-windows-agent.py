#!/usr/bin/env python3
"""NetworkStream Windows gateway agent.

Observation is always enabled. Data-plane mode is opt-in and uses the existing
Windows Mobile Hotspot/ICS path as the downstream transport while NetworkStream
controls client access with Windows Firewall rules. It never changes routing
or creates an AP automatically.
"""
import argparse, json, platform, re, socket, subprocess, time, urllib.request
from datetime import datetime, timezone

VERSION = "0.6.0-windows-agent"
INTERNET_TEST_URL = "https://www.google.com/generate_204"
DOWNSTREAM_PREFIX = "192.168.137."
FIREWALL_PREFIX = "NetworkStream-Client-"

def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True, check=False)

def post_json(url, payload):
    data=json.dumps(payload).encode("utf-8")
    request=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json","Accept":"application/json"},method="POST")
    with urllib.request.urlopen(request,timeout=8) as response:
        body=response.read().decode("utf-8")
        return json.loads(body) if body else None

def get_json(url):
    request=urllib.request.Request(url,headers={"Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=8) as response:
        body=response.read().decode("utf-8")
        return json.loads(body) if body else None

def internet_reachable():
    try:
        with urllib.request.urlopen(INTERNET_TEST_URL,timeout=5) as response:
            return 200 <= response.status < 400
    except Exception:
        return False

def channel_to_frequency(channel):
    try: channel=int(channel)
    except (TypeError,ValueError): return None
    if 1 <= channel <= 13: return f"{2407 + channel*5} MHz"
    if channel == 14: return "2484 MHz"
    if 36 <= channel <= 177: return f"{5000 + channel*5} MHz"
    return None

def scan_wifi():
    result=run(["netsh","wlan","show","networks","mode=bssid"])
    if result.returncode != 0: raise RuntimeError(result.stderr.strip() or "netsh Wi-Fi scan failed")
    networks=[]; current_ssid=None; current=None; current_auth="OPEN"; current_encryption=None
    for raw in result.stdout.splitlines():
        line=raw.strip()
        if not line: continue
        match=re.match(r"SSID\s+\d+\s*:\s*(.*)$",line,re.I)
        if match:
            current_ssid=match.group(1).strip() or "<hidden>"; current=None; current_auth="OPEN"; current_encryption=None; continue
        match=re.match(r"Authentication\s*:\s*(.*)$",line,re.I)
        if match:
            current_auth=match.group(1).strip() or "OPEN"
            if current is not None: current["security"]=current_auth
            continue
        match=re.match(r"Encryption\s*:\s*(.*)$",line,re.I)
        if match:
            current_encryption=match.group(1).strip()
            if current is not None and current_encryption.lower() != "none": current["security"]=f"{current_auth}/{current_encryption}"
            continue
        match=re.match(r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]+)",line,re.I)
        if match and current_ssid is not None:
            security=current_auth if not current_encryption or current_encryption.lower()=="none" else f"{current_auth}/{current_encryption}"
            current={"ssid":current_ssid,"bssid":match.group(1).lower(),"signalDbm":None,"signalPercent":None,"frequency":None,"security":security}
            networks.append(current); continue
        if current is None: continue
        match=re.match(r"Signal\s*:\s*(\d+)%",line,re.I)
        if match: current["signalPercent"]=int(match.group(1)); continue
        match=re.match(r"Channel\s*:\s*(\d+)",line,re.I)
        if match: current["frequency"]=channel_to_frequency(match.group(1)); current["channel"]=int(match.group(1))
    return networks

def discover_clients():
    result=run(["arp","-a"])
    if result.returncode != 0: return []
    clients=[]
    for line in result.stdout.splitlines():
        match=re.search(r"^\s*(192\.168\.137\.\d+)\s+([0-9a-fA-F-]{17})\s+\w+",line)
        if match:
            ip,mac=match.group(1),match.group(2).lower().replace("-",":")
            if ip != "192.168.137.1": clients.append({"ipAddress":ip,"macAddress":mac,"hostname":None})
    unique={c["ipAddress"]:c for c in clients}
    return list(unique.values())

def apply_firewall(ip, allow):
    if not re.fullmatch(r"192\.168\.137\.\d{1,3}",ip): raise ValueError("Only downstream Mobile Hotspot clients can be controlled")
    name=f"{FIREWALL_PREFIX}{ip}"
    run(["powershell","-NoProfile","-Command",f"Remove-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue"])
    if not allow:
        command=(f"New-NetFirewallRule -DisplayName '{name}' -Direction Outbound -RemoteAddress {ip} -Action Block -Profile Any; "
                 f"New-NetFirewallRule -DisplayName '{name}-Inbound' -Direction Inbound -RemoteAddress {ip} -Action Block -Profile Any")
        result=run(["powershell","-NoProfile","-Command",command])
        if result.returncode != 0: raise RuntimeError(result.stderr.strip() or "Windows Firewall update failed; run the agent elevated")

def register(api,gateway_id,hotspot_id=None):
    return post_json(f"{api}/api/gateways/{gateway_id}/register",{"gatewayId":gateway_id,"hotspotId":hotspot_id or None,"version":VERSION,"hostname":socket.gethostname(),"platform":platform.platform()})

def heartbeat(api,gateway_id):
    return post_json(f"{api}/api/gateways/{gateway_id}/heartbeat",{"gatewayId":gateway_id,"version":VERSION,"status":"ONLINE","hostname":socket.gethostname()})

def report_scan(api,gateway_id,networks):
    observed_at=datetime.now(timezone.utc).isoformat()
    payload={"gatewayId":gateway_id,"observedAt":observed_at,"hotspots":[{"gatewayId":gateway_id,"ssid":n["ssid"],"bssid":n["bssid"],"signalDbm":n.get("signalDbm"),"signalPercent":n.get("signalPercent"),"frequency":n.get("frequency"),"security":n.get("security","OPEN"),"observedAt":observed_at} for n in networks]}
    return post_json(f"{api}/api/gateways/{gateway_id}/scan",payload)

def report_telemetry(api,gateway_id,clients,internet_online):
    payload={"gatewayId":gateway_id,"observedAt":datetime.now(timezone.utc).isoformat(),"internetOnline":internet_online,
             "upstreamInterface":"Wi-Fi","upstreamAddress":None,"downstreamInterface":"Windows Mobile Hotspot",
             "downstreamAddress":"192.168.137.1","clients":clients}
    return post_json(f"{api}/api/gateways/{gateway_id}/telemetry",payload)

def get_policy(api,gateway_id): return get_json(f"{api}/api/gateways/{gateway_id}/policy")
def get_commands(api,gateway_id): return get_json(f"{api}/api/gateways/{gateway_id}/commands")
def ack_command(api,gateway_id,command_id): return post_json(f"{api}/api/gateways/{gateway_id}/commands/{command_id}/ack",{})

def process_commands(api,gateway_id):
    for command in get_commands(api,gateway_id) or []:
        try:
            if command.get("type")=="ALLOW_CLIENT": apply_firewall(command["value"],True)
            elif command.get("type")=="BLOCK_CLIENT": apply_firewall(command["value"],False)
            else: raise ValueError(f"Unsupported command: {command.get('type')}")
            ack_command(api,gateway_id,command["id"])
            print("command applied:",command)
        except Exception as error:
            print("command failed:",command,"error:",error)

def main():
    parser=argparse.ArgumentParser(description="NetworkStream Windows gateway agent")
    parser.add_argument("--api",default="http://127.0.0.1:8080"); parser.add_argument("--gateway-id",default=f"WIN-{socket.gethostname()}")
    parser.add_argument("--hotspot-id",default=None); parser.add_argument("--scan",action="store_true")
    parser.add_argument("--no-scan",action="store_true"); parser.add_argument("--data-plane",action="store_true",help="Control clients on the existing Windows Mobile Hotspot with firewall rules")
    parser.add_argument("--once",action="store_true"); parser.add_argument("--interval",type=int,default=30); args=parser.parse_args()
    scan_enabled=not args.no_scan
    print("NetworkStream Windows Gateway Agent",VERSION); print("gateway:",args.gateway_id); print("host:",socket.gethostname())
    print("data-plane:","ENABLED" if args.data_plane else "observation-only")
    try: print("register:",register(args.api,args.gateway_id,args.hotspot_id))
    except Exception as error: print("registration failed:",error); return 1
    while True:
        try:
            print("heartbeat:",heartbeat(args.api,args.gateway_id)); online=internet_reachable(); print("internet:","ONLINE" if online else "OFFLINE")
            networks=scan_wifi() if scan_enabled else []
            if scan_enabled:
                print(f"nearby Wi-Fi networks: {len(networks)}")
                for network in networks: print("  ",network)
                print("scan report:",report_scan(args.api,args.gateway_id,networks))
            clients=discover_clients(); print("downstream clients:",clients)
            print("telemetry:",report_telemetry(args.api,args.gateway_id,clients,online))
            if args.data_plane: process_commands(args.api,args.gateway_id)
            print("policy:",json.dumps(get_policy(args.api,args.gateway_id),indent=2)); print("commands:",json.dumps(get_commands(args.api,args.gateway_id),indent=2))
        except Exception as error: print("gateway communication failed:",error)
        if args.once: break
        time.sleep(max(5,args.interval))
    return 0

if __name__=="__main__": raise SystemExit(main())
