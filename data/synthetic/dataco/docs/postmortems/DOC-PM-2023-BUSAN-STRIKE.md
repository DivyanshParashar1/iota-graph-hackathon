---
id: DOC-PM-2023-BUSAN-STRIKE
type: postmortem
title: 'Postmortem: 2023 Pacific Arc Shipping strike at Busan'
authors:
- EMP-011
- EMP-012
mentions:
- PORT-KRPUS
decisions:
- id: DEC-004
  summary: Split ocean volume across at least two carriers on every busy lane after
    the 2023 Pacific Arc Shipping strike
  about:
  - PORT-KRPUS
  decided_at: '2023-06-30'
version: 1
updated_at: '2023-06-30'
disruption_type: carrier_strike
---

# Postmortem: 2023 Pacific Arc Shipping strike at Busan

Summary. In June 2023 crews of Pacific Arc Shipping, one of our ocean carriers, went on strike for eleven days. Every lane operated by Pacific Arc Shipping stopped, with the worst backlog at Busan (PORT-KRPUS).

Impact. About 900 open orders on affected lanes, $0.9M revenue at risk, mostly Standard Class shipments to the US and Europe.

Response. Lena Fischer [SYNTH] moved orders to lanes with the same origin and destination run by other carriers. Most reroutes added one day or less.

Decisions. We decided to split ocean volume across at least two carriers on every lane above fifty TEU per month, so that a single carrier strike never stops a lane.

Outcome. Resolved within twelve days. Carrier strikes are not force majeure in our contracts.
