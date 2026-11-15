---
status: accepted
---

# Read-only Broker Connections store Members' DNSE/SSI credentials

Upstream reads holdings from Futu; Vietnam has no equivalent retail read-only feed, so besides the manual Trade Log and SSI/VPS/TCBS statement Imports we let Members opt into a Broker Connection via DNSE or SSI APIs. This means holding third-party broker credentials on the Owner's VPS, so the rules are strict: read holdings and trades only and never place orders (even though those APIs can trade), encrypt credentials at rest, let Members revoke them at any time, and sync once after the close.

## Considered Options

- **Trade Log and Imports only**: safer, but rejected as too manual for active Members.
- **Owner-only Broker Connections**: rejected; Members want the same convenience.
- **Allow the Assistant to trade**: rejected; the risk is unacceptable for a hobby deployment.
