---
id: DOC-N-PM-2021-ROTTERDAM-CONGESTION
type: postmortem
title: 'Postmortem: 2021 Rotterdam port congestion'
authors:
- EMP-N-004
mentions:
- PORT-N-NLRTM
- PORT-N-BEANR
decisions:
- id: DEC-N-006
  summary: Auto-approve reroutes that add three days or less for fifty orders or fewer
  about:
  - PORT-N-NLRTM
  - PORT-N-BEANR
  decided_at: '2021-11-30'
version: 1
updated_at: '2021-11-30'
disruption_type: port_closure
---

# Postmortem: 2021 Rotterdam port congestion

Summary. In November 2021 congestion at Rotterdam (PORT-N-NLRTM) closed berths for eight days. This was handled as a port closure.

Response. Jennifer Durham [SYNTH] rerouted European orders through Antwerp (PORT-N-BEANR). Every reroute needed manual approval, which slowed the response by two days.

Decisions. We decided that reroutes adding three days or less of transit for fifty orders or fewer are auto-approved; larger reroutes need the Logistics Lead.

Outcome. Resolved. The approval rule is now in the Rerouting Approval SOP.
