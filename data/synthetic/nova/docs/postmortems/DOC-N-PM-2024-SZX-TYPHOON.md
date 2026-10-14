---
id: DOC-N-PM-2024-SZX-TYPHOON
type: postmortem
title: 'Postmortem: 2024 Shenzhen typhoon and the battery pack shortage'
authors:
- EMP-N-001
- EMP-N-004
mentions:
- PORT-N-CNSZX
- SUP-N-T1-0001
- PRT-N-0001
- PORT-N-HKHKG
- SUP-N-T1-0008
decisions:
- id: DEC-N-002
  summary: 'Dual-source the Fabric panel type 1 (Nova): qualify Martinez Pitts and
    Smith [SYNTH] as an alternate to Flowers-Gomez [SYNTH] after the 2024 Shenzhen
    typhoon'
  about:
  - PRT-N-0001
  - SUP-N-T1-0001
  - SUP-N-T1-0008
  decided_at: '2024-09-20'
- id: DEC-N-003
  summary: Hold three weeks of safety stock for the Fabric panel type 1 (Nova)
  about:
  - PRT-N-0001
  decided_at: '2024-09-20'
version: 1
updated_at: '2024-09-20'
disruption_type: port_closure
---

# Postmortem: 2024 Shenzhen typhoon and the battery pack shortage

Summary. On 2024-09-06 a typhoon closed the port of Shenzhen (Yantian) (PORT-N-CNSZX) for six days. Flowers-Gomez [SYNTH] (SUP-N-T1-0001), at the time our only supplier of the Fabric panel type 1 (Nova) (PRT-N-0001), stopped production for nine days. This was a port closure combined with a sole-source failure.

Impact. Open orders for fitness and technology products that contain the battery pack slipped by up to two weeks. About $1.4M of revenue was at risk at the peak and 61 customers were affected.

Response. Jennifer Durham [SYNTH] led the port closure response: orders were rerouted through Hong Kong (PORT-N-HKHKG) and Ningbo-Zhoushan (PORT-N-CNNGB), adding two to four days of transit. Adam Khan [SYNTH] worked with the supplier on a restart plan. The contract's force majeure clause meant no delay penalties could be claimed.

Root cause. A high-criticality part was single-sourced from one plant in one typhoon-exposed region, with no qualified alternate and less than one week of safety stock.

Decisions. (1) We decided to dual-source the Fabric panel type 1 (Nova): Martinez Pitts and Smith [SYNTH] (SUP-N-T1-0008, CN) was qualified as an alternate and a second alternate outside China will follow. (2) We hold three weeks of safety stock for battery packs. (3) The dual-sourcing policy was rewritten (version 2).

Outcome. Partially resolved: rerouting recovered most orders, but the battery shortage could only be fixed by waiting for the supplier restart.
