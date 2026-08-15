# Phone B local NetworkStream access

This is the controlled Windows prototype path for the three-device lab:

```text
Phone A hotspot / upstream Internet
              |
              v
      Windows NetworkStream gateway
        192.168.137.1
          /        \
       Wi-Fi       local frontend
         |             |
      Phone B  --->  :3000
```

## What is implemented

- The frontend binds to `0.0.0.0`, so it can be reached from the Windows Mobile Hotspot.
- Docker Compose exposes the frontend on port `3000` and proxies `/api/backend/*` to the local Spring API.
- The Windows agent exposes `http://192.168.137.1:8081/client` to identify the downstream source IP.
- In `--data-plane` mode, newly discovered `192.168.137.x` clients are blocked by Windows Firewall.
- The firewall explicitly leaves ports `3000` and `8081` reachable so Phone B can open the local NetworkStream UI and identify itself before authorization.
- A successful NetworkStream session queues `ALLOW_CLIENT`; ending the session queues `BLOCK_CLIENT`.

Windows Internet Sharing/ICS is the upstream/downstream transport. Microsoft documents that ICS can provide addressing, DNS and gateway services to a private client network, while Windows Filtering Platform/Windows Firewall provides packet filtering hooks. See the Microsoft documentation linked from the project README before enabling this on a non-lab network.

## Start

On the Windows gateway laptop:

```powershell
docker compose up -d --build
python .\gateway-agent\networkstream-windows-agent.py `
  --api http://127.0.0.1:8080 `
  --gateway-id WIN-LAPTOP-01 `
  --data-plane
```

Enable Windows Mobile Hotspot and use the upstream Wi-Fi connection (for example, Phone A) as the shared Internet connection.

On Phone B:

1. Join the Windows Mobile Hotspot.
2. Open `http://192.168.137.1:3000`.
3. The NetworkStream page should show **LOCAL ACCESS** and the detected client IP.
4. Internet remains blocked until the page's **Authorize this device** action creates a session and the gateway processes `ALLOW_CLIENT`.
5. After authorization, test an Internet URL from Phone B.
6. Press **Disconnect / block client** and verify Internet stops again.

## Important limitation

The current prototype deliberately does **not** claim automatic captive-portal redirection. Phone B opens the local NetworkStream URL explicitly. Automatic captive-portal detection/HTTP interception is a separate gateway feature and should be added only after the basic blocked -> local UI -> authorize -> Internet -> block cycle is proven.

Also, Windows Firewall enforcement over ICS is an experimental lab dataplane here. Verify the actual packet path on the target Windows build before treating it as production-grade gateway isolation.
