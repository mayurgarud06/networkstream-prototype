# Prototype architecture

                 +----------------------+
                 | NetworkStream Cloud  |
                 | API + DB + Policy    |
                 +----------+-----------+
                            |
                  HTTPS / gateway API
                            |
            +---------------+---------------+
            |               |               |
        Gateway A       Gateway B       Gateway C
            |               |               |
         Router A        Router B        Router C
            |               |               |
           ISP A           ISP B           ISP C

User-facing services:
- discovery
- identity
- session orchestration
- plan/policy
- usage records

Gateway services:
- enrollment
- heartbeat
- policy retrieval
- client authentication
- firewall/forwarding
- rate limiting
- metering
- tunnel endpoint (future)

The prototype intentionally separates the control plane from the dataplane.
