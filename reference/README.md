# Offline reference material

The cloud build session has no FalkorDB server and may have limited network access. Everything needed to
write correct code is here or in the installed packages under `.venv/lib/python3.*/site-packages/`.

| Path | What it is |
|---|---|
| `FALKORDB_VERIFIED.md` | **Read first.** Cypher, index and algorithm syntax verified against the embedded FalkorDB. Overrides idea.md. |
| `falkordb-docs/cypher/` | FalkorDB Cypher reference (clauses, functions, procedures, known limitations, indexing incl. vector + fulltext) |
| `falkordb-docs/algorithms/` | pageRank, betweenness, WCC, CDLP, BFS, SPpaths, SSpaths, MSF, harmonic, A*, maxflow |
| `falkordb-docs/agentic-memory/graphiti.mdx` | Graphiti + FalkorDB (optional memory layer) |
| `falkordb-docs/genai-tools/` | MCP server, LangGraph, GraphRAG SDK integrations |
| `falkordb-docs/getting-started/`, `operations/docker.mdx` | Client usage, Docker run |
| `claude-api/` | Anthropic Python SDK docs: client, tool use (manual loop + `tool_runner`), streaming, errors |

Library source to read when docs are not enough (after `scripts/setup_env.sh`):

* `falkordb` (client): `.venv/lib/python3.*/site-packages/falkordb/`
* embedded server wrapper: `.venv/lib/python3.*/site-packages/redislite/falkordb_client.py`
* FastMCP 4.1: `.venv/lib/python3.*/site-packages/fastmcp/` (in-memory testing: `async with fastmcp.Client(mcp) as c: await c.call_tool(name, args)`; result has `.data` / `.structured_content`)
* LangGraph: `.venv/lib/python3.*/site-packages/langgraph/`
* Graphiti FalkorDB driver: `.venv/lib/python3.*/site-packages/graphiti_core/driver/falkordb_driver.py`
