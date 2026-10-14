---
id: DOC-PM-2024-SZX-TYPHOON
type: postmortem
title: 'Postmortem: 2024 Shenzhen typhoon and the battery pack shortage'
authors:
- EMP-001
- EMP-011
mentions:
- PORT-CNSZX
- SUP-T1-0001
- PRT-0075
- PORT-HKHKG
- SUP-T1-0095
decisions:
- id: DEC-002
  summary: 'Dual-source the Li-ion battery pack: qualify Campbell-Clark [SYNTH] as
    an alternate to Shenzhen Volt Components [SYNTH] after the 2024 Shenzhen typhoon'
  about:
  - PRT-0075
  - SUP-T1-0001
  - SUP-T1-0095
  decided_at: '2024-09-20'
- id: DEC-003
  summary: Hold three weeks of safety stock for the Li-ion battery pack
  about:
  - PRT-0075
  decided_at: '2024-09-20'
version: 1
updated_at: '2024-09-20'
disruption_type: port_closure
---

# Postmortem: 2024 Shenzhen typhoon and the battery pack shortage

Summary. On 2024-09-06 a typhoon closed the port of Shenzhen (Yantian) (PORT-CNSZX) for six days. Shenzhen Volt Components [SYNTH] (SUP-T1-0001), at the time our only supplier of the Li-ion battery pack (PRT-0075), stopped production for nine days. This was a port closure combined with a sole-source failure.

Impact. Open orders for fitness and technology products that contain the battery pack slipped by up to two weeks. About $1.4M of revenue was at risk at the peak and 61 customers were affected.

Response. Lena Fischer [SYNTH] led the port closure response: orders were rerouted through Hong Kong (PORT-HKHKG) and Ningbo-Zhoushan (PORT-CNNGB), adding two to four days of transit. Priya Raman [SYNTH] worked with the supplier on a restart plan. The contract's force majeure clause meant no delay penalties could be claimed.

Root cause. A high-criticality part was single-sourced from one plant in one typhoon-exposed region, with no qualified alternate and less than one week of safety stock.

Decisions. (1) We decided to dual-source the Li-ion battery pack: Campbell-Clark [SYNTH] (SUP-T1-0095, BR) was qualified as an alternate and a second alternate outside China will follow. (2) We hold three weeks of safety stock for battery packs. (3) The dual-sourcing policy was rewritten (version 2).

Outcome. Partially resolved: rerouting recovered most orders, but the battery shortage could only be fixed by waiting for the supplier restart.
