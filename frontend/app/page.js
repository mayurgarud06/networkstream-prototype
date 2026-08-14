"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API||"http://localhost:8080";
export default function Home(){
 const [hotspots,setHotspots]=useState([]),[session,setSession]=useState(null),[tab,setTab]=useState("discover");
 async function load(){setHotspots(await (await fetch(`${API}/api/hotspots`)).json())}
 useEffect(()=>{load()},[]);
 async function connect(h,plan){
  setSession(await (await fetch(`${API}/api/sessions`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userId:"DEMO-USER",hotspotId:h.id,plan})})).json())
 }
 async function action(path,body){
  if(!session)return;
  setSession(await (await fetch(`${API}/api/sessions/${session.id}/${path}`,{method:"POST",headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined})).json())
 }
 return <main>
  <header><div><strong>NetworkStream</strong><small> Connectivity, as a software layer.</small></div>
   <nav><button onClick={()=>setTab("discover")}>Discover</button><button onClick={()=>setTab("provider")}>Provider</button></nav>
  </header>
  <section className="hero"><label>PROTOTYPE · SOFTWARE GATEWAY</label><h1>One identity. Multiple participating networks.</h1><p>Prototype the control plane first, then test the real gateway on an isolated lab network.</p></section>
  {tab==="discover"?<>
   <section className="grid">{hotspots.map(h=><article className="card" key={h.id}>
    <div className="meta">● {h.status}<span>{h.accessType}</span></div><h2>{h.name}</h2><p>{h.providerName}</p>
    <div className="stats"><div><b>{h.speedMbps} Mbps</b><small>advertised</small></div><div><b>{h.priceInr?`₹${h.priceInr}`:"Free"}</b><small>premium</small></div></div>
    <button onClick={()=>connect(h,"FREE")}>Connect Free</button><button className="light" onClick={()=>connect(h,"PREMIUM")}>Premium</button>
   </article>)}</section>
   {session&&<section className="session"><b>ACTIVE · {session.plan}</b><h2>{session.hotspotId}</h2><p>{session.speedMbps} Mbps · {session.usedMb}/{session.quotaMb} MB</p><button onClick={()=>action("usage",{mb:100})}>Simulate 100 MB</button><button className="light" onClick={()=>action("upgrade")}>Upgrade</button><button className="danger" onClick={()=>action("end")}>Disconnect</button></section>}
  </>:<section><h2>Provider dashboard</h2><div className="grid">{hotspots.map(h=><article className="card" key={h.id}><div className="meta">● {h.status}</div><h2>{h.name}</h2><p>Gateway: {h.gatewayId}</p><p>Provider: {h.providerName}</p></article>)}</div></section>}
 </main>
}
