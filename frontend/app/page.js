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
  const [session, setSession] = useState(null); const [client, setClient] = useState(null); const [pending, setPending] = useState({});
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [lastRefresh, setLastRefresh] = useState(null);
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
      setTelemetry(Object.fromEntries(entries)); setLastRefresh(new Date()); await loadClientIdentity();
    } catch (e) { setError(e.message); }
  }

  useEffect(() => { load(); const timer = setInterval(load, 10000); return () => clearInterval(timer); }, []);

  async function waitForActualState(gatewayId, ip, desired) {
    const started = Date.now();
    while (Date.now() - started < 4500) {
      try {
        const t = await json(`${API}/gateways/${encodeURIComponent(gatewayId)}/telemetry`);
        const c = (t?.clients || []).find(x => x.ipAddress === ip);
        if (c && c.authorized === desired) { setTelemetry(v => ({ ...v, [gatewayId]: t })); return c; }
      } catch {}
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    return null;
  }

  async function toggleClient(gatewayId, clientInfo) {
    const key = `${gatewayId}:${clientInfo.ipAddress}`;
    if (pending[key]) return;
    const allow = !clientInfo.authorized;
    setError(""); setMessage(""); setPending(v => ({ ...v, [key]: true }));
    try {
      await json(`${API}/gateways/${encodeURIComponent(gatewayId)}/commands`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: "0", type: allow ? "ALLOW_CLIENT" : "BLOCK_CLIENT", sessionId: null, value: clientInfo.ipAddress }) });
      const actual = await waitForActualState(gatewayId, clientInfo.ipAddress, allow);
      if (!actual) throw new Error(`Gateway did not confirm ${allow ? "ALLOW" : "BLOCK"} for ${clientInfo.ipAddress}.`);
      setMessage(actual.internetStatus === "FLOWING" ? `Internet is flowing for ${clientInfo.ipAddress}.` : allow ? `Internet access allowed for ${clientInfo.ipAddress}.` : `Internet blocked for ${clientInfo.ipAddress}.`);
      await load();
    } catch (e) { setError(e.message); }
    finally { setPending(v => { const next = { ...v }; delete next[key]; return next; }); }
  }

  async function connect(h, selectedClient = client) {
    setError("");
    try {
      const body = await json(`${API}/sessions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ userId: "PHONE-B-USER", hotspotId: h.id, clientIp: selectedClient?.clientIp || selectedClient?.ipAddress || null, clientMac: selectedClient?.macAddress || null }) });
      setSession(body); setMessage(body.clientIp ? `Authorization requested for ${body.clientIp}.` : `Session created for ${h.name}.`); await load();
    } catch (e) { setError(e.message); }
  }

  async function sessionAction(path) { if (!session) return; try { const next = await json(`${API}/sessions/${session.id}/${path}`, { method: "POST" }); setSession(next); setMessage(path === "end" ? "Client blocked again." : `Session ${path} completed.`); await load(); } catch (e) { setError(e.message); } }
  function update(setter) { return e => setter(v => ({ ...v, [e.target.name]: e.target.value })); }

  async function registerGateway(e) {
    e.preventDefault(); setError(""); setMessage("");
    try { const body = await json(`${API}/gateways/${encodeURIComponent(gatewayForm.gatewayId)}/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(gatewayForm) }); setGateway(body); setHotspotForm(v => ({ ...v, gatewayId: gatewayForm.gatewayId })); setMessage(`Gateway ${body.id} registered.`); await load(); }
    catch (x) { setError(x.message); }
  }

  function prepareEnrollment(h) {
    setHotspotForm(v => ({ ...v, ssid: h.ssid, bssid: h.bssid || "", gatewayId: h.gatewayId || gatewayForm.gatewayId }));
    setMessage(`Prepared ${h.ssid} for enrollment.`); setTab("provider");
  }

  async function enrollHotspot(e) {
    e.preventDefault(); setError(""); setMessage("");
    try {
      const payload = { ...hotspotForm, latitude: Number(hotspotForm.latitude || 0), longitude: Number(hotspotForm.longitude || 0), speedMbps: Number(hotspotForm.speedMbps || 0), priceInr: Number(hotspotForm.priceInr || 0) };
      const body = await json(`${API}/hotspots/enroll`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      setMessage(`Hotspot ${body.name} enrolled as ${body.id}.`); await load();
    } catch (x) { setError(x.message); }
  }

  const onlineGateways = gateways.filter(g => g.status === "ONLINE").length;
  const managedOnline = hotspots.filter(h => h.status === "ONLINE").length;
  const connectedClients = Object.values(telemetry).reduce((n, t) => n + (t?.clients?.length || 0), 0);
  const strongest = useMemo(() => [...observed].sort((a,b) => (b.signalPercent ?? -1) - (a.signalPercent ?? -1))[0], [observed]);

  return <main>
    <header><div><strong>NetworkStream</strong><small> software-controlled connectivity</small></div><nav><button className={tab === "discover" ? "active" : "light"} onClick={() => setTab("discover")}>Discover</button><button className={tab === "provider" ? "active" : "light"} onClick={() => setTab("provider")}>Gateway & Provider</button></nav></header>
    <section className="hero"><div className="eyebrow">{localMode ? "LOCAL GATEWAY MODE · PHONE B" : "NETWORKSTREAM CONTROL PLANE"}</div><h1>Discover first. Authorize second. Internet last.</h1><p>Phone B uses the laptop gateway. NetworkStream controls its Internet access while keeping the local portal reachable.</p><div className="flow"><span>Phone B</span><b>→</b><span>NetworkStream Gateway</span><b>→</b><span>Phone A</span><b>→</b><span>Internet</span></div></section>
    {error && <section className="banner error"><b>ERROR</b><span>{error}</span></section>}{message && <section className="banner success"><b>UPDATED</b><span>{message}</span></section>}
    <section className="overview"><article><small>Managed hotspots</small><b>{managedOnline}/{hotspots.length}</b><span>online</span></article><article><small>Gateways</small><b>{onlineGateways}/{gateways.length}</b><span>heartbeating</span></article><article><small>Downstream clients</small><b>{connectedClients}</b><span>observed</span></article><article><small>Best nearby signal</small><b>{strongest?.signalPercent != null ? `${strongest.signalPercent}%` : "—"}</b><span>{strongest?.ssid || "no scan"}</span></article></section>

    {tab === "discover" ? <>
      {localMode && <section className="local-card"><div><StatusPill good>LOCAL ACCESS</StatusPill><h2>This device is on the NetworkStream gateway</h2><p>The local portal remains reachable before Internet authorization.</p></div><div className="identity"><small>Detected client IP</small><b>{client?.clientIp || "detecting…"}</b><small>Gateway</small><b>192.168.137.1</b></div></section>}
      <section><div className="section-head"><div><h2>Available NetworkStream hotspots</h2><p>Only enrolled networks are eligible for authorization.</p></div><StatusPill good>{managedOnline} ONLINE</StatusPill></div><div className="grid">{hotspots.map(h => <article className="card" key={h.id}><div className="meta"><StatusPill good={h.status === "ONLINE"}>{h.status}</StatusPill><span>{h.accessType}</span></div><h2>{h.name}</h2><p>{h.providerName}</p><div className="stats"><div><b>{h.speedMbps} Mbps</b><small>advertised</small></div><div><b>{h.priceInr ? `₹${h.priceInr}` : "Free"}</b><small>price</small></div></div><button disabled={h.status !== "ONLINE"} onClick={() => connect(h)}>{client?.clientIp ? "Authorize this device" : "Connect session"}</button></article>)}</div>{hotspots.length === 0 && <article className="card"><p>No managed hotspots are enrolled yet. Use Gateway & Provider to enroll one.</p></article>}</section>
      <section><div className="section-head"><div><h2>Nearby Wi-Fi intelligence</h2><p>Real radio observations from gateways. An observation is not automatically a managed network.</p></div><span className="muted">refresh {lastRefresh?.toLocaleTimeString() || "—"}</span></div><div className="grid">{observed.length === 0 ? <article className="card"><p>No recent gateway scan.</p></article> : observed.map(h => <article className="card" key={h.bssid || `${h.gatewayId}-${h.ssid}`}><div className="meta"><StatusPill>RADIO</StatusPill><span>{h.security || "OPEN"}</span></div><h2>{h.ssid}</h2><p className="mono">{h.bssid || "BSSID unavailable"}</p><div className="stats"><div><Signal percent={h.signalPercent}/></div><div><b>{h.frequency || "—"}</b><small>frequency</small></div></div><small>Gateway {h.gatewayId} · {new Date(h.observedAt).toLocaleTimeString()}</small><button className="light" onClick={() => prepareEnrollment(h)}>Enroll this network</button></article>)}</div></section>
      {session && <section className="session"><div><StatusPill good={session.status === "ACTIVE"}>{session.status}</StatusPill><h2>Active session</h2><p>{session.hotspotId} · Gateway {session.gatewayId}</p></div><div className="session-grid"><div><small>Client</small><b>{session.clientIp || "not attached"}</b></div><div><small>Plan</small><b>{session.plan}</b></div><div><small>Usage</small><b>{session.usedMb}/{session.quotaMb} MB</b></div><div><small>Speed</small><b>{session.speedMbps} Mbps</b></div></div><button className="danger" onClick={() => sessionAction("end")}>Disconnect / block client</button></section>}
    </> : <section>
      <div className="section-head"><div><h2>Gateway control room</h2><p>Telemetry is authoritative for client policy and observed Internet flow.</p></div><StatusPill good>{onlineGateways} ONLINE</StatusPill></div>
      <div className="grid">
        <article className="card"><h2>Register gateway</h2><form onSubmit={registerGateway}><input name="gatewayId" value={gatewayForm.gatewayId} onChange={update(setGatewayForm)} placeholder="Gateway ID" required/><input name="hotspotId" value={gatewayForm.hotspotId} onChange={update(setGatewayForm)} placeholder="Managed hotspot ID (optional)"/><input name="version" value={gatewayForm.version} onChange={update(setGatewayForm)} placeholder="Agent version" required/><input name="hostname" value={gatewayForm.hostname} onChange={update(setGatewayForm)} placeholder="Hostname"/><button type="submit">Register gateway</button></form>{gateway && <p className="success-text">Registered: <b>{gateway.id}</b></p>}</article>
        <article className="card"><h2>Enroll hotspot</h2><form onSubmit={enrollHotspot}><input name="ssid" value={hotspotForm.ssid} onChange={update(setHotspotForm)} placeholder="SSID" required/><input name="bssid" value={hotspotForm.bssid} onChange={update(setHotspotForm)} placeholder="BSSID"/><input name="providerName" value={hotspotForm.providerName} onChange={update(setHotspotForm)} placeholder="Provider name"/><input name="gatewayId" value={hotspotForm.gatewayId} onChange={update(setHotspotForm)} placeholder="Gateway ID" required/><div className="two"><input name="latitude" value={hotspotForm.latitude} onChange={update(setHotspotForm)} placeholder="Latitude"/><input name="longitude" value={hotspotForm.longitude} onChange={update(setHotspotForm)} placeholder="Longitude"/></div><div className="two"><input name="speedMbps" value={hotspotForm.speedMbps} onChange={update(setHotspotForm)} placeholder="Speed Mbps" required/><input name="priceInr" value={hotspotForm.priceInr} onChange={update(setHotspotForm)} placeholder="Price INR" required/></div><button type="submit">Enroll hotspot</button></form></article>
      </div>
      <h2>Live gateway telemetry</h2>
      <div className="grid">{gateways.length === 0 ? <article className="card"><p>No gateways registered.</p></article> : gateways.map(g => { const t = telemetry[g.id]; return <article className="card" key={g.id}>
        <div className="meta"><StatusPill good={g.status === "ONLINE"}>{g.status}</StatusPill><span>{g.platform || "Windows"}</span></div><h2>{g.id}</h2><p>{g.hostname || "Hostname unavailable"} · Agent {g.version || "unknown"}</p>
        <div className="stats"><div><b>{t?.internetOnline === true ? "UPSTREAM ONLINE" : "UPSTREAM OFFLINE"}</b><small>gateway Internet</small></div><div><b>{t?.downstreamSsid || "Windows Mobile Hotspot"}</b><small>downstream Wi-Fi</small></div></div>
        {(t?.clients || []).map(c => { const key = `${g.id}:${c.ipAddress}`; const busy = !!pending[key]; const flow = c.internetStatus || (c.authorized ? "ALLOWED_NO_FLOW" : "BLOCKED"); const label = busy ? "Applying…" : c.authorized ? "Block Internet" : "Allow Internet"; return <div className="client-row" key={key}><div><b>Phone B</b><small>Wi-Fi: {c.ssid || t?.downstreamSsid || "Windows Mobile Hotspot"}</small><small>IP: {c.ipAddress} · MAC: {c.macAddress}</small><small>Policy: {c.authorized ? "ALLOWED" : "BLOCKED"} · Internet: {flow.replaceAll("_", " ")}{c.activeNatSessions ? ` · ${c.activeNatSessions} NAT session${c.activeNatSessions === 1 ? "" : "s"}` : ""}</small></div><button disabled={busy} className={c.authorized ? "danger" : ""} onClick={() => toggleClient(g.id, c)}>{label}</button></div>; })}
        {(t?.clients || []).length === 0 && <p>No downstream clients currently observed.</p>}
      </article>; })}</div>
    </section>}
    <footer><span>NetworkStream prototype · gateway telemetry refreshes every 10 seconds</span><span>Last refresh {lastRefresh?.toLocaleTimeString() || "—"}</span></footer>
  </main>;
}
