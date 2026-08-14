# NetworkStream Prototype Pack

Goal: run a safe end-to-end prototype using an ordinary Linux laptop/PC and an existing Wi-Fi router.

## Prototype modes

### Mode A — Local simulation
Cloud API + PostgreSQL + web app + two gateway simulators.

### Mode B — Real Linux gateway (safe first test)
Run `gateway-agent/networkstream-agent.py --dry-run`.
It inspects interfaces/routes and sends heartbeat only. It does NOT alter firewall/routing.

### Mode C — Real access-network experiment
Only after Mode B works. The gateway dataplane should be placed between a test client and test uplink, never a production network.

## Start

1. Start PostgreSQL + API:
   docker compose up --build

2. Start frontend:
   cd frontend
   npm install
   npm run dev

3. Start a gateway simulator:
   cd gateway-simulator
   npm install
   GATEWAY_ID=GW-A npm start

4. Open:
   http://localhost:3000

## Real Linux test

python3 gateway-agent/networkstream-agent.py --api http://YOUR_API:8080 --gateway-id TEST-GW --dry-run --once

## Test checklist

- [ ] API health works
- [ ] Hotspots appear
- [ ] Free session can be created
- [ ] Usage increments
- [ ] Premium upgrade works
- [ ] Gateway heartbeat appears
- [ ] Linux agent reports interfaces/routes
- [ ] Test router/client topology documented
- [ ] Captive portal tested on an isolated lab network
- [ ] Bandwidth policy tested
- [ ] Usage metering compared against router counters
- [ ] Roaming experiment completed

## Safety

Do not enable experimental forwarding/firewall rules on a production router.
Do not expose the API directly to the Internet without TLS, authentication and
rate limiting. Do not collect real user traffic until privacy, security and
network-isolation controls are implemented.
