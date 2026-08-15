```markdown
# NetworkStream Gateway Protocol V0.2

## Purpose

V0.2 establishes the control-plane protocol used by both:

- the real Linux gateway agent
- the gateway simulator

## Registration

```text
POST /api/gateways/{gatewayId}/register

Example:

{
  "gatewayId": "GW-A",
  "hotspotId": "HS-A",
  "version": "0.3.0",
  "hostname": "networkstream-gw-a",
  "platform": "Linux"
}
Heartbeat
POST /api/gateways/{gatewayId}/heartbeat

Example:

{
  "gatewayId": "GW-A",
  "version": "0.3.0",
  "status": "ONLINE",
  "hostname": "networkstream-gw-a"
}
Policy
GET /api/gateways/{gatewayId}/policy

The gateway retrieves the policies that should currently be enforced.

Example:

{
  "gatewayId": "GW-A",
  "version": 4,
  "clients": [
    {
      "sessionId": "SES-123",
      "userId": "DEMO-USER",
      "plan": "FREE",
      "status": "ACTIVE",
      "downloadMbps": 5,
      "uploadMbps": 5,
      "quotaBytes": 524288000,
      "usedBytes": 104857600
    }
  ]
}
Usage
POST /api/gateways/{gatewayId}/usage

Usage comes from gateway-side counters.

The browser must not be treated as the authoritative source of network usage.

Commands
GET /api/gateways/{gatewayId}/commands

Commands will eventually control:

session activation
session termination
policy changes
client blocking

V0.2 only defines the API.

Actual firewall/routing enforcement comes later.

Security

The current prototype uses simple HTTP communication for local development.

Production requirements include:

TLS
gateway authentication
credential rotation
request authentication
rate limiting
replay protection