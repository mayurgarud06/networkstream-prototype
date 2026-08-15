# Windows gateway data-plane prototype

This prototype uses the existing Windows Mobile Hotspot/ICS path as the downstream transport. NetworkStream does not create or reconfigure the hotspot. The Windows agent discovers downstream clients and applies NetworkStream allow/block commands with Windows Firewall.

## Hardware topology

```text
Phone A (mobile Internet + hotspot)
        |
        v
Windows laptop / NetworkStream gateway
        |
        v
Windows Mobile Hotspot
        |
        v
Phone B (NetworkStream client)
```

## Start the agent

For observation only:

```powershell
python .\gateway-agent\networkstream-windows-agent.py --api http://localhost:8080 --gateway-id WIN-LAPTOP-01
```

For the real data-plane prototype, run PowerShell **as Administrator** and enable the opt-in firewall control:

```powershell
python .\gateway-agent\networkstream-windows-agent.py --api http://localhost:8080 --gateway-id WIN-LAPTOP-01 --data-plane
```

The agent does not change Windows routing or create the AP. Windows Mobile Hotspot/ICS must already be enabled and Phone B must be connected to it.

## Website flow

1. Provider opens **Provider**.
2. Confirm `WIN-LAPTOP-01` is online and Internet is online.
3. Enroll the authorized upstream hotspot/provider network.
4. Connect Phone B to the laptop Mobile Hotspot.
5. Wait for the gateway telemetry to show Phone B under **Gateways & live clients**.
6. Click **Authorize Phone B**. The API creates a real NetworkStream session and queues `ALLOW_CLIENT` for the gateway.
7. The agent consumes the command and removes the NetworkStream block rule for Phone B.
8. Phone B can browse through the existing Windows Mobile Hotspot -> Phone A Internet path.
9. Click **Disconnect / block client** in the session view. The API queues `BLOCK_CLIENT`; the agent installs inbound/outbound firewall blocks for that downstream IP.

## Signal statistics

Nearby Wi-Fi cards show the Windows `netsh` signal percentage, frequency and security. dBm remains `Unavailable` when Windows did not report a dBm value; the agent never converts a percentage into a fake dBm number.

## Important limitation

This is a controlled prototype data plane. Windows Mobile Hotspot/ICS still owns NAT and forwarding. NetworkStream owns the client authorization decision and enforcement point through the Windows Firewall. A future native gateway datapath can replace ICS while preserving the same API/session model.
