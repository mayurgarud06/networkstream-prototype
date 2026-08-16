"use client";

import { useEffect, useMemo, useState } from "react";

const API = "/api";
const emptyGateway = { gatewayId: "WIN-LAPTOP-01", hotspotId: "", version: "0.7.0-windows-agent", hostname: "", platform: "Windows" };
const emptyHotspot = { ssid: "", bssid: "", providerName: "", latitude: "", longitude: "", accessType: "FREE", speedMbps: "20", priceInr: "0", gatewayId: "WIN-LAPTOP-01" };

function StatusPill({ children, good = false }) { return <span className={`pill ${good ? "good" : ""}`}>{children}</span>; }
function Signal({ percent }) { return percent == null ? <><b>—</b><small>signal unavailable</small></> : <><b>{percent}%</b><small>Wi-Fi signal</small><progress max="100" value={percent} /></>; }
function uniqueObserved(items) { const seen = new Map(); for (const item of items) { const key = (item.bssid || `${item.gatewayId}:${item.ssid}`).toLowerCase(); const old = seen.get(key); if (!old || new Date(item.observedAt) > new Date(old.observedAt)) seen.set(key, item); } return [...seen.values()]; }

export default function Home() {
  const [tab, setTab] = useState("discover");
  const [hotspots, setHotspots] = useState([]); const [observed, setObserved] = useState([]); const [gateways, setGateways] = useState([]); const [telemetry, setTelemetry] = useState({});
  const [session, setSession] = useState(null); const [client, setClient] = useState(null); const [clientState, setClientState] = useState({});
  const [pending, setPending] = useState({}); const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [lastRefresh, setLastRefresh] = useState(null);
  const [gatewayForm, setGatewayForm] = useState(emptyGateway); const [gateway, setGateway] = useState(null); const [hotspotForm, setHotspotForm] = useState(emptyHotspot);
  const localMode = typeof window !== "undefined" && window.location.hostname.startsWith("192.168.137.");

  async function json(url, options) { const response = await fetch(url, options); const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.message || `Request failed (${response.status})`); return body; }

  async function loadClientIdentity() {
    if (typeof window === "undefined" || !/^192\.168\.137\./.test(window.location.hostname)) return;
    try { const response = await fetch(`http://${window.location.hostname}:8081/client`, { cache: "no-store" }); if (response.ok) setClient(await response.json()); } catch {}
  }

  async function load() {
    try {
      const [managed, nearby, registered] = await Promise.all([json(`${API}/hotspots`), json(`${API}/hotspots/observed?seconds=180`), json(`${API}/gateways`)]);
      setHotspots(managed); setObserved(uniqueObserved(nearby)); setGateways(registered);
      const entries = await Promise.all(registered.map(async g => { try { return [g.id, await json(`${API}/gateways/${encodeURIComponent(g.id)}/telemetry`)]; } catch { return [g.id, null]; } }));
      const nextTelemetry = Object.fromEntries(entries); setTelemetry(nextTelemetry); setLastRefresh(new Date()); await loadClientIdentity();
      for (const [id, t] of entries) { if (t?.clients) for (const c of t.clients) setClientState(s => ({ ...s, [`${id}:${c.ipAddress}`]: !!c.authorized })); }
    } catch (e) { setError(e.message); }
  }

  useEffect(() => { load(); const timer = setInterval(load, 1000); return () => clearInterval(timer); }, []);

  async function waitForCommand(gatewayId, commandId, desired) {
    const started = Date.now();
    while (Date.now() - started < 3000) {
      const commands = await json(`${API}/gateways/${encodeURIComponent(gatewayId)}/commands`);
      if (!commands.some(c => String(c.id) === String(commandId))) { setClientState(s => ({ ...s, [`${gatewayId}:${desired.ipAddress}`]: desired.allow })); return true; }
      await new Promise(r => setTimeout(r, 200));
    }
    return false;
  }

  async function toggleClient(gatewayId, c) {
    const key = `${gatewayId}:${c.ipAddress}`; const allow = !clientState[key]; if (pending[key]) return;
    setError(""); setPending(p => ({ ...p, [key]: true })); setClientState(s => ({ ...s, [key]: allow }));
    try {
      const command = await json(`${API}/gateways/${encodeURIComponent(gatewayId)}/commands`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: "0", type: allow ? "ALLOW_CLIENT" : "BLOCK_CLIENT", sessionId: null, value: c.ipAddress }) });
      const applied = command?.id != null ? await waitForCommand(gatewayId, command.id, { ipAddress: c.ipAddress, allow }) : true;
      if (applied) setMessage(`${allow ? "Internet allowed" : "Internet blocked"} for ${c.ipAddress}.`); else { setClientState(s => ({ ...s, [key]: !allow })); setError("Gateway did not acknowledge the command within 3 seconds."); }
    } catch (e) { setClientState(s => ({ ...s, [key]: !allow })); setError(e.message); }
    finally { setPending(p => { const next = { ...p }; delete next[key]; return next; }); }
  }

  async function connect(h, selectedClient = client) { try { const body = await json(`${API}/sessions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ userId: "PHONE-B-USER", hotspotId: h.id, clientIp: selectedClient?.clientIp || null, clientMac: selectedClient?.macAddress || null }) }); setSession(body); setMessage(body.clientIp ? `Authorization requested for ${body.clientIp}.` : `Session created for ${h.name}.`); } catch (e) { setError(e.message); } }
  async function sessionAction(path) { if (!session) return; try { const next = await json(`${API}/sessions/${session.id}/${path}`, { method: "POST" }); setSession(next); setMessage(path === "end" ? "Client blocked again." : `Session ${path} completed.`); await load(); } catch (e) { setError(e.message); } }
  function update(setter) { return e => setter(v => ({ ...v, [e.target.name]: e.target.value })); }
  async function registerGateway(e) { e.preventDefault(); try { const body = await json(`${API}/gateways/${encodeURIComponent(gatewayForm.gatewayId)}/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(gatewayForm) }); setGateway(body); setHotspotForm(v => ({ ...v, gatewayId: gatewayForm.gatewayId })); setMessage(`Gateway ${body.id} registered.`); await load(); } catch (x) { setError(x.message); } }
  async function enrollHotspot(e) { e.preventDefault(); try { const payload = { ...hotspotForm, latitude: Number(hotspotForm.latitude || 0), longitude: Number(hotspotForm.longitude || 0), speedMbps: Number(hotspotForm.speedMbps || 0), priceInr: Number(hotspotForm.priceInr || 0) }; const body = await json(`${API}/hotspots/enroll`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); setMessage(`Hotspot ${body.name} enrolled.`); await load(); } catch (x) { setError(x.message); } }
  function prepareEnrollment(h) { setHotspotForm(v => ({ ...v, ssid: h.ssid, bssid: h.bssid || "", gatewayId: h.gatewayId || gatewayForm.gatewayId })); setTab("provider"); setMessage(`Prepared ${h.ssid} for enrollment.`); }

  const onlineGateways = gateways.filter(g => g.status === "ONLINE").length; const managedOnline = hotspots.filter(h => h.status === "ONLINE").length; const connectedClients = Object.values(telemetry).reduce((n, t) => n + (t?.clients?.length || 0), 0);
  const strongest = useMemo(() => [...observed].sort((a,b) => (b.signalPercent ?? -1) - (a.signalPercent ?? -1))[0], [observed]);

  return <main>
    <header><div><strong>NetworkStream</strong><small> software-controlled connectivity</small></div><nav><button className={tab === "discover" ? "active" : "light"} onClick={() => setTab("discover")}>Discover</button><button className={tab === "provider" ? "active" : "light"} onClick={() => setTab("provider")}>Gateway & Provider</button></nav></header>
    <section className="hero"><div className="eyebrow">{localMode ? "LOCAL GATEWAY MODE · PHONE B" : "NETWORKSTREAM CONTROL PLANE"}</div><h1>Discover first. Authorize second. Internet last.</h1><p>Phone B uses the laptop gateway. NetworkStream controls its Internet access while keeping the local portal reachable.</p><div className="flow"><span>Phone B</span><b>→</b><span>NetworkStream Gateway</span><b>→</b><span>Phone A</span><b>→</b><span>Internet</span></div></section>
    {error && <section className="banner error"><b>ERROR</b><span>{error}</span></section>}{message && <section className="banner success"><b>UPDATED</b><span>{message}</span></section>}
    <section className="overview"><article><small>Managed hotspots</small><b>{managedOnline}/{hotspots.length}</b><span>online</span></article><article><small>Gateways</small><b>{onlineGateways}/{gateways.length}</b><span>heartbeating</span></article><article><small>Downstream clients</small><b>{connectedClients}</b><span>observed</span></article><article><small>Best nearby signal</small><b>{strongest?.signalPercent != null ? `${strongest.signalPercent}%` : "—"}</b><span>{strongest?.ssid || "no scan"}</span></article></section>

    {tab === "discover" ? <>
      {localMode && <section className="local-card"><div><StatusPill good>LOCAL ACCESS</StatusPill><h2>This device is on the NetworkStream gateway</h2><p>The local portal remains reachable before Internet authorization.</p></div><div className="identity"><small>Detected client IP</small><b>{client?.clientIp || "detecting…"}</b><small>Gateway</small><b>192.168.137.1</b></div></section>}
      <section><div className="section-head"><div><h2>Available NetworkStream hotspots</h2><p>Only enrolled networks are eligible for authorization.</p></div><StatusPill good>{managedOnline} ONLINE</StatusPill></div><div className="grid">{hotspots.map(h => <article className="card" key={h.id}><div className="meta"><StatusPill good={h.status === "ONLINE"}>{h.status}</StatusPill><span>{h.accessType}</span></div><h2>{h.name}</h2><p>{h.providerName}</p><div className="stats"><div><b>{h.speedMbps} Mbps</b><small>advertised</small></div><div><b>{h.priceInr ? `₹${h.priceInr}` : "Free"}</b><small>price</small></div></div><button disabled={h.status !== "ONLINE"} onClick={() => connect(h)}>{client?.clientIp ? "Authorize this device" : "Connect session"}</button></article>)}</div>{hotspots.length === 0 && <article className="card"><p>No managed hotspots are enrolled yet.</p></article>}</section>
      <section><div className="section-head"><div><h2>Nearby Wi-Fi intelligence</h2><p>Real radio observations from gateways; observations are not automatically managed networks.</p></div><span className="muted">refresh {lastRefresh?.toLocaleTimeString() || "—"}</span></div><div className="grid">{observed.length === 0 ? <article className="card"><p>No recent gateway scan.</p></article> : observed.map(h => <article className="card" key={h.bssid || `${h.gatewayId}-${h.ssid}`}><div className="meta"><StatusPill>RADIO</StatusPill><span>{h.security || "OPEN"}</span></div><h2>{h.ssid}</h2><p className="mono">{h.bssid || "BSSID unavailable"}</p><div className="stats"><div><Signal percent={h.signalPercent}/></div><div><b>{h.frequency || "—"}</b><small>frequency</small></div></div><small>Gateway {h.gatewayId} · {new Date(h.observedAt).toLocaleTimeString()}</small><button className="light" onClick={() => prepareEnrollment(h)}>Enroll this network</button></article>)}</div></section>
      {session && <section className="session"><div><StatusPill good={session.status === "ACTIVE"}>{session.status}</StatusPill><h2>Active session</h2><p>{session.hotspotId} · Gateway {session.gatewayId}</p></div><div className="session-grid"><div><small>Client</small><b>{session.clientIp || "not attached"}</b></div><div><small>Plan</small><b>{session.plan}</b></div><div><small>Usage</small><b>{session.usedMb}/{session.quotaMb} MB</b></div><div><small>Speed</small><b>{session.speedMbps} Mbps</b></div></div><button className="danger" onClick={() => sessionAction("end")}>Disconnect / block client</button></section>}
    </> : <section>
      <div className="section-head"><div><h2>Gateway control room</h2><p>Real downstream client control. One button toggles Internet access.</p></div><StatusPill good>{onlineGateways} ONLINE</StatusPill></div>
      <div className="grid"><article className="card"><h2>Register gateway</h2><form onSubmit={registerGateway}><input name="gatewayId" value={gatewayForm.gatewayId} onChange={update(setGatewayForm)} placeholder="Gateway ID" required/><input name="hotspotId" value={gatewayForm.hotspotId} onChange={update(setGatewayForm)} placeholder="Managed hotspot ID (optional)"/><input name="version" value={gatewayForm.version} onChange={update(setGatewayForm)} placeholder="Agent version" required/><input name="hostname" value={gatewayForm.hostname} onChange={update(setGatewayForm)} placeholder="Hostname"/><button type="submit">Register gateway</button></form>{gateway && <p className="success-text">Registered: <b>{gateway.id}</b></p>}</article>
        <article className="card"><h2>Enroll hotspot</h2><form onSubmit={enrollHotspot}><input name="ssid" value={hotspotForm.ssid} onChange={update(setHotspotForm)} placeholder="SSID" required/><input name="bssid" value={hotspotForm.bssid} onChange={update(setHotspotForm)} placeholder="BSSID"/><input name="providerName" value={hotspotForm.providerName} onChange={update(setHotspotForm)} placeholder="Provider name"/><input name="gatewayId" value={hotspotForm.gatewayId} onChange={update(setHotspotForm)} placeholder="Gateway ID" required/><div className="two"><input name="latitude" value={hotspotForm.latitude} onChange={update(setHotspotForm)} placeholder="Latitude"/><input name="longitude" value={hotspotForm.longitude} onChange={update(setHotspotForm)} placeholder="Longitude"/></div><div className="two"><input name="speedMbps" value={hotspotForm.speedMbps} onChange={update(setHotspotForm)} placeholder="Speed Mbps" required/><input name="priceInr" value={hotspotForm.priceInr} onChange={update(setHotspotForm)} placeholder="Price INR" required/></div><button type="submit">Enroll hotspot</button></form></article></div>
      <h2>Live gateway telemetry</h2><div className="grid">{gateways.length === 0 ? <article className="card"><p>No gateways registered.</p></article> : gateways.map(g => { const t = telemetry[g.id]; return <article className="card" key={g.id}><div className="meta"><StatusPill good={g.status === "ONLINE"}>{g.status}</StatusPill><span>{g.platform || "Windows"}</span></div><h2>{g.id}</h2><p>{g.hostname || "Hostname unavailable"} · Agent {g.version || "unknown"}</p><div className="stats"><div><b>{t?.internetOnline === true ? "ONLINE" : t?.internetOnline === false ? "OFFLINE" : "UNKNOWN"}</b><small>upstream Internet</small></div><div><b>{t?.clients?.length ?? 0}</b><small>downstream clients</small></div></div><p>Wi-Fi: <b>{t?.downstreamSsid || "Windows Mobile Hotspot"}</b> · Gateway IP: <b>{t?.downstreamAddress || "192.168.137.1"}</b></p>{t?.clients?.length ? t.clients.map(c => { const key = `${g.id}:${c.ipAddress}`; const allowed = clientState[key] ?? !!c.authorized; return <div className="client-row" key={c.ipAddress}><div><b>Phone B</b><small>Wi-Fi: {t?.downstreamSsid || "Windows Mobile Hotspot"} · IP: {c.ipAddress} · MAC: {c.macAddress || "unavailable"}</small><StatusPill good={allowed}>{pending[key] ? "APPLYING…" : allowed ? "INTERNET ALLOWED" : "INTERNET BLOCKED"}</StatusPill></div><button disabled={!!pending[key]} className={allowed ? "danger" : ""} onClick={() => toggleClient(g.id, c)}>{pending[key] ? "Applying…" : allowed ? "Block Internet" : "Allow Internet"}</button></div>; }) : <p>No downstream clients detected. Connect Phone B to the Windows Mobile Hotspot.</p>}</article>; })}</div>
    </section>}
    <footer><span>NetworkStream prototype · real gateway control</span><span>New clients are blocked by default.</span></footer>
  </main>;
}
