#!/usr/bin/env python3
import argparse, json, platform, socket, subprocess, time, urllib.request

def run(cmd):
    return subprocess.run(cmd,text=True,capture_output=True,check=False)

def heartbeat(api,gateway_id):
    data=json.dumps({"gatewayId":gateway_id,"version":"0.2.0-linux-agent","status":"ONLINE"}).encode()
    req=urllib.request.Request(f"{api}/api/gateways/{gateway_id}/heartbeat",data=data,
        headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=5) as r: return r.status

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--api",default="http://127.0.0.1:8080")
    p.add_argument("--gateway-id",default=socket.gethostname())
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--once",action="store_true")
    a=p.parse_args()
    print("NetworkStream Linux Gateway Agent")
    print("platform:",platform.platform())
    print("gateway:",a.gateway_id)
    if a.dry_run:
        print("DRY RUN: no routing/firewall changes.")
        for cmd in [["ip","addr"],["ip","route"]]:
            r=run(cmd); print("$ "+" ".join(cmd)); print(r.stdout or r.stderr)
    while True:
        try: print("heartbeat:",heartbeat(a.api,a.gateway_id))
        except Exception as e: print("heartbeat failed:",e)
        if a.once: break
        time.sleep(10)

if __name__=="__main__": main()
