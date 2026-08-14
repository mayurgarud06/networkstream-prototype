# Prototype test plan

## Test 1: Control plane

Expected:
- `/api/hotspots` returns seeded hotspots.
- A FREE session is ACTIVE with a small policy.
- 100 MB usage increments usage.
- Upgrade changes the policy to PREMIUM.
- End changes status to ENDED.

## Test 2: Gateway control channel

Run two simulators:
GW-A and GW-B.

Expected:
- both gateways heartbeat every 10 seconds.
- `/api/gateways/GW-A` and `/api/gateways/GW-B` show ONLINE.

## Test 3: Real Linux host

Run the agent in dry-run mode.

Expected:
- prints Linux platform
- prints `ip addr`
- prints `ip route`
- sends one heartbeat
- makes no routing/firewall changes

## Test 4: Real lab dataplane

Topology:

Internet/ISP
    |
Test router/uplink
    |
Linux gateway
    |
Test Wi-Fi/AP
    |
Test phone/laptop

Only use equipment/network you control or have explicit permission to test.

Acceptance:
1. Client reaches captive portal.
2. Client authenticates.
3. Gateway assigns a session policy.
4. Client is isolated from other clients.
5. Rate limit is enforced.
6. Usage is recorded.
7. Session can expire/revoke.

## Test 5: Roaming

Two isolated gateways/APs share the same cloud identity service.

Acceptance:
1. User authenticates at A.
2. User can authenticate at B without creating a new NetworkStream account.
3. Cloud records the handoff.
4. Session continuity behavior is measured.

This is not yet seamless layer-2 roaming. The first prototype proves identity/session continuity.

## Test 6: Bonding research experiment

Do not claim bonding until measured.

A future lab:
client -> encrypted tunnel -> aggregation server
       \-> path A
       \-> path B

Measure:
- single path throughput
- two-path throughput
- latency
- packet loss
- failover time
- CPU overhead
