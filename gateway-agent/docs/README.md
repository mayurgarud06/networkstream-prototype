# NetworkStream Linux Gateway Agent

The NetworkStream gateway agent is the software component that will eventually
control client traffic on a Linux gateway.

## Current V0.2 capabilities

- Gateway registration
- Gateway heartbeat
- Network interface discovery
- Route discovery
- Gateway policy retrieval
- Gateway command retrieval
- Safe dry-run mode

## Important

V0.2 does NOT modify:

- firewall rules
- routing
- NAT
- traffic shaping
- network interfaces

## Dry run

```bash
python3 networkstream-agent.py \
  --api http://YOUR_API:8080 \
  --gateway-id TEST-GW \
  --hotspot-id HS-A \
  --dry-run \
  --once
  ```
## Continuous mode

``` bash
python3 networkstream-agent.py \
  --api http://YOUR_API:8080 \
  --gateway-id TEST-GW \
  --hotspot-id HS-A \
  --dry-run
```