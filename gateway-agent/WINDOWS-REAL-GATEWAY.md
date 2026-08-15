# Real Windows gateway test

This is the real-hardware control-plane experiment for one Windows laptop and two phones.

## What the gateway does

The Windows gateway registers with NetworkStream, sends heartbeats, scans nearby Wi-Fi using the laptop's physical adapter, reports those observations, and reads policy/commands.

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

## 3. Verify Windows can see real Wi-Fi

```powershell
netsh wlan show networks mode=bssid
```

This output comes from Windows Wi-Fi discovery, not the NetworkStream database.

## 4. Run the NetworkStream Windows gateway

From the repository root:

```powershell
python .\gateway-agent\networkstream-windows-agent.py `
  --api http://localhost:8080 `
  --gateway-id WIN-LAPTOP-01 `
  --scan `
  --once
```

The agent registers `WIN-LAPTOP-01`, sends a heartbeat, scans nearby Wi-Fi, posts `/api/gateways/WIN-LAPTOP-01/scan`, and reads policy/commands.

For continuous observation:

```powershell
python .\gateway-agent\networkstream-windows-agent.py `
  --api http://localhost:8080 `
  --gateway-id WIN-LAPTOP-01 `
  --scan `
  --interval 15
```

## 5. Verify observations

```powershell
curl "http://localhost:8080/api/hotspots/observed?seconds=300"
```

The returned observations should contain SSIDs/BSSIDs seen by `WIN-LAPTOP-01`.

## 6. Register and enroll from the website

Open the frontend and use **Provider**:

1. Register `WIN-LAPTOP-01` with the same ID used by the agent.
2. Go to **Discover**.
3. Find a Wi-Fi network that you control/are authorized to provide.
4. Choose **Enroll this network**.
5. Confirm SSID/BSSID, provider, location, speed, price and gateway.
6. Submit **Enroll hotspot**.
7. Return to **Discover** and verify the network appears under managed NetworkStream hotspots.

A discovered SSID is only an observation. It is never automatically enrolled.

## 7. Important hardware limitation

With one Windows Wi-Fi adapter, this agent is a real observation/control-plane gateway, not a full downstream forwarding AP. To test Phone B receiving Internet *through* the NetworkStream gateway, we need a separate downstream interface/AP or the Linux two-interface lab gateway.

Do not enroll a third-party nearby Wi-Fi network. A phone hotspot used only as the laptop's upstream Internet connection is an uplink dependency, not automatically a NetworkStream provider hotspot.
