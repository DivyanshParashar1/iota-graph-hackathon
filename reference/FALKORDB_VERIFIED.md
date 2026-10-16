# FalkorDB: verified behaviour (falkordblite 0.10.0, graph module v4.18.3, falkordb-py 1.8.0)

Verified on 2026-10-15 by running real queries against the embedded server. `scripts/verify_falkordb.py`
re-checks every item. When idea.md and this file disagree, this file wins.

## Connecting

```python
# Embedded (no server, used by tests and the cloud session). Data persists in the .db file.
from redislite.falkordb_client import FalkorDB
db = FalkorDB("var/ripple.db")          # starts a private redis-server + falkordb.so

# Remote (docker / FalkorDB Cloud). Same Graph API afterwards.
from falkordb import FalkorDB
db = FalkorDB(host="localhost", port=6379, username=None, password=None)

g = db.select_graph("tenant_dataco")
res = g.query("MATCH (n) RETURN count(n)", {"param": 1})
res.result_set          # list of rows (lists)
res.header              # column names
res.nodes_created, res.relationships_created, res.properties_set
g.ro_query(...)         # read-only variant
g.delete()              # drop the graph
db.list_graphs()
db.connection           # underlying redis client: db.connection.execute_command("SAVE")
```

* **One process must own an embedded DB file.** Two processes opening the same path each start their own server
  and the last save wins (data loss). The API process owns it; MCP, agents and the load test run in-process
  (threads or asyncio) or go through the HTTP API.
* Threads sharing one `FalkorDB` object are fine. 200 concurrent `MERGE`s from 20 threads produced exactly the
  expected 10 nodes (MERGE is atomic per query).
* Persistence across restarts works. Call `db.connection.execute_command("SAVE")` after important writes
  (incident close) and on shutdown, so a hard kill doesn't lose memory.
* Writes are fast: `UNWIND range(1,50000) CREATE (:Order {...})` took 0.02 s. Batch loads with `UNWIND $rows`
  (5K rows per batch).
* Node values come back as Python types: `datetime` from `localdatetime()`, `date` from `date()`, `OrderedDict` for
  maps, `falkordb.Node` / `falkordb.Edge` / `falkordb.Path` objects when you return entities. Return scalar
  properties (`n.id`) unless you need the object.

## Schema

```cypher
CREATE INDEX FOR (s:Supplier) ON (s.id)                 -- range index, works
CREATE VECTOR INDEX FOR (c:Chunk) ON (c.embedding) OPTIONS {dimension: 384, similarityFunction: 'cosine'}
CALL db.idx.fulltext.createNodeIndex('Document', 'title')
```

* Full-text index: use `CREATE FULLTEXT INDEX FOR (n:Document) ON (n.title)`. It works on the embedded 4.18 and on
  the `falkordb/falkordb:latest` Docker image; the procedure form `db.idx.fulltext.createNodeIndex('Document',
  'title')` is rejected by the newer server ("expected at most 1" argument). (Found during the build session.)
* Re-running `CREATE INDEX` on an existing index raises an error: wrap in try/except so schema setup is idempotent.
* Write vectors with `vecf32($list)`. The vector index dimension must match the embedder (384 for the local hash
  embedder, 1536 for `text-embedding-3-small`).
* `GRAPH.CONSTRAINT CREATE ... UNIQUE` is a separate Redis command, not Cypher, and needs an index first. Not needed:
  use `MERGE` on `id` instead.

## Queries

```cypher
-- Vector search. score is a DISTANCE: lower = more similar. Sort ASC.
CALL db.idx.vector.queryNodes('Chunk', 'embedding', 8, vecf32($qvec)) YIELD node, score
RETURN node.id, score ORDER BY score ASC

CALL db.idx.fulltext.queryNodes('Document', 'port') YIELD node, score RETURN node.title, score
```

* **Map-valued properties are rejected** ("Property values can only be of primitive types or arrays of
  primitive types"). Store maps as JSON strings (`params_json`). Lists of primitives are fine.
* `UNWIND $rows AS r MERGE (o:Order {id: r.id}) SET o += r` works (r must not contain nested maps).
* Pattern predicates work: `WHERE NOT (s)<-[:AFFECTS]-(:Disruption)`.
* `EXISTS { MATCH ... }` subquery syntax is **not** supported. Use a pattern predicate or `OPTIONAL MATCH` + `IS NULL`.
* `CALL { ... }` subqueries work (including `WITH d` imports and `UNION` inside). `FOREACH` works.
* **Trap:** a node returned by `CALL { ... UNION ... }` is not bound for a following pattern: `CALL {...} OPTIONAL MATCH
  (k)-[:WITH]->(s)` matches every `k`. Pass it through `WITH DISTINCT s` first. (Found during the build session.)
* `timestamp()` returns epoch ms. Store times as epoch-ms integers or ISO strings; compare consistently.

## Paths and routing

```cypher
-- NOT supported: MATCH p = shortestPath(...)  -> "only supports shortestPaths in WITH or RETURN clauses"
MATCH (a:Port {id:$from}), (b:Port {id:$to})
WITH shortestPath((a)-[:CONNECTS*..6]->(b)) AS p
RETURN [n IN nodes(p) | n.id] AS route, length(p) AS hops

-- Weighted k-shortest paths, then drop paths through a closed port (use this for alt_route):
MATCH (a:Port {id:$from}), (b:Port {id:$to})
CALL algo.SPpaths({sourceNode: a, targetNode: b, relTypes: ['CONNECTS'],
                   weightProp: 'transit_days', maxLen: 6, pathCount: 10})
YIELD path, pathWeight
WITH path, pathWeight WHERE NONE(n IN nodes(path) WHERE n.id IN $avoid)
RETURN [n IN nodes(path) | n.id] AS route, pathWeight AS transit_days
ORDER BY transit_days LIMIT 3

-- Single source, all destinations:
CALL algo.SSpaths({sourceNode: a, relTypes: ['CONNECTS'], weightProp: 'transit_days', maxLen: 3, pathCount: 1})
YIELD path, pathWeight
```

* `MATCH p = (a)-[*1..4]->(b) WHERE NONE(...)` fails with an internal alias error. Put the filter after
  `WITH p WHERE ...`.
* Variable-length matches can revisit nodes (`NGB->LAX->SHA->LAX`). Prefer `algo.SPpaths`.
* `allShortestPaths` needs both endpoints bound earlier in the query.

## Algorithms (procedure list: algo.betweenness, algo.BFS, algo.labelPropagation, algo.MSF, algo.pageRank, algo.SPpaths, algo.SSpaths, algo.WCC)

```cypher
CALL algo.pageRank('Supplier', 'SUPPLIES_TO') YIELD node, score            -- (label, relType) positional
CALL algo.betweenness({nodeLabels: ['Supplier'], relationshipTypes: ['SUPPLIES_TO']}) YIELD node, score
CALL algo.WCC({nodeLabels: ['Supplier'], relationshipTypes: ['SUPPLIES_TO']}) YIELD node, componentId
CALL algo.labelPropagation({nodeLabels: ['Supplier'], relationshipTypes: ['SUPPLIES_TO']}) YIELD node, communityId
MATCH (a:Supplier {id:'S1'}) CALL algo.BFS(a, 3, 'SUPPLIES_TO') YIELD nodes, edges
```

* **Betweenness is sampled by default**: it uses `samplingSize: 32` random source nodes with a time-based seed, so
  scores change between runs. Pass `samplingSize` larger than the node count (exact) and a fixed `samplingSeed`:
  `algo.betweenness({nodeLabels: ['Supplier'], relationshipTypes: ['SUPPLIES_TO'], samplingSize: 100000, samplingSeed: 42})`.
  (Found during the build session; the original smoke check failed intermittently because of this.)
* Betweenness with `{}` includes every node in the graph (Chunks, Orders...). Always pass `nodeLabels` and
  `relationshipTypes`.
* Betweenness respects edge direction. A planted chokepoint must sit *between* upstream and downstream suppliers
  along the `SUPPLIES_TO` direction to score high. Tune the generator until the test passes.
* Harmonic centrality, A*, max-flow and MSF exist in the docs (reference/falkordb-docs/algorithms) but are not
  needed.

## Generated (per-tenant) ontologies

Verified while building v2, where labels and relationship types come from a model rather than from the repo.

* **A label cannot be a parameter.** There is no `MERGE (n:$label)`. The label has to be in the query text, so
  v2 validates every generated label (`ripple/onboarding/validate.py`) and then interpolates it through one
  guarded function (`ripple.graph.queries.ident`, `^[A-Za-z][A-Za-z0-9_]{0,63}$`). The query text itself stays
  in `graph/queries/*.cypher` with `{placeholders}`.
* **`MERGE` on an unlabelled pattern scans the graph.** `MATCH (a {id: r.from}) MATCH (b {id: r.to}) MERGE
  (a)-[:REL]->(b)` cannot use an id index, because the index is per label. Loading 6,000 nodes and 5,500 edges
  that way took **16.3 s**; grouping edges by `(relationship, from label, to label)` so both `MATCH`es are
  labelled took **0.33 s** - a ~50x difference, and the single biggest performance finding of the v2 build.
* **`SET n += r.props` works with a map inside a parameter row.** The restriction is on *stored* property
  values, not on reading a map out of a parameter: `UNWIND $rows AS r ... SET e += r.props` is how edge
  properties are loaded. (A property whose own value is a map is still rejected, so
  `ripple/graph/apply.py:_flat` flattens one level and JSON-encodes anything deeper.)
* **`labels(n)` can carry a naming convention.** Every platform label is `_`-prefixed and every generated label
  is rejected if it is, so `MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH '_') DETACH DELETE n`
  reloads a tenant's instance data without touching its onboarding state.
* **Cypher keywords are fine as names.** A type called `Order`, `Set`, `Match` or `End`, a relationship type
  `ORDER`, and properties called `order`, `set`, `where` or `end` all work unquoted in the positions v2
  interpolates them. So `validate_spec` needs no reserved-word list - the identifier shape is the whole rule.
* **A duplicate `CREATE INDEX` raises**, so both the platform schema and `apply_spec` treat an
  "already exists" error as success; approving an ontology twice is a no-op rather than a failure.
* `scripts/verify_falkordb.py` checks all four of these.

## Other notes

* Labels: multiple labels per node work (`:Supplier:RiskBearing`). `labels(n)[0]` returns the first one.
* `CALL db.meta.stats()` returns label counts, relationship-type counts, and totals. Use it for the Ontology page.
* `CALL dbms.procedures()` lists procedures. `db.labels()`, `db.relationshipTypes()`, `db.propertyKeys()` exist.
* The idea.md query Q4 uses `(:Disruption {active:true})` inside a pattern predicate. That form works.
