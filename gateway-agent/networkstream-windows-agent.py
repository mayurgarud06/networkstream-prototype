#!/usr/bin/env python3
"""NetworkStream Windows gateway agent.
Safe by default: observes Wi-Fi and downstream clients. With --data-plane,
new Windows Mobile Hotspot clients are blocked until NetworkStream authorizes
them. Telemetry separates policy from observed Internet flow.
"""
import argparse,json,platform,re,socket,subprocess,threading,time,urllib.request
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
VERSION="0.7.0-windows-agent"; INTERNET_TEST_URL="https://www.google.com/generate_204"; FIREWALL_PREFIX="NetworkStream-Client-"; DOWNSTREAM_RE=re.compile(r"^192\.168\.137\.(\d{1,3})$")
def run(cmd): return subprocess.run(cmd,text=True,capture_output=True,check=False)
def is_admin():
 r=run(["powershell","-NoProfile","-Command","([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"]); return r.returncode==0 and r.stdout.strip().lower()=="true"
def post_json(url,payload):
 req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","Accept":"application/json"},method="POST")
 with urllib.request.urlopen(req,timeout=8) as r:
  b=r.read().decode(); return json.loads(b) if b else None
def get_json(url):
 req=urllib.request.Request(url,headers={"Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=8) as r:
  b=r.read().decode(); return json.loads(b) if b else None
def internet_reachable():
 try:
  with urllib.request.urlopen(INTERNET_TEST_URL,timeout=5) as r:return 200<=r.status<400
 except Exception:return False
def channel_to_frequency(c):
 try:c=int(c)
 except(TypeError,ValueError):return None
 if 1<=c<=13:return f"{2407+c*5} MHz"
 if c==14:return "2484 MHz"
 if 36<=c<=177:return f"{5000+c*5} MHz"
 return None
def scan_wifi():
 r=run(["netsh","wlan","show","networks","mode=bssid"])
 if r.returncode!=0:raise RuntimeError(r.stderr.strip() or "netsh Wi-Fi scan failed")
 out=[]; ssid=None; cur=None; auth="OPEN"; enc=None
 for raw in r.stdout.splitlines():
  line=raw.strip()
  if not line:continue
  m=re.match(r"SSID\s+\d+\s*:\s*(.*)$",line,re.I)
  if m:ssid=m.group(1).strip() or "<hidden>";cur=None;auth="OPEN";enc=None;continue
  m=re.match(r"Authentication\s*:\s*(.*)$",line,re.I)
  if m:auth=m.group(1).strip() or "OPEN";continue
  m=re.match(r"Encryption\s*:\s*(.*)$",line,re.I)
  if m:enc=m.group(1).strip();continue
  m=re.match(r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]+)",line,re.I)
  if m and ssid is not None:
   sec=auth if not enc or enc.lower()=="none" else f"{auth}/{enc}";cur={"ssid":ssid,"bssid":m.group(1).lower(),"signalDbm":None,"signalPercent":None,"frequency":None,"security":sec};out.append(cur);continue
  if cur is None:continue
  m=re.match(r"Signal\s*:\s*(\d+)%",line,re.I)
  if m:cur["signalPercent"]=int(m.group(1))
  m=re.match(r"Channel\s*:\s*(\d+)",line,re.I)
  if m:cur["frequency"]=channel_to_frequency(m.group(1));cur["channel"]=int(m.group(1))
 return out
def discover_clients():
 r=run(["arp","-a"])
 if r.returncode!=0:return[]
 out=[]
 for line in r.stdout.splitlines():
  m=re.search(r"^\s*(192\.168\.137\.\d+)\s+([0-9a-fA-F-]{17})\s+\w+",line)
  if not m:continue
  ip=m.group(1)
  if 2<=int(ip.rsplit('.',1)[1])<=254:out.append({"ipAddress":ip,"macAddress":m.group(2).lower().replace('-',':'),"hostname":None})
 return list({x["ipAddress"]:x for x in out}.values())
def validate_client_ip(ip):
 m=DOWNSTREAM_RE.fullmatch(ip or "")
 if not m or not 2<=int(m.group(1))<=254:raise ValueError("Only Windows Mobile Hotspot clients in 192.168.137.0/24 can be controlled")
def firewall_rule_names(ip):
 s=ip.replace('.','-');return f"{FIREWALL_PREFIX}{s}-Block",f"{FIREWALL_PREFIX}{s}-Portal"
def apply_firewall(ip,allow):
 validate_client_ip(ip);bn,pn=firewall_rule_names(ip);cleanup=f"Remove-NetFirewallRule -DisplayName '{bn}' -ErrorAction SilentlyContinue; Remove-NetFirewallRule -DisplayName '{pn}' -ErrorAction SilentlyContinue";run(["powershell","-NoProfile","-Command",cleanup])
 if allow:return
 cmd=f"New-NetFirewallRule -DisplayName '{bn}' -Direction Inbound -RemoteAddress {ip} -Action Block -Profile Any; New-NetFirewallRule -DisplayName '{pn}' -Direction Inbound -RemoteAddress {ip} -Protocol TCP -LocalPort 3000,8081 -Action Allow -Profile Any -OverrideBlockRules $true"
 r=run(["powershell","-NoProfile","-Command",cmd])
 if r.returncode!=0:
  e=r.stderr.strip() or r.stdout.strip() or "Windows Firewall update failed"
  if "Access is denied" in e or "System Error 5" in e:raise RuntimeError("Windows Firewall access denied. Restart PowerShell as Administrator and run the gateway agent again.")
  raise RuntimeError(e)
def downstream_ssid():
 r=run(["netsh","wlan","show","hostednetwork"])
 if r.returncode==0:
  for line in r.stdout.splitlines():
   m=re.search(r"SSID name\s*:\s*(.*)$",line,re.I)
   if m and m.group(1).strip():return m.group(1).strip()
 return "Windows Mobile Hotspot"
def nat_sessions_for_clients(ips):
 if not ips:return{}
 r=run(["powershell","-NoProfile","-Command","Get-NetNatSession -ErrorAction Stop | Select-Object InternalSourceAddress,CreationTime | ConvertTo-Json -Compress"])
 if r.returncode!=0 or not r.stdout.strip():return{}
 try:d=json.loads(r.stdout)
 except json.JSONDecodeError:return{}
 if isinstance(d,dict):d=[d]
 g={ip:[] for ip in ips}
 for x in d or []:
  ip=str(x.get("InternalSourceAddress") or "")
  if ip in g:g[ip].append(x)
 return g
def internet_state(authorized,upstream,sessions):
 if not authorized:return"BLOCKED"
 if not upstream:return"UPSTREAM_OFFLINE"
 return"FLOWING" if sessions else"ALLOWED_NO_FLOW"
def register(api,gid,hid=None):return post_json(f"{api}/api/gateways/{gid}/register",{"gatewayId":gid,"hotspotId":hid or None,"version":VERSION,"hostname":socket.gethostname(),"platform":platform.platform()})
def heartbeat(api,gid):return post_json(f"{api}/api/gateways/{gid}/heartbeat",{"gatewayId":gid,"version":VERSION,"status":"ONLINE","hostname":socket.gethostname()})
def report_scan(api,gid,nets):
 o=datetime.now(timezone.utc).isoformat();p={"gatewayId":gid,"observedAt":o,"hotspots":[{"gatewayId":gid,"ssid":n["ssid"],"bssid":n["bssid"],"signalDbm":n.get("signalDbm"),"signalPercent":n.get("signalPercent"),"frequency":n.get("frequency"),"security":n.get("security","OPEN"),"observedAt":o} for n in nets]};return post_json(f"{api}/api/gateways/{gid}/scan",p)
def report_telemetry(api,gid,clients,online,dname,authorized,nats):
 o=datetime.now(timezone.utc);en=[]
 for c in clients:
  ip=c["ipAddress"];s=nats.get(ip,[]);a=ip in authorized;en.append({**c,"ssid":dname,"authorized":a,"internetStatus":internet_state(a,online,len(s)),"activeNatSessions":len(s),"lastTrafficAt":max((x.get("CreationTime") for x in s if x.get("CreationTime")),default=None)})
 p={"gatewayId":gid,"observedAt":o.isoformat(),"internetOnline":online,"upstreamInterface":"Wi-Fi","upstreamAddress":None,"downstreamInterface":"Windows Mobile Hotspot","downstreamAddress":"192.168.137.1","downstreamSsid":dname,"clients":en};return post_json(f"{api}/api/gateways/{gid}/telemetry",p)
def get_policy(api,gid):return get_json(f"{api}/api/gateways/{gid}/policy")
def get_commands(api,gid):return get_json(f"{api}/api/gateways/{gid}/commands")
def ack(api,gid,cid):return post_json(f"{api}/api/gateways/{gid}/commands/{cid}/ack",{})
def process_commands(api,gid,authorized):
 for c in get_commands(api,gid) or []:
  try:
   ip=c.get("value")
   if c.get("type")=="ALLOW_CLIENT":apply_firewall(ip,True);authorized.add(ip)
   elif c.get("type")=="BLOCK_CLIENT":apply_firewall(ip,False);authorized.discard(ip)
   else:raise ValueError(f"Unsupported command: {c.get('type')}")
   ack(api,gid,c["id"]);print("command applied:",c)
  except Exception as e:print("command failed:",c,"error:",e)
def start_client_endpoint(port):
 class H(BaseHTTPRequestHandler):
  def do_GET(self):
   if self.path not in("/client","/health"):self.send_response(404);self.end_headers();return
   b=b'{"status":"OK"}' if self.path=="/health" else json.dumps({"clientIp":self.client_address[0],"gatewayAddress":"192.168.137.1","frontendPort":3000}).encode();self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
  def log_message(self,*args):return
 s=ThreadingHTTPServer(("0.0.0.0",port),H);threading.Thread(target=s.serve_forever,daemon=True).start();return s
def cleanup(ips):
 for ip in sorted(ips):
  try:apply_firewall(ip,True)
  except Exception as e:print("firewall cleanup failed:",ip,e)
def main():
 p=argparse.ArgumentParser();p.add_argument("--api",default="http://127.0.0.1:8080");p.add_argument("--gateway-id",default=f"WIN-{socket.gethostname()}");p.add_argument("--hotspot-id",default=None);p.add_argument("--no-scan",action="store_true");p.add_argument("--data-plane",action="store_true");p.add_argument("--once",action="store_true");p.add_argument("--interval",type=float,default=15.0);p.add_argument("--portal-port",type=int,default=8081);a=p.parse_args()
 if a.data_plane and not is_admin():raise SystemExit("NetworkStream data-plane requires an elevated PowerShell window. Right-click PowerShell -> Run as administrator, then start the agent again.")
 auth=set();managed=set();print("NetworkStream Windows Gateway Agent",VERSION);print("gateway:",a.gateway_id);print("host:",socket.gethostname());print("data-plane:","ENABLED" if a.data_plane else"observation-only");portal=start_client_endpoint(a.portal_port)
 try:
  print("register:",register(a.api,a.gateway_id,a.hotspot_id))
  while True:
   try:
    print("heartbeat:",heartbeat(a.api,a.gateway_id));online=internet_reachable();print("internet:","ONLINE" if online else"OFFLINE");clients=discover_clients();managed.update(c["ipAddress"] for c in clients);dname=downstream_ssid()
    if a.data_plane:
     process_commands(a.api,a.gateway_id,auth)
     for c in clients:apply_firewall(c["ipAddress"],c["ipAddress"] in auth)
    if not a.no_scan:
     nets=scan_wifi();print(f"nearby Wi-Fi networks: {len(nets)}");print("scan report:",report_scan(a.api,a.gateway_id,nets))
    nats=nat_sessions_for_clients([c["ipAddress"] for c in clients]);print("downstream clients:",clients);print("telemetry:",report_telemetry(a.api,a.gateway_id,clients,online,dname,auth,nats));print("authorized clients:",sorted(auth));print("policy:",json.dumps(get_policy(a.api,a.gateway_id),indent=2));print("commands:",json.dumps(get_commands(a.api,a.gateway_id),indent=2))
   except Exception as e:print("gateway communication failed:",e)
   if a.once:break
   time.sleep(max(5.0,a.interval))
 except KeyboardInterrupt:print("stopping Windows gateway agent")
 finally:
  if a.data_plane:cleanup(managed)
  portal.shutdown()
 return 0
if __name__=="__main__":raise SystemExit(main())