"""Smoke test for the embedded FalkorDB (falkordblite) and every Cypher feature Ripple depends on.

Run: .venv/bin/python scripts/verify_falkordb.py
Exits non-zero if any feature is missing. Each check mirrors a finding recorded in
reference/FALKORDB_VERIFIED.md, so a failure here means that file is out of date.
"""

import os
import sys
import tempfile

from redislite.falkordb_client import FalkorDB

failures = []


def check(name, fn):
    try:
        fn()
        print(f"  ok   {name}")
    except Exception as e:  # noqa: BLE001
        failures.append(name)
        print(f"  FAIL {name}: {e}")


def main():
    tmp = tempfile.mkdtemp(prefix="ripple-verify-")
    db = FalkorDB(os.path.join(tmp, "verify.db"))
    g = db.select_graph("verify")
    q = lambda cy, p=None: g.query(cy, p or {}).result_set  # noqa: E731

    q("UNWIND range(1,8) AS i CREATE (:Supplier:RiskBearing {id:'S'+toString(i), country: CASE WHEN i<4 THEN 'CN' ELSE 'VN' END})")
    q("MATCH (a:Supplier),(b:Supplier) WHERE toInteger(substring(a.id,1))+1 = toInteger(substring(b.id,1)) CREATE (a)-[:SUPPLIES_TO]->(b)")
    q("MATCH (a:Supplier {id:'S4'}),(b:Supplier) WHERE b.id IN ['S1','S7'] CREATE (b)-[:SUPPLIES_TO]->(a)")

    check("range index", lambda: q("CREATE INDEX FOR (s:Supplier) ON (s.id)"))

    def vector():
        q("CREATE VECTOR INDEX FOR (c:Chunk) ON (c.embedding) OPTIONS {dimension:4, similarityFunction:'cosine'}")
        q("UNWIND [[1,0,0,0],[0,1,0,0],[0.9,0.1,0,0]] AS v CREATE (:Chunk {id: toString(v[1]), embedding: vecf32(v)})")
        rows = q("CALL db.idx.vector.queryNodes('Chunk','embedding',2,vecf32($v)) YIELD node, score RETURN node.id, score ORDER BY score ASC", {"v": [1, 0, 0, 0]})
        assert rows[0][1] <= rows[1][1], "score is a distance: lower is closer"
    check("vector index + queryNodes (score = distance)", vector)

    def fulltext():
        q("CALL db.idx.fulltext.createNodeIndex('Document','title')")
        q("CREATE (:Document {title:'Shanghai port closure SOP'})")
        assert q("CALL db.idx.fulltext.queryNodes('Document','port') YIELD node RETURN node.title")
    check("fulltext index", fulltext)

    check("algo.pageRank(label, relType)", lambda: q("CALL algo.pageRank('Supplier','SUPPLIES_TO') YIELD node, score RETURN node.id, score"))

    def betweenness():
        rows = q("CALL algo.betweenness({nodeLabels:['Supplier'], relationshipTypes:['SUPPLIES_TO'], samplingSize: 1000, samplingSeed: 1}) YIELD node, score RETURN node.id, score ORDER BY score DESC")
        # S1 -> ... -> S8 chain plus S1->S4 and S7->S4 (a cycle S4..S7). Exact directed betweenness puts the
        # cycle members on top; the source S1 and sink S8 score 0. Without samplingSize the procedure samples
        # 32 random sources with a time-based seed, so scores vary run to run.
        top3 = {r[0] for r in rows[:3]}
        scores = dict(rows)
        assert "S4" in top3 and scores["S1"] == 0 and scores["S8"] == 0, rows
    check("algo.betweenness(config map)", betweenness)

    check("algo.WCC -> componentId", lambda: q("CALL algo.WCC({nodeLabels:['Supplier'], relationshipTypes:['SUPPLIES_TO']}) YIELD node, componentId RETURN componentId, count(node)"))
    check("algo.labelPropagation -> communityId", lambda: q("CALL algo.labelPropagation({nodeLabels:['Supplier'], relationshipTypes:['SUPPLIES_TO']}) YIELD node, communityId RETURN communityId, count(node)"))

    def sppaths():
        rows = q("MATCH (a:Supplier {id:'S1'}),(b:Supplier {id:'S8'}) "
                 "CALL algo.SPpaths({sourceNode:a, targetNode:b, relTypes:['SUPPLIES_TO'], maxLen:10, pathCount:3}) "
                 "YIELD path, pathWeight WITH path, pathWeight WHERE NONE(n IN nodes(path) WHERE n.id='S2') "
                 "RETURN [n IN nodes(path) | n.id], pathWeight ORDER BY pathWeight")
        assert rows and "S2" not in rows[0][0], rows
    check("algo.SPpaths + avoid-node filter", sppaths)

    check("shortestPath inside WITH", lambda: q("MATCH (a:Supplier {id:'S1'}),(b:Supplier {id:'S8'}) WITH shortestPath((a)-[:SUPPLIES_TO*..10]->(b)) AS p RETURN length(p)"))

    def shortest_in_match_rejected():
        try:
            q("MATCH (a:Supplier {id:'S1'}),(b:Supplier {id:'S8'}) MATCH p=shortestPath((a)-[:SUPPLIES_TO*..10]->(b)) RETURN p")
        except Exception:
            return
        raise AssertionError("MATCH p=shortestPath(...) unexpectedly works; FALKORDB_VERIFIED.md can be relaxed")
    check("MATCH p=shortestPath(...) is rejected (known limitation)", shortest_in_match_rejected)

    def map_props_rejected():
        try:
            q("CREATE (:Action {params: $p})", {"p": {"x": 1}})
        except Exception:
            return
        raise AssertionError("map properties unexpectedly allowed")
    check("map-valued properties rejected (store JSON strings)", map_props_rejected)

    check("list properties", lambda: q("CREATE (:Playbook {steps: ['a','b']})"))
    check("UNWIND $rows + MERGE + SET +=", lambda: q("UNWIND $rows AS r MERGE (o:Order {id:r.id}) SET o += r", {"rows": [{"id": 1, "total": 2.5}]}))
    check("pattern predicate NOT (a)<-[:R]-()", lambda: q("MATCH (s:Supplier) WHERE NOT (s)<-[:AFFECTS]-(:Disruption) RETURN count(s)"))
    check("CALL {} subquery", lambda: q("CALL { MATCH (s:Supplier) RETURN count(s) AS c } RETURN c"))
    check("db.meta.stats()", lambda: q("CALL db.meta.stats()"))

    def multigraph():
        g2 = db.select_graph("verify_other")
        g2.query("CREATE (:X)")
        assert "verify_other" in db.list_graphs()
        g2.delete()
    check("multiple graphs in one db", multigraph)

    # --- what v2's generated ontology depends on -------------------------------------------------------
    def nested_map_in_a_row():
        """`SET e += r.props` reads a map out of a parameter row: how edge properties are loaded."""
        q("UNWIND $rows AS r MERGE (a:Gen {id: r.id}) SET a += r.props",
          {"rows": [{"id": "G-1", "props": {"name": "one", "value": 1.5}}]})
        rows = q("MATCH (a:Gen {id:'G-1'}) RETURN a.name, a.value")
        assert rows == [["one", 1.5]], rows
    check("UNWIND $rows + SET n += r.props (a nested map in a row)", nested_map_in_a_row)

    def label_grouped_edge_merge():
        """Both endpoints labelled, so each MATCH uses the id index. Unlabelled, this scans the graph - which
        made v2's instance load ~50x slower (see docs/KNOWN_ISSUES.md)."""
        q("CREATE INDEX FOR (n:Gen) ON (n.id)")
        q("UNWIND range(1,50) AS i MERGE (:Gen {id:'G-'+toString(i)})")
        q("UNWIND $rows AS r MATCH (a:Gen {id: r.from}) MATCH (b:Gen {id: r.to}) MERGE (a)-[e:GEN_REL]->(b) "
          "SET e += r.props", {"rows": [{"from": "G-1", "to": "G-2", "props": {"weight": 1.0}}]})
        assert q("MATCH (:Gen {id:'G-1'})-[e:GEN_REL]->(:Gen {id:'G-2'}) RETURN e.weight") == [[1.0]]
    check("label-grouped edge MERGE (uses the id index)", label_grouped_edge_merge)

    def platform_prefix_split():
        """A generated label can never start with `_`, which is what makes "wipe the instance data but keep the
        onboarding state" a one-line predicate."""
        q("CREATE (:_Session {id:'SES-keep'})")
        q("MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH '_') AND 'Gen' IN labels(n) DETACH DELETE n")
        assert q("MATCH (n:Gen) RETURN count(n)") == [[0]]
        assert q("MATCH (n:_Session) RETURN count(n)") == [[1]]
    check("labels(n) STARTS WITH '_' separates platform state from instance data", platform_prefix_split)

    def duplicate_index_raises():
        try:
            q("CREATE INDEX FOR (n:Gen) ON (n.id)")
        except Exception as e:
            assert "already" in str(e).lower() or "exists" in str(e).lower(), e
            return
        raise AssertionError("a duplicate CREATE INDEX unexpectedly succeeded; schema setup can be simplified")
    check("duplicate CREATE INDEX raises (schema setup must be idempotent)", duplicate_index_raises)

    db.close()
    if failures:
        print(f"FAILED: {failures}")
        sys.exit(1)
    print("all FalkorDB checks passed")


if __name__ == "__main__":
    main()
