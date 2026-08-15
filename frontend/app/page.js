"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API||"http://localhost:8080";

export default function Home(){
 const [hotspots,setHotspots]=useState([]),[observed,setObserved]=useState([]),[session,setSession]=useState(null),[tab,setTab]=useState("discover"),[error,setError]=useState("");
 async function load(){
   try{
     const [managed,nearby]=await Promise.all([
       fetch(`${API}/api/hotspots`).then(r=>r.json()),
       fetch(`${API}/api/hotspots/observed?seconds=180`).then(r=>r.json())
     ]);
     setHotspots(managed); setObserved(nearby);
   }catch(e){setError(e.message)}
 }
 useEffect(()=>{load(); const timer=setInterval(load,15000); return()=>clearInterval(timer)},[]);
 async function connect(h) {
   setError("");
   const response=await fetch(`${API}/api/sessions`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userId:"DEMO-USER",hotspotId:h.id})});
   const body=await response.json();
   if(!response.ok){setError(body.message||"Connection failed");return}
   setSession(body);
 }
 async function action(path,body){
   if(!session)return;
   const response=await fetch(`${API}/api/sessions/${session.id}/${path}`,{method:"POST",headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
   const next=await response.json(); if(response.ok)setSession(next); else setError(next.message||"Request failed");
 }
 return <main>
  <header><div><strong>NetworkStream</strong><small> Connectivity, as a software layer.</small></div>
   <nav><button onClick={()=>setTab("discover")}>Discover</button><button onClick={()=>setTab("provider")}>Provider</button></nav>
  </header>
  <section className="hero"><label>PROTOTYPE · SOFTWARE GATEWAY</label><h1>Explore real nearby Wi-Fi, then connect through NetworkStream.</h1><p>Nearby networks are scanned by a NetworkStream Linux gateway. The gateway never joins discovered networks automatically.</p></section>
  {error&&<section className="session"><b>ERROR</b><p>{error}</p></section>}
  {tab==="discover"?<>
   <section><h2>NetworkStream hotspots</h2><div className="grid">{hotspots.map(h=><article className="card" key={h.id}>
    <div className="meta">● {h.status}<span>{h.accessType}</span></div><h2>{h.name}</h2><p>{h.providerName}</p>
    <div className="stats"><div><b>{h.speedMbps} Mbps</b><small>advertised</small></div><div><b>{h.priceInr?`₹${h.priceInr}`:"Free"}</b><small>premium</small></div></div>
    <button disabled={h.status!=="ONLINE"} onClick={()=>connect(h)}>Connect</button>
   </article>)}</div></section>
   <section><h2>Nearby Wi-Fi observed by gateways</h2><p>These are physical radio observations, not yet NetworkStream-approved hotspots.</p><div className="grid">{observed.length===0?<article className="card"><p>No recent gateway scan. Run the Linux agent with <code>--scan --once</code>.</p></article>:observed.map((h,i)=><article className="card" key={`${h.bssid||h.ssid}-${i}`}>
     <div className="meta">RADIO OBSERVATION<span>{h.security||"OPEN"}</span></div><h2>{h.ssid}</h2><p>{h.bssid||"BSSID unavailable"}</p><div className="stats"><div><b>{h.signalDbm??"?"}{h.signalDbm!=null?" dBm":""}</b><small>signal</small></div><div><b>{h.frequency||"?"}</b><small>frequency</small></div></div>
     <small>Observed by {h.gatewayId} · {new Date(h.observedAt).toLocaleTimeString()}</small>
   </article>)}</div></section>
   {session&&<section className="session"><b>{session.status} · {session.plan}</b><h2>{session.hotspotId}</h2><p>Gateway: {session.gatewayId||"pending"}</p><p>{session.speedMbps} Mbps · {session.usedMb}/{session.quotaMb} MB</p><button onClick={()=>action("usage",{bytesUsed:100*1024*1024})}>Simulate 100 MB (demo only)</button><button className="light" onClick={()=>action("upgrade")}>Upgrade</button><button className="danger" onClick={()=>action("end")}>Disconnect</button></section>}
  </>:<section><h2>Provider gateway status</h2><div className="grid">{hotspots.map(h=><article className="card" key={h.id}><div className="meta">● {h.status}</div><h2>{h.name}</h2><p>Gateway: {h.gatewayId}</p><p>Provider: {h.providerName}</p></article>)}</div></section>}
 </main>
}
