#!/usr/bin/env python3
import argparse,json,platform,re,socket,subprocess,threading,time,urllib.request
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
VERSION="0.7.0-windows-agent";TEST="https://www.google.com/generate_204";PREFIX="NetworkStream-Client-";RE=re.compile(r"^192\.168\.137\.(\d{1,3})$")
def run(c):return subprocess.run(c,text=True,capture_output=True,check=False)
def admin():
 r=run(["powershell","-NoProfile","-Command","([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"]);return r.returncode==0 and r.stdout.strip().lower()=="true"
def post(u,p):
 r=urllib.request.Request(u,data=json.dumps(p).encode(),headers={"Content-Type":"application/json","Accept":"application/json"},method="POST")
 with urllib.request.urlopen(r,timeout=8) as x:
  b=x.read().decode();return json.loads(b) if b else None
def get(u):
 r=urllib.request.Request(u,headers={"Accept":"application/json"})
 with urllib.request.urlopen(r,timeout=8) as x:
  b=x.read().decode();return json.loads(b) if b else None
def online():
 try:
  with urllib.request.urlopen(TEST,timeout=5) as r:return 200<=r.status<400
 except:return False
def scan():
 r=run(["netsh","wlan","show","networks","mode=bssid"])
 if r.returncode:raise RuntimeError(r.stderr.strip() or "Wi-Fi scan failed")
 out=[];ssid=None;cur=None;auth="OPEN";enc=None
 for z in r.stdout.splitlines():
  s=z.strip()
  if not s:continue
  m=re.match(r"SSID\s+\d+\s*:\s*(.*)$",s,re.I)
  if m:ssid=m.group(1).strip() or "<hidden>";cur=None;auth="OPEN";enc=None;continue
  m=re.match(r"Authentication\s*:\s*(.*)$",s,re.I)
  if m:auth=m.group(1).strip() or "OPEN";continue
  m=re.match(r"Encryption\s*:\s*(.*)$",s,re.I)
  if m:enc=m.group(1).strip();continue
  m=re.match(r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]+)",s,re.I)
  if m and ssid is not None:cur={"ssid":ssid,"bssid":m.group(1).lower(),"signalDbm":None,"signalPercent":None,"frequency":None,"security":auth if not enc or enc.lower()=="none" else f"{auth}/{enc}"};out.append(cur);continue
  if cur is None:continue
  m=re.match(r"Signal\s*:\s*(\d+)%",s,re.I)
  if m:cur["signalPercent"]=int(m.group(1))
  m=re.match(r"Channel\s*:\s*(\d+)",s,re.I)
  if m:
   c=int(m.group(1));cur["frequency"]=f"{2407+c*5} MHz" if 1<=c<=13 else ("2484 MHz" if c==14 else f"{5000+c*5} MHz" if 36<=c<=177 else None)
def clients():
 r=run(["arp","-a"]);out=[]
 if r.returncode:return out
 for s in r.stdout.splitlines():
  m=re.search(r"^\s*(192\.168\.137\.\d+)\s+([0-9a-fA-F-]{17})\s+\w+",s)
  if m and 2<=int(m.group(1).rsplit('.',1)[1])<=254:out.append({"ipAddress":m.group(1),"macAddress":m.group(2).lower().replace('-',':'),"hostname":None})
 return list({x["ipAddress"]:x for x in out}.values())
def valid(ip):
 m=RE.fullmatch(ip or "")
 if not m or not 2<=int(m.group(1))<=254:raise ValueError("Only 192.168.137.2-254 clients can be controlled")
def names(ip):s=ip.replace('.','-');return f"{PREFIX}{s}-Block",f"{PREFIX}{s}-Portal"
def firewall(ip,allow):
 valid(ip);bn,pn=names(ip);run(["powershell","-NoProfile","-Command",f"Remove-NetFirewallRule -DisplayName '{bn}' -ErrorAction SilentlyContinue; Remove-NetFirewallRule -DisplayName '{pn}' -ErrorAction SilentlyContinue"])
 if allow:return
 r=run(["powershell","-NoProfile","-Command",f"New-NetFirewallRule -DisplayName '{bn}' -Direction Inbound -RemoteAddress {ip} -Action Block -Profile Any; New-NetFirewallRule -DisplayName '{pn}' -Direction Inbound -RemoteAddress {ip} -Protocol TCP -LocalPort 3000,8081 -Action Allow -Profile Any -OverrideBlockRules $true"])
 if r.returncode:
  e=r.stderr.strip() or r.stdout.strip() or "Firewall update failed"
  if "Access is denied" in e or "System Error 5" in e:raise RuntimeError("Windows Firewall access denied. Run PowerShell as Administrator.")
  raise RuntimeError(e)
def ssid():
 r=run(["netsh","wlan","show","hostednetwork"])
 if not r.returncode:
  for s in r.stdout.splitlines():
   m=re.search(r"SSID name\s*:\s*(.*)$",s,re.I)
   if m and m.group(1).strip():return m.group(1).strip()
 return "Windows Mobile Hotspot"
def nats(ips):
 if not ips:return{}
 r=run(["powershell","-NoProfile","-Command","Get-NetNatSession -ErrorAction Stop | Select-Object InternalSourceAddress,CreationTime | ConvertTo-Json -Compress"])
 if r.returncode or not r.stdout.strip():return{}
 try:d=json.loads(r.stdout)
 except:return{}
 if isinstance(d,dict):d=[d]
 g={x:[] for x in ips}
 for x in d or []:
  ip=str(x.get("InternalSourceAddress") or "")
  if ip in g:g[ip].append(x)
 return g
def register(a,g,h=None):return post(f"{a}/api/gateways/{g}/register",{"gatewayId":g,"hotspotId":h,"version":VERSION,"hostname":socket.gethostname(),"platform":platform.platform()})
def heartbeat(a,g):return post(f"{a}/api/gateways/{g}/heartbeat",{"gatewayId":g,"version":VERSION,"status":"ONLINE","hostname":socket.gethostname()})
def reportscan(a,g,ns):
 o=datetime.now(timezone.utc).isoformat();return post(f"{a}/api/gateways/{g}/scan",{"gatewayId":g,"observedAt":o,"hotspots":[{"gatewayId":g,"ssid":x["ssid"],"bssid":x["bssid"],"signalDbm":x.get("signalDbm"),"signalPercent":x.get("signalPercent"),"frequency":x.get("frequency"),"security":x.get("security","OPEN"),"observedAt":o} for x in ns]})
def telemetry(a,g,cs,up,dn,auth,ns):
 e=[]
 for c in cs:
  ip=c["ipAddress"];s=ns.get(ip,[]);ok=ip in auth;state="BLOCKED" if not ok else ("UPSTREAM_OFFLINE" if not up else ("FLOWING" if s else "ALLOWED_NO_FLOW"));e.append({**c,"ssid":dn,"authorized":ok,"internetStatus":state,"activeNatSessions":len(s),"lastTrafficAt":max((x.get("CreationTime") for x in s if x.get("CreationTime")),default=None)})
 return post(f"{a}/api/gateways/{g}/telemetry",{"gatewayId":g,"observedAt":datetime.now(timezone.utc).isoformat(),"internetOnline":up,"upstreamInterface":"Wi-Fi","upstreamAddress":None,"downstreamInterface":"Windows Mobile Hotspot","downstreamAddress":"192.168.137.1","downstreamSsid":dn,"clients":e})
def commands(a,g):return get(f"{a}/api/gateways/{g}/commands")
def ack(a,g,i):return post(f"{a}/api/gateways/{g}/commands/{i}/ack",{})
def process(a,g,auth):
 for c in commands(a,g) or []:
  try:
   ip=c.get("value")
   if c.get("type")=="ALLOW_CLIENT":firewall(ip,True);auth.add(ip)
   elif c.get("type")=="BLOCK_CLIENT":firewall(ip,False);auth.discard(ip)
   else:raise ValueError(c.get("type"))
   ack(a,g,c["id"]);print("command applied:",c)
  except Exception as e:print("command failed:",c,"error:",e)
def endpoint(port):
 class H(BaseHTTPRequestHandler):
  def do_GET(self):
   if self.path not in("/client","/health"):self.send_response(404);self.end_headers();return
   b=b'{"status":"OK"}' if self.path=="/health" else json.dumps({"clientIp":self.client_address[0],"gatewayAddress":"192.168.137.1","frontendPort":3000}).encode();self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
  def log_message(self,*a):return
 s=ThreadingHTTPServer(("0.0.0.0",port),H);threading.Thread(target=s.serve_forever,daemon=True).start();return s
def main():
 p=argparse.ArgumentParser();p.add_argument("--api",default="http://127.0.0.1:8080");p.add_argument("--gateway-id",default=f"WIN-{socket.gethostname()}");p.add_argument("--hotspot-id",default=None);p.add_argument("--no-scan",action="store_true");p.add_argument("--data-plane",action="store_true");p.add_argument("--once",action="store_true");p.add_argument("--interval",type=float,default=15.0);p.add_argument("--portal-port",type=int,default=8081);x=p.parse_args()
 if x.data_plane and not admin():raise SystemExit("NetworkStream data-plane requires an elevated PowerShell window. Run PowerShell as Administrator.")
 auth=set();managed=set();print("NetworkStream Windows Gateway Agent",VERSION);print("gateway:",x.gateway_id);print("host:",socket.gethostname());print("data-plane:","ENABLED" if x.data_plane else "observation-only");ep=endpoint(x.portal_port)
 try:
  print("register:",register(x.api,x.gateway_id,x.hotspot_id))
  while True:
   try:
    print("heartbeat:",heartbeat(x.api,x.gateway_id));up=online();print("internet:","ONLINE" if up else"OFFLINE");cs=clients();managed.update(c["ipAddress"] for c in cs);dn=ssid()
    if x.data_plane:
     process(x.api,x.gateway_id,auth)
     for c in cs:firewall(c["ipAddress"],c["ipAddress"] in auth)
    if not x.no_scan:
     ns=scan();print(f"nearby Wi-Fi networks: {len(ns)}");print("scan report:",reportscan(x.api,x.gateway_id,ns))
    nt=nats([c["ipAddress"] for c in cs]);print("downstream clients:",cs);print("telemetry:",telemetry(x.api,x.gateway_id,cs,up,dn,auth,nt));print("authorized clients:",sorted(auth));print("commands:",json.dumps(commands(x.api,x.gateway_id),indent=2))
   except Exception as e:print("gateway communication failed:",e)
   if x.once:break
   time.sleep(max(5.0,x.interval))
 except KeyboardInterrupt:print("stopping Windows gateway agent")
 finally:
  if x.data_plane:
   for ip in managed:
    try:firewall(ip,True)
    except Exception as e:print("firewall cleanup failed:",ip,e)
  ep.shutdown()
if __name__=="__main__":main()
