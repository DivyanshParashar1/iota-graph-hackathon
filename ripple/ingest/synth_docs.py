"""Template-generated company documents for the synthetic layer: contracts, SOPs, postmortems, chat threads.

Each markdown doc has YAML front matter (id, type, title, authors, mentions, decisions, version, updated_at);
each chat thread is a JSON file with the same fields plus messages. The generator is the source of truth for
decisions (no LLM extraction). All people and companies are synthetic.
"""

from __future__ import annotations

import yaml

SOPS = [
    ("PORT-CLOSURE", "Port Closure Response SOP", "LOG", [
        "This SOP applies when a port used by any of our lanes is closed or severely congested for more than 48 hours, "
        "for example by a typhoon, a strike or a customs shutdown. The Logistics Lead owns the response.",
        "Step 1: confirm the closure with the carrier and the port authority. Step 2: list every open order whose lane "
        "starts or ends at the closed port. Step 3: compute revenue at risk and the customers affected.",
        "Step 4: find an alternate port within trucking distance of the plant and an alternate lane to the destination. "
        "Reroutes that add three days or less of transit for fifty orders or fewer are pre-approved; anything larger "
        "needs approval from the Logistics Lead.",
        "Step 5: notify the relationship owner of every affected supplier and the Customer Ops team. Step 6: run a "
        "postmortem within ten working days and update the playbook success rate."]),
    ("SUPPLIER-INSOLVENCY", "Supplier Insolvency and Failure SOP", "PROC", [
        "This SOP covers a tier-1, tier-2 or tier-3 supplier that stops shipping because of insolvency, fire, flood or "
        "a regulatory shutdown. Procurement owns the response together with Quality.",
        "Map every part that depends on the failed supplier directly or through the tier-2 and tier-3 network. A part is "
        "at risk when all of its active suppliers are affected.",
        "Activate a qualified alternate supplier outside the affected region. Alternates must already be qualified; "
        "emergency qualification takes six weeks and needs the Supplier Quality Lead to sign off.",
        "Place customer orders that cannot be covered on hold and inform Customer Ops."]),
    ("QUALITY-HOLD", "Quality Hold Procedure", "QA", [
        "A quality hold stops shipments of a part or product lot when inspection finds a defect rate above the "
        "agreed AQL. The Quality Engineer raises the hold and records the lot numbers.",
        "Held stock is segregated. The supplier must deliver a corrective action report within five working days.",
        "Release requires two consecutive lots inside the AQL and approval from the Supplier Quality Lead."]),
    ("EXPEDITE-MATRIX", "Expedite Approval Matrix", "LOG", [
        "Expediting moves an order to a faster shipping mode, usually First Class or air freight. Every expedite has a "
        "cost delta that must be approved.",
        "Up to $5,000 of extra freight: Transport Planner. Up to $50,000: Logistics Lead. Above $50,000: Head of "
        "Supply Chain and Finance.",
        "Expedites caused by a supplier delay are charged back to the supplier when the contract has a delay penalty "
        "clause and force majeure does not apply."]),
    ("DUAL-SOURCING", "Dual-Sourcing Policy", "PROC", [
        "Version 2, updated 2024-11-15 after the September 2024 Shenzhen typhoon. Version 1 (2022) only required dual "
        "sourcing for parts above $1M annual spend.",
        "What changed in version 2: every part with high criticality must have at least two qualified suppliers in "
        "different countries. A part that is single-sourced from China must have a qualified alternate outside China.",
        "The Li-ion battery pack, previously single-sourced from Shenzhen Volt Components, now has qualified alternates "
        "and a three-week safety stock. Category Managers review single-sourced parts every quarter.",
        "Exceptions to the dual-sourcing policy need approval from the Head of Procurement and are recorded as decisions."]),
    ("CARRIER-STRIKE", "Carrier Strike Contingency SOP", "LOG", [
        "When a carrier announces a strike or a work stoppage, every lane operated by that carrier is at risk.",
        "Move open orders to a lane with the same origin and destination operated by another carrier. Since 2023 no "
        "lane above fifty TEU per month may depend on a single carrier.",
        "Notify Customer Ops of any order whose delivery date moves by more than two days."]),
    ("INCIDENT-COMMS", "Incident Communication SOP", "COPS", [
        "During a supply incident the incident lead posts an update every four hours in the incident channel.",
        "Every affected supplier's relationship owner is notified with the incident id, the numbers at risk and the "
        "relevant contract clause.",
        "Customers with more than $10,000 at risk receive a personal call from Customer Ops."]),
    ("ALT-QUALIFICATION", "Alternate Supplier Qualification SOP", "QA", [
        "An alternate supplier is qualified for a part after a capability audit, a first article inspection and a "
        "pilot lot of at least 500 units.",
        "Qualified alternates are recorded in the supplier master as QUALIFIED_FOR links and can be activated within "
        "two weeks.",
        "Qualification expires after three years without an order."]),
    ("CUSTOMER-NOTIFY", "Customer Notification Policy", "COPS", [
        "Customers are told about a delay as soon as the new delivery date is known, and never later than the original "
        "delivery date.",
        "Corporate segment customers get a named contact. Consumer segment customers get an email with the new date."]),
    ("FORCE-MAJEURE", "Force Majeure Claims Handling", "LEGAL", [
        "When a supplier invokes force majeure, Legal checks that the event is listed in the contract clause and that "
        "the supplier notified us within the contractual window.",
        "If force majeure applies, delay penalties are suspended for the duration of the event. If it does not apply, "
        "penalties accrue from the first day after the SLA.",
        "Typhoons and port closures are force majeure events in most of our contracts; carrier strikes usually are not."]),
    ("BUFFER-STOCK", "Inventory Buffer Policy", "PLAN", [
        "Safety stock covers lead time variability. High-criticality single-sourced parts carry at least three weeks "
        "of cover.",
        "Supply Planners review buffer levels monthly against the supplier reliability score."]),
    ("REROUTE-APPROVAL", "Rerouting Approval SOP", "LOG", [
        "A reroute moves open orders from a disrupted lane to an alternate lane.",
        "Reroutes adding three days or less of transit for fifty orders or fewer are executed automatically by the "
        "control tower. Larger reroutes wait in the action queue for approval by the Logistics Lead.",
        "Every reroute records the before-state so it can be undone."]),
    ("RISK-SCORING", "Supplier Risk Scoring Method", "PROC", [
        "Supplier risk score combines reliability, country risk, single-sourcing exposure and network position.",
        "Network position uses betweenness centrality over the supplier network: tier-2 suppliers that sit between "
        "many tier-3 and tier-1 suppliers are chokepoints and get a higher score."]),
    ("PENALTY-ENFORCEMENT", "Contract Penalty Enforcement SOP", "LEGAL", [
        "Delay penalties are calculated as the contract penalty percentage times the value of the affected orders times "
        "the days of delay beyond the SLA, capped at the contract cap.",
        "Legal sends a penalty notice within thirty days of the incident close. Force majeure suspends penalties."]),
    ("SUPPLIER-ONBOARDING", "Onboarding a New Tier-1 Supplier", "PROC", [
        "New tier-1 suppliers need a signed supply agreement, a relationship owner in Procurement and a backup owner.",
        "The relationship owner is the single point of contact and must hand over formally when roles change."]),
]

TEAM_ROLE_HINT = {"LOG": "Logistics", "PROC": "Procurement", "QA": "Quality", "LEGAL": "Legal", "COPS": "Customer Ops",
                  "PLAN": "Planning"}


def _md(front: dict, title: str, body: list[str]) -> str:
    fm = yaml.safe_dump(front, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm}\n---\n\n# {title}\n\n" + "\n\n".join(body) + "\n"


def generate_docs(g) -> None:  # g: synth.Gen
    rng, c = g.rng, g.c
    P = c.p
    nova = c.tenant == "nova"
    emps = g.files["employees"]
    by_team: dict[str, list[dict]] = {}
    for e in emps:
        by_team.setdefault(e["team_id"].split("-")[-1], []).append(e)
    emp = {e["id"]: e for e in emps}
    sups = {s["id"]: s for s in g.files["suppliers"]}
    parts = {p["id"]: p for p in g.files["parts"]}
    ports = {p["code"]: p for p in g.files["ports"]}
    owner_now = {o["supplier_id"]: o["employee_id"] for o in g.files["ownership"] if not o["valid_to"]}
    sup_parts: dict[str, list[str]] = {}
    for s in g.files["supplies"]:
        sup_parts.setdefault(s["supplier_id"], []).append(s["part_id"])
    qual_by_part: dict[str, list[str]] = {}
    for q in g.files["qualified"]:
        qual_by_part.setdefault(q["part_id"], []).append(q["supplier_id"])
    decisions: list[dict] = []
    dn = [0]

    def did() -> str:
        dn[0] += 1
        return f"DEC-{P}{dn[0]:03d}"

    def lead(team: str) -> dict:
        return by_team[team][0]

    # ------------------------------------------------------------- contracts
    for k in g.files["contracts"]:
        s = sups[k["supplier_id"]]
        own = emp[owner_now[s["id"]]]
        pl = [parts[p]["name"] for p in sup_parts.get(s["id"], [])[:6]]
        fm_text = ("Neither party is liable for delays caused by events beyond its reasonable control, including typhoons, "
                   "floods, earthquakes, port closures and government action, provided the Supplier notifies the Buyer "
                   "in writing within five days. Carrier strikes are not force majeure events under this agreement."
                   if k["force_majeure"] else
                   "This agreement contains no force majeure relief for port closures, weather or carrier strikes. Delay "
                   "penalties apply regardless of the cause of the delay.")
        body = [
            f"**Contract id:** {k['id']}  \n**Supplier:** {s['name']} ({s['id']}), {s['country']}  \n"
            f"**Relationship owner:** {own['name']} ({own['id']}), Procurement  \n**Term:** {k['start']} to {k['end']}",
            f"1. Scope. The Supplier supplies the following parts to the Buyer: {', '.join(pl) or 'components as ordered'}. "
            "Purchase orders are issued monthly against a rolling forecast.",
            f"2. Lead time SLA. The Supplier delivers every purchase order within {k['sla_days']} days of the order date. "
            "The SLA is measured at the Supplier's export port.",
            f"3. Delay penalties. If a delivery is late beyond the {k['sla_days']}-day SLA, the Supplier pays liquidated "
            f"damages of {k['penalty_pct']}% of the value of the affected orders for each day of delay, capped at "
            f"{k['penalty_cap_pct']}% of that value. Penalties are invoiced after the incident is closed.",
            f"4. Force majeure. {fm_text}",
            "5. Exclusivity. " + ("The Buyer sources these parts exclusively from the Supplier during the term."
                                  if k["exclusivity"] else "This agreement is non-exclusive. The Buyer may qualify and "
                                  "use alternate suppliers for any part."),
            "6. Quality. Deliveries must meet the agreed AQL. Lots outside the AQL may be placed on quality hold at the "
            "Supplier's cost.",
            "7. Termination. Either party may terminate with ninety days written notice, or immediately for a material "
            "breach that is not cured within thirty days.",
        ]
        front = {"id": k["doc_id"], "type": "contract", "title": f"Supply Agreement: {s['name']}",
                 "authors": [by_team["LEGAL"][0]["id"]], "mentions": [s["id"], own["id"]] + sup_parts.get(s["id"], [])[:6],
                 "decisions": [], "version": 1, "updated_at": k["start"]}
        g.json[f"docs/contracts/{k['doc_id']}.md"] = _md(front, front["title"], body)

    # ------------------------------------------------------------- SOPs
    sops = SOPS if not nova else SOPS[:6]
    hero_sup = g.hero_supplier
    hero_part = g.hero_part
    for i, (slug, title, team, paras) in enumerate(sops):
        doc_id = f"DOC-{P}SOP-{slug}"
        authors = [x["id"] for x in by_team[team][:2]]
        mentions: list[str] = []
        decs = []
        version, updated = 1, f"2023-{(i % 12) + 1:02d}-10"
        body = list(paras)
        if slug == "DUAL-SOURCING":
            version, updated = 2, "2024-11-15"
            if nova:
                body = [p.replace("Shenzhen Volt Components", "our electronics supplier") for p in body]
            mentions = [x for x in (hero_part, hero_sup) if x]
            d = {"id": did(), "summary": "Sourcing policy v2: every high-criticality part needs two qualified suppliers in "
                 "different countries; parts single-sourced from China need an alternate outside China",
                 "about": mentions, "decided_at": "2024-11-15", "sources": [doc_id], "participants": authors}
            decisions.append(d)
            decs.append({k2: d[k2] for k2 in ("id", "summary", "about", "decided_at")})
        if slug == "PORT-CLOSURE":
            mentions = [ports["CNSHA"]["id"], ports["NLRTM"]["id"]]
        front = {"id": doc_id, "type": "sop", "title": title, "authors": authors, "mentions": mentions,
                 "decisions": decs, "version": version, "updated_at": updated}
        body = [f"Owner team: {TEAM_ROLE_HINT[team]}. Version {version}, last updated {updated}."] + body
        g.json[f"docs/sops/{doc_id}.md"] = _md(front, title, body)

    # ------------------------------------------------------------- postmortems
    logl, procl, legal = lead("LOG"), lead("PROC"), lead("LEGAL")
    proc2 = by_team["PROC"][1] if len(by_team["PROC"]) > 1 else procl
    proc3 = by_team["PROC"][2] if len(by_team["PROC"]) > 2 else procl
    log2 = by_team["LOG"][1] if len(by_team["LOG"]) > 1 else logl
    t1 = [s for s in g.files["suppliers"] if s["tier"] == 1]
    hs = sups[hero_sup] if hero_sup else t1[0]
    hp = parts[hero_part] if hero_part else next(iter(parts.values()))
    alts = qual_by_part.get(hp["id"], [])
    alt = sups[alts[0]] if alts else t1[-1]
    choke2 = g.chokes[1]
    choke2_outs = choke2["outputs"][:4]

    def pm(slug, title, date, authors, mentions, paras, dec_specs, dtype):
        doc_id = f"DOC-{P}PM-{slug}"
        decs = []
        for summary, about in dec_specs:
            d = {"id": did(), "summary": summary, "about": about, "decided_at": date, "sources": [doc_id],
                 "participants": authors, "disruption_type": dtype}
            decisions.append(d)
            decs.append({k2: d[k2] for k2 in ("id", "summary", "about", "decided_at")})
        front = {"id": doc_id, "type": "postmortem", "title": title, "authors": authors, "mentions": mentions,
                 "decisions": decs, "version": 1, "updated_at": date, "disruption_type": dtype}
        g.json[f"docs/postmortems/{doc_id}.md"] = _md(front, title, paras)
        return doc_id, decs

    szx, hkg, ngb = ports["CNSZX"], ports["HKHKG"], ports["CNNGB"]
    pm_typhoon, dec_typhoon = pm(
        "2024-SZX-TYPHOON", "Postmortem: 2024 Shenzhen typhoon and the battery pack shortage", "2024-09-20",
        [procl["id"], logl["id"]], [szx["id"], hs["id"], hp["id"], hkg["id"], alt["id"]],
        [f"Summary. On 2024-09-06 a typhoon closed the port of {szx['name']} ({szx['id']}) for six days. "
         f"{hs['name']} ({hs['id']}), at the time our only supplier of the {hp['name']} ({hp['id']}), stopped "
         "production for nine days. This was a port closure combined with a sole-source failure.",
         "Impact. Open orders for fitness and technology products that contain the battery pack slipped by up to two "
         "weeks. About $1.4M of revenue was at risk at the peak and 61 customers were affected.",
         f"Response. {logl['name']} led the port closure response: orders were rerouted through {hkg['name']} "
         f"({hkg['id']}) and {ngb['name']} ({ngb['id']}), adding two to four days of transit. {procl['name']} "
         "worked with the supplier on a restart plan. The contract's force majeure clause meant no delay penalties "
         "could be claimed.",
         "Root cause. A high-criticality part was single-sourced from one plant in one typhoon-exposed region, with no "
         "qualified alternate and less than one week of safety stock.",
         f"Decisions. (1) We decided to dual-source the {hp['name']}: {alt['name']} ({alt['id']}, {alt['country']}) "
         "was qualified as an alternate and a second alternate outside China will follow. (2) We hold three weeks of "
         "safety stock for battery packs. (3) The dual-sourcing policy was rewritten (version 2).",
         "Outcome. Partially resolved: rerouting recovered most orders, but the battery shortage could only be fixed by "
         "waiting for the supplier restart."],
        [(f"Dual-source the {hp['name']}: qualify {alt['name']} as an alternate to {hs['name']} after the 2024 "
          "Shenzhen typhoon", [hp["id"], hs["id"], alt["id"]]),
         (f"Hold three weeks of safety stock for the {hp['name']}", [hp["id"]])], "port_closure")
    pus = ports["KRPUS"]
    carrier = "Pacific Arc Shipping"
    pm_busan, dec_busan = pm(
        "2023-BUSAN-STRIKE", f"Postmortem: 2023 {carrier} strike at Busan", "2023-06-30",
        [logl["id"], log2["id"]], [pus["id"]],
        [f"Summary. In June 2023 crews of {carrier}, one of our ocean carriers, went on strike for eleven days. "
         f"Every lane operated by {carrier} stopped, with the worst backlog at {pus['name']} ({pus['id']}).",
         "Impact. About 900 open orders on affected lanes, $0.9M revenue at risk, mostly Standard Class shipments "
         "to the US and Europe.",
         f"Response. {logl['name']} moved orders to lanes with the same origin and destination run by other carriers. "
         "Most reroutes added one day or less.",
         f"Decisions. We decided to split ocean volume across at least two carriers on every lane above fifty TEU per "
         "month, so that a single carrier strike never stops a lane.",
         "Outcome. Resolved within twelve days. Carrier strikes are not force majeure in our contracts."],
        [(f"Split ocean volume across at least two carriers on every busy lane after the 2023 {carrier} strike",
          [pus["id"]])], "carrier_strike")
    c2 = sups[choke2["id"]]
    pm_fire, dec_fire = pm(
        "2022-TIER2-FIRE", f"Postmortem: 2022 fire at tier-2 supplier {c2['name']}", "2022-03-15",
        [proc2["id"], by_team["QA"][0]["id"]], [c2["id"]] + choke2_outs,
        [f"Summary. A fire at {c2['name']} ({c2['id']}), a tier-2 supplier, stopped its output for three weeks. "
         f"It feeds {len(choke2['outputs'])} of our tier-1 suppliers, so the failure rippled into parts we did not "
         "know depended on it.",
         "Impact. Several single-sourced parts went on allocation; some customer orders were placed on hold.",
         "Root cause. We had no map of tier-2 and tier-3 dependencies. The supplier was a hidden chokepoint between many "
         "tier-3 and tier-1 suppliers.",
         "Decisions. We decided to map tier-2 dependencies for all critical parts and to qualify alternates for parts "
         "fed through a single tier-2 supplier. Betweenness centrality on the supplier network is now part of the risk "
         "score.",
         "Outcome. Partially resolved: alternates were qualified for most parts within two months."],
        [(f"Map tier-2 dependencies and qualify alternates for parts fed through a single tier-2 supplier after the "
          f"{c2['name']} fire", [c2["id"]] + choke2_outs)], "supplier_failure")
    rtm, anr = ports["NLRTM"], ports["BEANR"]
    pm_rtm, dec_rtm = pm(
        "2021-ROTTERDAM-CONGESTION", "Postmortem: 2021 Rotterdam port congestion", "2021-11-30",
        [logl["id"]], [rtm["id"], anr["id"]],
        [f"Summary. In November 2021 congestion at {rtm['name']} ({rtm['id']}) closed berths for eight days. "
         "This was handled as a port closure.",
         f"Response. {logl['name']} rerouted European orders through {anr['name']} ({anr['id']}). Every reroute needed "
         "manual approval, which slowed the response by two days.",
         "Decisions. We decided that reroutes adding three days or less of transit for fifty orders or fewer are "
         "auto-approved; larger reroutes need the Logistics Lead.",
         "Outcome. Resolved. The approval rule is now in the Rerouting Approval SOP."],
        [("Auto-approve reroutes that add three days or less for fifty orders or fewer", [rtm["id"], anr["id"]])],
        "port_closure")

    # ------------------------------------------------------------- chats
    ts_n = [0]

    def thread(n: int, channel: str, title: str, msgs: list[tuple[dict, str]], date: str, mentions: list[str],
               dec_specs: list[tuple[str, list[str], int]] | None = None, docs_ref: list[str] | None = None,
               existing: list[tuple[dict, int]] | None = None) -> dict:
        tid = f"THR-{P}{n:03d}"
        doc_id = f"DOC-{P}CHAT-{n:03d}"
        messages = []
        for i, (who, text) in enumerate(msgs):
            messages.append({"id": f"MSG-{P}{n:03d}-{i + 1:02d}", "author": who["id"],
                             "ts": f"{date}T{9 + i // 2:02d}:{(i * 13) % 60:02d}", "text": text})
        decs = []
        for summary, about, msg_idx in dec_specs or []:
            d = {"id": did(), "summary": summary, "about": about, "decided_at": date,
                 "sources": [doc_id, messages[msg_idx]["id"]] + (docs_ref or []),
                 "participants": sorted({m["author"] for m in messages})}
            decisions.append(d)
            decs.append({k2: d[k2] for k2 in ("id", "summary", "about", "decided_at")})
        for dref, msg_idx in existing or []:  # a decision first recorded elsewhere, also argued in this thread
            d = next(x for x in decisions if x["id"] == dref["id"])
            d["sources"] += [doc_id, messages[msg_idx]["id"]]
            d["participants"] = sorted(set(d["participants"]) | {m["author"] for m in messages})
            decs.append(dref)
        obj = {"id": tid, "doc_id": doc_id, "type": "chat_thread", "channel": channel, "title": title,
               "authors": sorted({m["author"] for m in messages}), "mentions": mentions, "decisions": decs,
               "version": 1, "updated_at": date, "messages": messages}
        g.json[f"chats/{tid}.json"] = obj
        return obj

    pr, dan, hiro = procl, proc2, proc3
    thread(1, "#sourcing-electronics", f"Should we dual-source the {hp['name']}?", [
        (pr, f"After the typhoon we can't stay single-sourced on the {hp['name']} from {hs['name']}. Nine days without "
             "batteries took out a whole product line."),
        (dan, f"{hs['name']} is about 12% cheaper than anyone else. Dual-sourcing the battery pack raises unit cost and "
              "we lose volume discounts."),
        (legal, f"Legal view: the {hs['name']} contract has a force majeure clause that covers typhoons, so we had no "
                "recourse for the stoppage. Penalties won't protect us here."),
        (hiro, f"{alt['name']} in {alt['country']} passed the qualification audit last week. They can take 30% of the "
               "battery volume within a quarter."),
        (pr, f"Decision: we dual-source the {hp['name']}. {alt['name']} becomes the qualified alternate and stays on "
             "standby until their capacity ramps; we also keep three weeks of safety stock."),
        (dan, "Agreed. I'll update the sourcing policy and the supplier master."),
    ], "2024-09-27", [hp["id"], hs["id"], alt["id"]], existing=[(dec_typhoon[0], 4)])
    thread(2, "#incident-war-room", "Shenzhen typhoon war room (2024)", [
        (logl, f"Typhoon warning for {szx['name']}. Port authority says {szx['id']} closes tonight, probably five to "
               "seven days."),
        (log2, f"We have open orders on lanes out of {szx['name']}. I'm checking alternate routing through "
               f"{hkg['name']}."),
        (logl, f"Rerouting the larger customer orders through {hkg['name']} and {ngb['name']}. Adds two to four days. "
               "This is our standard port closure play."),
        (pr, f"{hs['name']} just confirmed their plant is shut too. Battery packs will be the bottleneck."),
    ], "2024-09-06", [szx["id"], hkg["id"], ngb["id"], hs["id"]])
    thread(3, "#logistics", f"{carrier} strike (2023)", [
        (logl, f"{carrier} crews walk out tomorrow. Every lane they run is affected, Busan is the worst."),
        (log2, "Moving the Standard Class orders to the same lanes on other carriers. Mostly one extra day."),
        (logl, "Decision: from now on no busy lane depends on a single carrier. Split volume across at least two."),
    ], "2023-06-12", [pus["id"]], existing=[(dec_busan[0], 2)])
    thread(4, "#incident-war-room", "Rotterdam congestion (2021)", [
        (logl, f"Berths at {rtm['name']} closed for at least a week. Rerouting Europe orders via {anr['name']}."),
        (log2, "Approvals are taking forever, every reroute needs a sign-off."),
        (logl, "Proposal: auto-approve small reroutes (three days or less, fifty orders or fewer)."),
    ], "2021-11-09", [rtm["id"], anr["id"]], existing=[(dec_rtm[0], 2)])
    thread(5, "#quality", f"{c2['name']} fire (2022)", [
        (proc2, f"{c2['name']} had a fire overnight. They are a tier-2 supplier but feed a lot of our tier-1s."),
        (by_team["QA"][0], "We had no idea how many parts depend on them. We need a tier-2 map."),
    ], "2022-02-21", [c2["id"]] + choke2_outs, existing=[(dec_fire[0], 1)])
    # templated threads
    templates = [
        ("#sourcing", "Lead time slip from {s}", ["{s} says lead times on {p} move from {a} to {b} days.",
                                                  "That eats our buffer for {p}. Can we pull forward the next order?",
                                                  "Decision: raise safety stock for {p} to four weeks until {s} recovers."]),
        ("#quality", "Quality issue on {p}", ["Incoming inspection rejected a lot of {p} from {s}: defect rate 3.1%.",
                                              "Placing the lot on quality hold and asking {s} for a corrective action report.",
                                              "Decision: 100% inspection on {p} from {s} for the next three lots."]),
        ("#sourcing", "Price increase from {s}", ["{s} wants a 6% price increase on {p} from next quarter.",
                                                  "Their contract caps increases at 3%. I'll push back.",
                                                  "Legal confirms the cap applies."]),
        ("#logistics", "Customs hold at {port}", ["Two containers are held by customs at {port}.",
                                                  "Paperwork issue on the commercial invoice. Expect two days.",
                                                  "Released this morning."]),
        ("#planning", "Capacity check with {s}", ["Can {s} cover a 20% forecast increase on {p} in Q3?",
                                                  "They can do 10% from the current plant, the rest needs overtime.",
                                                  "Decision: split the extra volume of {p} with a second supplier."]),
    ]
    n_thr = 5
    t1_list = [s for s in t1 if s["id"] in sup_parts]
    port_list = sorted(ports.values(), key=lambda p: p["id"])
    while n_thr < c.n_chats:
        n_thr += 1
        ch, title, lines = templates[(n_thr - 6) % len(templates)]
        s = rng.choice(t1_list)
        pid = rng.choice(sup_parts[s["id"]])
        prt = rng.choice(port_list)
        own = emp[owner_now[s["id"]]]
        others = [x for x in emps if x["id"] != own["id"]]
        who = [own, rng.choice(others), own]
        fill = {"s": s["name"], "p": parts[pid]["name"], "a": rng.randint(14, 25), "b": rng.randint(28, 45),
                "port": prt["name"]}
        msgs = [(who[i], line.format(**fill)) for i, line in enumerate(lines)]
        decs = None
        if lines[-1].startswith("Decision"):
            decs = [(lines[-1].format(**fill).replace("Decision: ", "").rstrip("."), [pid, s["id"]], 2)]
        thread(n_thr, ch, title.format(**fill), msgs,
               f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", [s["id"], pid, prt["id"]], decs)

    # ------------------------------------------------------------- delta (not ingested at build)
    if hero_sup:
        new_owner = dan
        g.json["delta/handover.json"] = {
            "kind": "chat", "channel": "#sourcing-electronics", "author_id": pr["id"],
            "text": (f"Heads up team: I'm handing over the {hs['name']} relationship to {new_owner['name']} effective "
                     f"today. {new_owner['name'].replace(' [SYNTH]', '')} is the new owner; I stay on as backup during "
                     "the transition."),
            "expected": {"supplier_id": hs["id"], "new_owner_id": new_owner["id"], "old_owner_id": pr["id"]}}

    g.json["decisions.json"] = decisions
    g.json["planted.json"] = {
        "chokepoints": g.chokes, "single_sourced_parts": len(g.single_sourced), "n_parts": len(g.files["parts"]),
        "hero": {"supplier_id": hero_sup, "part_id": hero_part, "alt_supplier_id": alt["id"],
                 "owner_id": owner_now.get(hero_sup) if hero_sup else None,
                 "typhoon_postmortem": pm_typhoon, "battery_thread_doc": f"DOC-{P}CHAT-001",
                 "dual_sourcing_sop": f"DOC-{P}SOP-DUAL-SOURCING",
                 "contract_doc": next((k["doc_id"] for k in g.files["contracts"] if k["supplier_id"] == hero_sup), None),
                 "port_closure_postmortems": [pm_typhoon, pm_rtm], "port_closure_expert": logl["id"]},
        "carrier_strike_carrier": carrier,
        "postmortems": {"port_closure": [pm_typhoon, pm_rtm], "carrier_strike": [pm_busan],
                        "supplier_failure": [pm_fire]},
    }
