"""Dual persistence for expert roles: the graph is the source of truth, `tenants/<id>/experts/<name>.md` is a
readable export that can be re-imported.

The file is front-matter plus the system prompt, so a prompt can be reviewed in git or edited in a text editor
and brought back in (`import_dir`). Round-tripping is tested: export -> import -> the same role.
"""

from __future__ import annotations

import json
from pathlib import Path

from ripple.db import TenantScope
from ripple.onboarding.models import ExpertRole
from ripple.onboarding.store import list_experts, save_expert

FRONT = "---"
FIELDS = ("id", "name", "title", "status", "version", "origin", "stale", "ts", "mandate",
          "justification", "focus_types", "focus_relationships", "playbook", "tools")


def experts_dir(scope: TenantScope) -> Path:
    d = scope.dir / "experts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def to_markdown(role: ExpertRole) -> str:
    data = role.model_dump()
    lines = [FRONT]
    for k in FIELDS:
        v = data.get(k)
        lines.append(f"{k}: {json.dumps(v, default=str)}")
    lines += [FRONT, "", role.system_prompt.strip(), ""]
    return "\n".join(lines)


def from_markdown(text: str) -> ExpertRole:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT:
        raise ValueError("not an expert role file: no front matter")
    end = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == FRONT), None)
    if end is None:
        raise ValueError("unterminated front matter")
    data: dict = {}
    for ln in lines[1:end]:
        if not ln.strip() or ":" not in ln:
            continue
        k, raw = ln.split(":", 1)
        try:
            data[k.strip()] = json.loads(raw.strip())
        except json.JSONDecodeError:
            data[k.strip()] = raw.strip()
    data["system_prompt"] = "\n".join(lines[end + 1:]).strip()
    return ExpertRole.model_validate(data)


def export_role(scope: TenantScope, role: ExpertRole) -> Path:
    p = experts_dir(scope) / f"{role.name}.md"
    p.write_text(to_markdown(role))
    return p


def export_all(scope: TenantScope) -> list[Path]:
    return [export_role(scope, r) for r in list_experts(scope)]


def import_dir(scope: TenantScope, directory: Path | None = None) -> list[ExpertRole]:
    """Read every `*.md` in the tenant's experts directory back into the graph. Returns what was imported."""
    d = Path(directory) if directory else experts_dir(scope)
    out = []
    for p in sorted(d.glob("*.md")):
        role = from_markdown(p.read_text())
        out.append(save_expert(scope, role.model_copy(update={"origin": role.origin or "user"})))
    return out
