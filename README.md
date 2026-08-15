# NetworkStream Prototype Pack

NetworkStream is a software-first connectivity control plane with a Linux software gateway. The repository supports local simulation and a real Linux lab gateway path.

## Mode A — Local simulation

```bash
docker compose up --build
cd frontend
npm install
npm run dev
```

Run a gateway simulator:

```bash
cd gateway-simulator
npm install
GATEWAY_ID=GW-A npm start
```

## Mode B — Real Linux gateway and hotspot exploration

The Linux agent can inspect interfaces/routes and scan nearby Wi-Fi without associating with discovered networks.

```bash
python3 gateway-agent/networkstream-agent.py \
  --api http://YOUR_API:8080 \
  --gateway-id TEST-GW \
  --dry-run --scan --once
```

`--dry-run` never changes forwarding, firewall or traffic-control configuration. The Wi-Fi scan is physical radio discovery performed by the Linux gateway.

Open the frontend and use **Nearby Wi-Fi observed by gateways**. These observations are deliberately separate from approved NetworkStream hotspots: discovering an SSID does not mean NetworkStream has permission to use it.

## Mode C — Isolated lab gateway dataplane

Only use this on a dedicated lab topology with separate uplink and test-client/downlink interfaces.

```bash
sudo python3 gateway-agent/networkstream-agent.py \
  --api http://YOUR_API:8080 \
  --gateway-id LAB-GW \
  --apply --lab-mode \
  --uplink-iface eth0 \
  --downlink-iface eth1 \
  --lab-cidr 10.77.0.0/24 \
  --rate 20mbit
```

The explicit `--apply --lab-mode` gate is intentional. It enables IPv4 forwarding, NAT and an aggregate traffic shaper for the isolated lab. Do not run it against a production router/network.

## Gateway control-plane protocol

- `POST /api/gateways/{id}/register`
- `POST /api/gateways/{id}/heartbeat`
- `GET /api/gateways/{id}/policy`
- `POST /api/gateways/{id}/usage`
- `POST /api/gateways/{id}/scan`
- `GET /api/gateways/{id}/commands`
- `GET /api/hotspots/observed?seconds=180`

## Prototype checklist

- [x] API health works
- [x] Managed hotspots appear
- [x] Free session can be created
- [x] Usage simulation remains available for control-plane tests
- [x] Premium upgrade works as a prototype entitlement transition
- [x] Gateway registration and heartbeat
- [x] Gateway policy, usage and command APIs
- [x] Linux interface/route discovery
- [x] Real nearby Wi-Fi radio scan and scan ingestion
- [x] Frontend exploration of observed networks
- [x] Explicitly guarded isolated-lab NAT/forwarding/shaping path
- [ ] Captive portal on an isolated lab network
- [ ] Per-client authentication and isolation
- [ ] Per-client bandwidth policy enforcement
- [ ] Gateway byte counters reconciled against router counters
- [ ] Roaming experiment
- [ ] Production authentication, TLS, rate limiting and gateway credentials
- [ ] Payments, provider rewards and settlement

## Real lab topology

```text
                 INTERNET
                    |
               TEST UPLINK
                    |
             +--------------+
             | Linux PC     |
             | NetworkStream|
             | Gateway      |
             +------+-------+
                    |
              TEST Wi-Fi/AP
                    |
              +-----+-----+
              |           |
            Phone       Laptop
```

The gateway is the software dataplane. The existing router/uplink remains the Internet source; dedicated gateway hardware is not required for this prototype.

## Safety

Do not enable experimental forwarding/firewall rules on a production router. Do not expose the API directly to the Internet without TLS, authentication and rate limiting. Do not collect real user traffic until privacy, security and network-isolation controls are implemented.
