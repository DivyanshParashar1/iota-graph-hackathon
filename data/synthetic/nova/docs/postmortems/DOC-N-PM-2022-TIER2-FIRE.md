---
id: DOC-N-PM-2022-TIER2-FIRE
type: postmortem
title: 'Postmortem: 2022 fire at tier-2 supplier Fox Inc [SYNTH]'
authors:
- EMP-N-002
- EMP-N-008
mentions:
- SUP-N-T2-0013
- SUP-N-T1-0004
- SUP-N-T1-0006
- SUP-N-T1-0007
decisions:
- id: DEC-N-005
  summary: Map tier-2 dependencies and qualify alternates for parts fed through a
    single tier-2 supplier after the Fox Inc [SYNTH] fire
  about:
  - SUP-N-T2-0013
  - SUP-N-T1-0004
  - SUP-N-T1-0006
  - SUP-N-T1-0007
  decided_at: '2022-03-15'
version: 1
updated_at: '2022-03-15'
disruption_type: supplier_failure
---

# Postmortem: 2022 fire at tier-2 supplier Fox Inc [SYNTH]

Summary. A fire at Fox Inc [SYNTH] (SUP-N-T2-0013), a tier-2 supplier, stopped its output for three weeks. It feeds 3 of our tier-1 suppliers, so the failure rippled into parts we did not know depended on it.

Impact. Several single-sourced parts went on allocation; some customer orders were placed on hold.

Root cause. We had no map of tier-2 and tier-3 dependencies. The supplier was a hidden chokepoint between many tier-3 and tier-1 suppliers.

Decisions. We decided to map tier-2 dependencies for all critical parts and to qualify alternates for parts fed through a single tier-2 supplier. Betweenness centrality on the supplier network is now part of the risk score.

Outcome. Partially resolved: alternates were qualified for most parts within two months.
