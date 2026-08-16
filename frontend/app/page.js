"use client";

import { useEffect, useMemo, useState } from "react";

const API = "/api";
const DEFAULT_SPEED = 20;

function Pill({ children, good = false }) {
  return <span className={`pill ${good ? "good" : ""}`}>{children}</span>;
}

function Signal({ percent }) {
  if (percent == null) return <><b>—</b><small>signal unavailable</small></>;
  return <><b>{percent}%</b><small>Wi-Fi signal</small><progress max="100" value={percent} /></>;
}

function unique(items) {
  const seen = new Map();
  for (const item of items) {
    const key = (item.bssid || `${item.gatewayId}:${item.ssid}`).toLowerCase();
    const old = seen.get(key);
    if (!old || new Date(item.observedAt) > new Date(old.observedAt)) seen.set(key, item);
  }
  return [...seen.values()];
}

export default function Home() {
  const [tab, setTab] = useState("discover");
  const [hotspots, setHotspots] = useState([]);
  const [observed, setObserved] = useState([]);
  const [gateways, setGateways] = useState([]);
  const [telemetry, setTelemetry] = useState({});
  const [client, setClient] = useState(null);
  const [pending, setPending] = useState({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);
  const [gatewayForm, setGatewayForm] = useState({ gatewayId: "WIN-LAPTOP-01", hotspotId: "", version: "0.7.0-windows-agent", hostname: "", platform: "Windows" });
  const [hotspotForm, setHotspotForm] = useState({ ssid: "", bssid: "", providerName: "NetworkStream", latitude: "0", longitude: "0", accessType: "FREE", speedMbps: String(DEFAULT_SPEED), priceInr: "0", gatewayId: "" });

  const localMode = typeof window !== "undefined" && window.location.hostname.startsWith("192.168.137.");

  async function json(url, options) {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.message || `Request failed (${response.status})`);
    return body;
  }

  async function loadIdentity() {
    if (typeof window === "undefined" || !/^192\.168\.137\./.test(window.location.hostname)) return;
    try {
      const response = await fetch(`http://${window.location.hostname}:8081/client`, { cache: "no-store" });
      if (response.ok) setClient(await response.json());
    } catch { /* cloud/public mode has no local gateway identity endpoint */ }
  }

  async function load() {
    try {
      const [managed, nearby, registered] = await Promise.all([
        json(`${API}/hotspots`),
        json(`${API}/hotspots/observed?seconds=180`),
        json(`${API}/gateways`),
      ]);
      setHotspots(managed);
      setObserved(unique(nearby));
      setGateways(registered);
      const entries = await Promise.all(registered.map(async gateway => {
        try {
          return [gateway.id, await json(`${API}/gateways/${encodeURIComponent(gateway.id)}/telemetry`)];
        } catch {
          return [gateway.id, null];
        }
      }));
      setTelemetry(Object.fromEntries(entries));
      setLastRefresh(new Date());
      await loadIdentity();
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  function currentNetworkFor(gatewayId) {
    return telemetry[gatewayId]?.upstreamSsid || null;
  }

  function currentObserved(gatewayId, ssid) {
    return observed.find(item => item.gatewayId === gatewayId && item.ssid === ssid) || null;
  }

  function enrolledNetwork(gatewayId, ssid) {
    return hotspots.find(item => item.gatewayId === gatewayId && item.name === ssid) || null;
  }

  async function enrollCurrentNetwork(gatewayId) {
    const ssid = currentNetworkFor(gatewayId);
    const observation = currentObserved(gatewayId, ssid);
    if (!ssid) {
      setError("The gateway has not reported its current upstream Wi-Fi network yet.");
      return;
    }
    if (enrolledNetwork(gatewayId, ssid)) {
      setMessage(`${ssid} is already enrolled and connected.`);
      return;
    }
    const key = `enroll:${gatewayId}`;
    if (pending[key]) return;
    setPending(v => ({ ...v, [key]: true }));
    setError("");
    setMessage("");
    try {
      const body = await json(`${API}/hotspots/enroll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ssid,
          bssid: observation?.bssid || "",
          providerName: "NetworkStream",
          latitude: 0,
          longitude: 0,
          accessType: "FREE",
          speedMbps: DEFAULT_SPEED,
          priceInr: 0,
          gatewayId,
        }),
      });
      setMessage(`Connected network ${body.name} is now enrolled in NetworkStream.`);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(v => { const next = { ...v }; delete next[key]; return next; });
    }
  }

  async function toggleClient(gatewayId, c) {
    const key = `${gatewayId}:${c.ipAddress}`;
    if (pending[key]) return;
    const allow = !c.authorized;
    setPending(v => ({ ...v, [key]: true }));
    setError("");
    setMessage("");
    try {
      await json(`${API}/gateways/${encodeURIComponent(gatewayId)}/commands`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: "0", type: allow ? "ALLOW_CLIENT" : "BLOCK_CLIENT", sessionId: null, value: c.ipAddress }),
      });
      setMessage(`${allow ? "Allow" : "Block"} requested for ${c.ipAddress}. Waiting for gateway telemetry.`);
      // The gateway keeps its normal 15-second communication cadence. Do not
      // create a high-frequency API polling loop here; the next telemetry
      // refresh is authoritative.
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(v => { const next = { ...v }; delete next[key]; return next; });
    }
  }

  async function registerGateway(event) {
    event.preventDefault();
    setError("");
    try {
      const body = await json(`${API}/gateways/${encodeURIComponent(gatewayForm.gatewayId)}/register`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(gatewayForm),
      });
      setHotspotForm(v => ({ ...v, gatewayId: gatewayForm.gatewayId }));
      setMessage(`Gateway ${body.id} registered.`);
      await load();
    } catch (e) { setError(e.message); }
  }

  async function enrollFromForm(event) {
    event.preventDefault();
    setError("");
    try {
      const body = await json(`${API}/hotspots/enroll`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...hotspotForm,
          latitude: Number(hotspotForm.latitude || 0),
          longitude: Number(hotspotForm.longitude || 0),
          speedMbps: Number(hotspotForm.speedMbps || DEFAULT_SPEED),
          priceInr: Number(hotspotForm.priceInr || 0),
        }),
      });
      setMessage(`Hotspot ${body.name} enrolled as ${body.id}.`);
      await load();
    } catch (e) { setError(e.message); }
  }

  function update(setter) {
    return event => setter(value => ({ ...value, [event.target.name]: event.target.value }));
  }

  const onlineGateways = gateways.filter(g => g.status === "ONLINE").length;
  const managedOnline = hotspots.filter(h => h.status === "ONLINE").length;
  const connectedClients = Object.values(telemetry).reduce((sum, t) => sum + (t?.clients?.length || 0), 0);
  const strongest = useMemo(() => [...observed].sort((a, b) => (b.signalPercent ?? -1) - (a.signalPercent ?? -1))[0], [observed]);
  const currentGateway = gateways.find(g => telemetry[g.id]?.upstreamSsid);
  const currentSsid = currentGateway ? currentNetworkFor(currentGateway.id) : null;
  const currentHotspot = currentGateway && currentSsid ? enrolledNetwork(currentGateway.id, currentSsid) : null;

  return (
    <main>
      <header>
        <div><strong>NetworkStream</strong><small> software-controlled connectivity</small></div>
        <nav>
          <button className={tab === "discover" ? "active" : "light"} onClick={() => setTab("discover")}>Discover</button>
          <button className={tab === "provider" ? "active" : "light"} onClick={() => setTab("provider")}>Gateway & Provider</button>
        </nav>
      </header>

      <section className="hero">
        <div className="eyebrow">{localMode ? "LOCAL GATEWAY MODE · PHONE B" : "NETWORKSTREAM CONTROL PLANE"}</div>
        <h1>Discover. Enroll. Control Internet access.</h1>
        <p>The laptop's real upstream Wi-Fi is discovered by the gateway. Enroll that connected network once, then downstream clients are discovered and can be allowed or blocked from Internet access.</p>
        <div className="flow"><span>Upstream Wi-Fi</span><b>→</b><span>Laptop Gateway</span><b>→</b><span>Phone B</span><b>→</b><span>Internet</span></div>
      </section>

      {error && <section className="banner error"><b>ERROR</b><span>{error}</span></section>}
      {message && <section className="banner success"><b>UPDATED</b><span>{message}</span></section>}

      <section className="overview">
        <article><small>Managed networks</small><b>{managedOnline}/{hotspots.length}</b><span>online</span></article>
        <article><small>Gateways</small><b>{onlineGateways}/{gateways.length}</b><span>online</span></article>
        <article><small>Downstream clients</small><b>{connectedClients}</b><span>observed</span></article>
        <article><small>Best nearby signal</small><b>{strongest?.signalPercent != null ? `${strongest.signalPercent}%` : "—"}</b><span>{strongest?.ssid || "no scan"}</span></article>
      </section>

      {tab === "discover" ? <>
        {localMode && <section className="local-card">
          <div><Pill good>LOCAL ACCESS</Pill><h2>This device is on the NetworkStream gateway</h2><p>The local NetworkStream portal remains reachable while Internet access is controlled.</p></div>
          <div className="identity"><small>Detected client IP</small><b>{client?.clientIp || "detecting…"}</b><small>Gateway</small><b>192.168.137.1</b></div>
        </section>}

        <section>
          <div className="section-head"><div><h2>Current upstream network</h2><p>This is the Wi-Fi network the laptop gateway is actually connected to.</p></div><Pill good={!!currentGateway}>{currentGateway ? "CONNECTED" : "WAITING"}</Pill></div>
          {currentGateway && currentSsid ? <article className="card">
            <div className="meta"><Pill good>CONNECTED</Pill>{currentHotspot ? <Pill good>ENROLLED</Pill> : <Pill>NOT ENROLLED</Pill>}</div>
            <h2>📶 {currentSsid}</h2>
            <p>Gateway {currentGateway.id} · Internet {telemetry[currentGateway.id]?.internetOnline ? "online" : "offline"}</p>
            <div className="stats">
              <div><b>{currentHotspot ? "NetworkStream active" : "NetworkStream not active"}</b><small>management state</small></div>
              <div><b>{telemetry[currentGateway.id]?.downstreamSsid || "Windows Mobile Hotspot"}</b><small>downstream hotspot</small></div>
            </div>
            {!currentHotspot && <button disabled={!!pending[`enroll:${currentGateway.id}`]} onClick={() => enrollCurrentNetwork(currentGateway.id)}>{pending[`enroll:${currentGateway.id}`] ? "Enrolling…" : "Enroll this network"}</button>}
            {currentHotspot && <p className="success-text">✓ This connected network is already part of NetworkStream.</p>}
          </article> : <article className="card"><p>Waiting for a gateway to report its current upstream Wi-Fi connection. Start the Windows gateway agent while the laptop is connected to the Internet.</p></article>}
        </section>

        <section>
          <div className="section-head"><div><h2>Downstream clients</h2><p>Devices connected to the laptop's Mobile Hotspot. New clients are blocked until NetworkStream allows them.</p></div><Pill>{connectedClients} CLIENTS</Pill></div>
          <div className="grid">
            {gateways.flatMap(g => (telemetry[g.id]?.clients || []).map(c => ({ gateway: g, telemetry: telemetry[g.id], client: c }))).map(({ gateway, telemetry: t, client: c }) => {
              const key = `${gateway.id}:${c.ipAddress}`;
              const busy = !!pending[key];
              const state = c.internetStatus || (c.authorized ? "ALLOWED_NO_FLOW" : "BLOCKED");
              return <article className="card" key={key}>
                <div className="meta"><Pill good={c.authorized}>{c.authorized ? "ALLOWED" : "BLOCKED"}</Pill><span>{state.replaceAll("_", " ")}</span></div>
                <h2>📱 Phone B</h2>
                <p>Wi-Fi: {c.ssid || t?.downstreamSsid || "Windows Mobile Hotspot"}</p>
                <div className="stats"><div><b>{c.ipAddress}</b><small>IP address</small></div><div><b>{c.macAddress}</b><small>MAC address</small></div></div>
                <p>Internet: <strong>{state.replaceAll("_", " ")}</strong>{c.activeNatSessions ? ` · ${c.activeNatSessions} active flow(s)` : ""}</p>
                <button disabled={busy || !currentHotspot} className={c.authorized ? "danger" : ""} onClick={() => toggleClient(gateway.id, c)}>{busy ? "Applying…" : c.authorized ? "Block Internet" : "Allow Internet"}</button>
                {!currentHotspot && <small>Enroll the laptop's connected upstream network before controlling downstream Internet access.</small>}
              </article>;
            })}
            {connectedClients === 0 && <article className="card"><p>No downstream client is currently observed. Connect Phone B to the laptop's Mobile Hotspot and wait for the next gateway telemetry cycle.</p></article>}
          </div>
        </section>

        <section>
          <div className="section-head"><div><h2>Nearby Wi-Fi discovery</h2><p>Radio observations are discovery data. Only the network currently connected to the laptop can be enrolled from this screen.</p></div><span className="muted">refresh {lastRefresh?.toLocaleTimeString() || "—"}</span></div>
          <div className="grid">
            {observed.length === 0 ? <article className="card"><p>No recent gateway scan.</p></article> : observed.map(h => {
              const connected = currentNetworkFor(h.gatewayId) === h.ssid;
              const enrolled = !!enrolledNetwork(h.gatewayId, h.ssid);
              return <article className="card" key={h.bssid || `${h.gatewayId}-${h.ssid}`}>
                <div className="meta"><Pill good={connected}>{connected ? "CONNECTED" : "DISCOVERED"}</Pill>{enrolled && <Pill good>ENROLLED</Pill>}</div>
                <h2>{h.ssid}</h2><p className="mono">{h.bssid || "BSSID unavailable"}</p>
                <div className="stats"><div><Signal percent={h.signalPercent} /></div><div><b>{h.frequency || "—"}</b><small>frequency</small></div></div>
                {connected && !enrolled ? <button className="light" disabled={!!pending[`enroll:${h.gatewayId}`]} onClick={() => enrollCurrentNetwork(h.gatewayId)}>{pending[`enroll:${h.gatewayId}`] ? "Enrolling…" : "Enroll this network"}</button> : connected && enrolled ? <p className="success-text">✓ Connected and enrolled</p> : <small>This network is not the laptop gateway's current upstream connection.</small>}
              </article>;
            })}
          </div>
        </section>
      </> : <section>
        <div className="section-head"><div><h2>Gateway & Provider</h2><p>Register the Windows edge and use this page for manual enrollment when needed.</p></div><Pill good={onlineGateways > 0}>{onlineGateways} ONLINE</Pill></div>
        <div className="grid">
          <article className="card"><h2>Register gateway</h2><form onSubmit={registerGateway}>
            <input name="gatewayId" value={gatewayForm.gatewayId} onChange={update(setGatewayForm)} placeholder="Gateway ID" required />
            <input name="hotspotId" value={gatewayForm.hotspotId} onChange={update(setGatewayForm)} placeholder="Managed hotspot ID (optional)" />
            <input name="version" value={gatewayForm.version} onChange={update(setGatewayForm)} placeholder="Agent version" required />
            <input name="hostname" value={gatewayForm.hostname} onChange={update(setGatewayForm)} placeholder="Hostname" />
            <button type="submit">Register gateway</button>
          </form></article>
          <article className="card"><h2>Enroll hotspot manually</h2><form onSubmit={enrollFromForm}>
            <input name="ssid" value={hotspotForm.ssid} onChange={update(setHotspotForm)} placeholder="SSID" required />
            <input name="bssid" value={hotspotForm.bssid} onChange={update(setHotspotForm)} placeholder="BSSID" />
            <input name="providerName" value={hotspotForm.providerName} onChange={update(setHotspotForm)} placeholder="Provider name" />
            <input name="gatewayId" value={hotspotForm.gatewayId} onChange={update(setHotspotForm)} placeholder="Gateway ID" required />
            <input name="speedMbps" value={hotspotForm.speedMbps} onChange={update(setHotspotForm)} placeholder="Speed Mbps" required />
            <input name="priceInr" value={hotspotForm.priceInr} onChange={update(setHotspotForm)} placeholder="Price INR" required />
            <button type="submit">Enroll hotspot</button>
          </form></article>
        </div>
        <h2>Live gateway telemetry</h2>
        <div className="grid">{gateways.map(g => {
          const t = telemetry[g.id];
          return <article className="card" key={g.id}><div className="meta"><Pill good={g.status === "ONLINE"}>{g.status}</Pill><span>{g.platform || "Windows"}</span></div><h2>{g.id}</h2><p>{g.hostname || "Hostname unavailable"}</p><p>Upstream: {t?.upstreamSsid || "not reported"}</p><p>Downstream: {t?.downstreamSsid || "Windows Mobile Hotspot"}</p><p>Internet: {t?.internetOnline ? "ONLINE" : "OFFLINE"}</p></article>;
        })}</div>
      </section>}

      <footer><span>Gateway telemetry refreshes every 10 seconds</span><span>Normal gateway API cadence remains 15 seconds</span><span>Last refresh {lastRefresh?.toLocaleTimeString() || "—"}</span></footer>
    </main>
  );
}
