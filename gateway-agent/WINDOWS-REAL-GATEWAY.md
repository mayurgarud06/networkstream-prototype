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

## 6. Explicitly enroll a provider hotspot

Enrollment is deliberately separate from discovery. For the prototype, an
operator/provider can explicitly enroll a hotspot with the gateway that will
provide the NetworkStream access path:

```powershell
$body = @{
  ssid = "NetworkStream-Lab"
  bssid = "AA:BB:CC:DD:EE:FF"
  providerName = "Lab Provider"
  latitude = 20.705
  longitude = 77.020
  accessType = "FREE"
  speedMbps = 20
  priceInr = 0
  gatewayId = "WIN-LAPTOP-01"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8080/api/hotspots/enroll `
  -ContentType "application/json" `
  -Body $body
```

**Do not use a random nearby third-party SSID for enrollment.** The endpoint
is a prototype operator workflow and does not yet implement provider
authentication/consent. Enrolling a phone's hotspot as a managed hotspot is
also incorrect if that phone is only being used as the laptop's upstream
Internet connection.

## 7. Verify the enrolled hotspot

```powershell
curl http://localhost:8080/api/hotspots
```

The returned hotspot has a NetworkStream hotspot ID and `gatewayId`. Its
ONLINE/OFFLINE state is derived from gateway heartbeat when it is gateway-backed.

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
