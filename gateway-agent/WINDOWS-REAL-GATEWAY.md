# Real Windows gateway test

This is the first real-hardware NetworkStream experiment for a Windows laptop plus two phones.

## Topology

```text
Phone A hotspot (uplink / Internet)
          |
          v
   Windows laptop
   NetworkStream gateway
          |
          +---- Windows Wi-Fi radio scans nearby APs
          |
          v
   NetworkStream API + PostgreSQL

Phone B is the optional test client. It is NOT automatically a downstream
NetworkStream client just because the laptop is connected to Phone A.
```

## 1. Start backend

```powershell
docker compose up -d --build
docker compose ps
curl http://localhost:8080/api/hotspots
```

## 2. Verify real Windows Wi-Fi discovery

```powershell
netsh wlan show networks mode=bssid
```

This output is from the Windows Wi-Fi adapter, not from mock hotspot records.

## 3. Run the NetworkStream Windows gateway

From the repository root:

```powershell
python .\gateway-agent\networkstream-windows-agent.py `
  --api http://localhost:8080 `
  --gateway-id WIN-LAPTOP-01 `
  --scan `
  --once
```

The agent registers the laptop, sends a heartbeat, scans nearby Wi-Fi, posts
`POST /api/gateways/WIN-LAPTOP-01/scan`, and reads policy/commands.

## 4. Inspect the observed networks

```powershell
curl "http://localhost:8080/api/hotspots/observed?seconds=300"
```

You should see real SSIDs/BSSIDs observed by `WIN-LAPTOP-01`.

## 5. Keep the gateway online

```powershell
python .\gateway-agent\networkstream-windows-agent.py `
  --api http://localhost:8080 `
  --gateway-id WIN-LAPTOP-01 `
  --scan `
  --interval 15
```

## Important enrollment rule

A discovered SSID is **observed**, not automatically a NetworkStream hotspot.

For a network to become a managed NetworkStream hotspot, the provider must
explicitly authorize it and a gateway must actually provide the downstream
access path. A phone hotspot used as the laptop's Internet uplink is therefore
an **uplink dependency**, not automatically a NetworkStream provider hotspot.

## Current hardware limitation

With one Windows Wi-Fi adapter, the laptop can connect to Phone A and observe
Wi-Fi, but it cannot safely be treated as a full NetworkStream AP/forwarding
gateway for Phone B by this agent. The agent deliberately does not modify
Windows routing, firewall, or Internet Connection Sharing.

The Linux agent remains the isolated-lab dataplane path for two-interface
forwarding/NAT experiments.
