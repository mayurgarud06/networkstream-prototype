# Real Windows gateway test

This is the real-hardware control-plane experiment for one Windows laptop and two phones.

## What the gateway does

The Windows gateway registers with NetworkStream, sends heartbeats, checks that the laptop's current uplink reaches the Internet, scans nearby Wi-Fi using the laptop's physical adapter, reports those observations, and reads policy/commands.

It deliberately does **not** modify Windows routing, firewall rules, Internet Connection Sharing, or adapter configuration.

## Hardware topology

```text
Phone A hotspot (Internet uplink)
          |
          v
   Windows laptop
   NetworkStream gateway
          |
          +---- physical Wi-Fi scan
          |
          v
   NetworkStream API + PostgreSQL

Phone B can create another hotspot so the laptop can discover a known
real network. Phone B is not automatically a downstream NetworkStream
client just because the laptop is connected to Phone A.
```

## 1. Start NetworkStream

```powershell
docker compose up -d --build
docker compose ps
curl http://localhost:8080/api/hotspots
```

## 2. Put the laptop on Phone A

Enable Phone A hotspot and connect Windows to it. This is the laptop's Internet uplink.

The Windows agent also reports `internet: ONLINE/OFFLINE` by testing the laptop's current upstream connection. This verifies the gateway machine's Internet path; it does not prove that a separate downstream client can already route through NetworkStream.

## 3. Verify Windows can see real Wi-Fi

```powershell
netsh wlan show networks mode=bssid
```

This output comes from Windows Wi-Fi discovery, not the NetworkStream database.

## 4. Install the NetworkStream Windows gateway for continuous operation

Instead of manually starting the Python process for every scan, install it as a Windows scheduled task once:

```powershell
powershell -ExecutionPolicy Bypass -File .\gateway-agent\install-windows-agent.ps1 `
  -Api http://localhost:8080 `
  -GatewayId WIN-LAPTOP-01 `
  -Interval 30
```

The task starts at user logon and keeps the gateway registered, heartbeating and scanning. The agent scans by default; use `--no-scan` only when observation is intentionally disabled.

For a one-shot diagnostic run:

```powershell
python .\gateway-agent\networkstream-windows-agent.py `
  --api http://localhost:8080 `
  --gateway-id WIN-LAPTOP-01 `
  --once
```

## 5. Verify observations

```powershell
curl "http://localhost:8080/api/hotspots/observed?seconds=300"
```

The returned observations are deduplicated by BSSID when one is available. Repeated scans refresh the existing observation rather than creating a new logical entry.

## 6. Register and enroll from the website

Open the frontend and use **Provider**:

1. Register `WIN-LAPTOP-01` with the same ID used by the agent.
2. The **Registered gateways** section should show the actual gateway record.
3. Go to **Discover**.
4. Find a Wi-Fi network that you control/are authorized to provide.
5. Choose **Enroll this network**.
6. Confirm SSID/BSSID, provider, location, speed, price and gateway.
7. Submit **Enroll hotspot**.
8. Return to **Discover** and verify the network appears under managed NetworkStream hotspots.

A discovered SSID is only an observation. It is never automatically enrolled.

## 7. Important hardware limitation

With one Windows Wi-Fi adapter, this agent is a real observation/control-plane gateway, not a full downstream forwarding AP. To test Phone B receiving Internet *through* the NetworkStream gateway, we need a separate downstream interface/AP or the Linux two-interface lab gateway.

Do not enroll a third-party nearby Wi-Fi network. A phone hotspot used only as the laptop's upstream Internet connection is an uplink dependency, not automatically a NetworkStream provider hotspot.
