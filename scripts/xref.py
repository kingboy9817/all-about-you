#!/usr/bin/env python3
"""
Cross-reference integrity check: every id referenced in frontmatter must point at
a real entity file. Catches typos and dangling links before they land on main.

What it checks:
  - contact.met_via:  if kebab-case and not free-text (no spaces), must be a known id
  - skill.used_at[]:  each id must resolve to an experience/ entry
  - project.context:  must be a known id (any entity)
  - experience.skills[]: each id must resolve to a skill/ entry

Deps: PyYAML.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


class _DateAsStringLoader(yaml.SafeLoader):
    pass


_DateAsStringLoader.yaml_implicit_resolvers = {
    ch: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


REPO = Path(__file__).resolve().parent.parent
KB_ROOT = REPO / "kb"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

FOLDERS = {
    "experience": "experience",
    "education": "education",
    "certificate": "certificates",
    "contact": "contacts",
    "skill": "skills",
    "project": "projects",
    "goal": "goals",
}


def parse_fm(md: Path) -> dict[str, Any] | None:
    text = md.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        data = yaml.load(m.group(1), Loader=_DateAsStringLoader)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def load_index() -> dict[str, dict[str, dict[str, Any]]]:
    """Return {entity_type: {id: frontmatter}}."""
    idx: dict[str, dict[str, dict[str, Any]]] = {t: {} for t in FOLDERS}
    for entity_type, folder in FOLDERS.items():
        d = KB_ROOT / folder
        if not d.exists():
            continue
        for md in sorted(d.glob("*.md")):
            fm = parse_fm(md)
            if fm and "id" in fm:
                idx[entity_type][fm["id"]] = fm
    return idx


def main() -> int:
    idx = load_index()
    all_ids: dict[str, str] = {}  # id -> entity_type
    for t, entries in idx.items():
        for eid in entries:
            all_ids[eid] = t

    errors: list[str] = []

    # contacts: met_via may be free-text OR an id
    for cid, fm in idx["contact"].items():
        v = fm.get("met_via", "")
        if isinstance(v, str) and ID_RE.match(v) and " " not in v:
            if v not in all_ids:
                errors.append(f"contact/{cid}: met_via '{v}' does not resolve to any entity id")

    # skills: used_at must resolve to experience ids
    for sid, fm in idx["skill"].items():
        for ref in fm.get("used_at", []) or []:
            if ref not in idx["experience"]:
                errors.append(
                    f"skill/{sid}: used_at '{ref}' is not a known experience id"
                )

    # experience: skills must resolve to skill ids
    for eid, fm in idx["experience"].items():
        for ref in fm.get("skills", []) or []:
            if ref not in idx["skill"]:
                errors.append(
                    f"experience/{eid}: skills '{ref}' is not a known skill id"
                )

    # projects: context (if set) must resolve to any entity
    for pid, fm in idx["project"].items():
        ctx = fm.get("context")
        if ctx and ctx not in all_ids:
            errors.append(f"project/{pid}: context '{ctx}' is not a known entity id")
        for ref in fm.get("skills", []) or []:
            if ref not in idx["skill"]:
                errors.append(f"project/{pid}: skills '{ref}' is not a known skill id")

    total = sum(len(e) for e in idx.values())
    if errors:
        print(f"xref: {len(errors)} error(s) across {total} entity file(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"xref: OK ({total} entities cross-checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
