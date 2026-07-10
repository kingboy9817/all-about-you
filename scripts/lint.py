#!/usr/bin/env python3
"""
Validate frontmatter in every entity MD file against its JSON Schema.

Exits 0 on success, non-zero on any error. Designed to run in CI and locally.

Deps: PyYAML, jsonschema (>=4.18 for referencing). Install:
    pip install pyyaml 'jsonschema>=4.18'
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import datetime as _dt

import yaml


class _DateAsStringLoader(yaml.SafeLoader):
    """SafeLoader variant that keeps ISO-date scalars as strings.

    YAML auto-parses `2026-04-24` into `datetime.date`; our JSON Schemas declare
    these fields as strings with a regex pattern. Removing the timestamp implicit
    resolver lets the scalar through as a string.
    """


_DateAsStringLoader.yaml_implicit_resolvers = {
    ch: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _coerce(value: object) -> object:
    """Recursively turn any stray date/int values (fallback) into strings where a
    schema string is expected. We only coerce scalar year ints at the leaf level."""
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _coerce(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce(v) for v in value]
    return value


try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except ImportError as e:
    sys.stderr.write(
        f"lint.py: missing dep ({e.name}). Run: pip install pyyaml 'jsonschema>=4.18'\n"
    )
    sys.exit(2)


REPO = Path(__file__).resolve().parent.parent
KB_ROOT = REPO / "kb"
SCHEMAS_DIR = KB_ROOT / "schemas"
ENTITY_DIRS = {
    "experience": "experience",
    "education": "education",
    "certificate": "certificate",
    "contact": "contact",
    "skill": "skill",
    "project": "project",
    "goal": "goal",
}
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def load_registry() -> Registry:
    """Build a referencing Registry so $refs between schema files resolve locally."""
    resources = []
    for schema_path in SCHEMAS_DIR.glob("*.schema.json"):
        schema = json.loads(schema_path.read_text())
        resource = Resource.from_contents(schema, default_specification=DRAFT202012)
        resources.append((schema_path.name, resource))
    return Registry().with_resources(resources)


def entity_schemas(registry: Registry) -> dict[str, dict[str, Any]]:
    """Return {type: schema} for each per-entity schema."""
    out: dict[str, dict[str, Any]] = {}
    for entity_type, folder in ENTITY_DIRS.items():
        # Folder name matches schema filename stem for singular/plural? We use singular schema name.
        schema_file = SCHEMAS_DIR / f"{entity_type}.schema.json"
        if not schema_file.exists():
            raise SystemExit(f"missing schema: {schema_file}")
        out[entity_type] = json.loads(schema_file.read_text())
    return out


def parse_frontmatter(text: str, file: Path) -> dict[str, Any]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{file}: no YAML frontmatter (must start with '---')")
    try:
        data = yaml.load(m.group(1), Loader=_DateAsStringLoader)
    except yaml.YAMLError as e:
        raise ValueError(f"{file}: invalid YAML frontmatter: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{file}: frontmatter must be a mapping")
    return _coerce(data)  # type: ignore[return-value]


def folder_for_type(t: str) -> str:
    """experience/education/certificate/contact/skill/project -> folder name (plural)."""
    return {
        "experience": "experience",
        "education": "education",
        "certificate": "certificates",
        "contact": "contacts",
        "skill": "skills",
        "project": "projects",
        "goal": "goals",
    }[t]


def iter_entity_files() -> list[tuple[str, Path]]:
    """Yield (entity_type, md_path) pairs for all entity files. Skips schemas/_shared etc."""
    out: list[tuple[str, Path]] = []
    for entity_type in ENTITY_DIRS:
        folder = KB_ROOT / folder_for_type(entity_type)
        if not folder.exists():
            continue
        for md in sorted(folder.glob("*.md")):
            out.append((entity_type, md))
    return out


def freshness_warning(md: Path, fm: dict[str, Any], today: _dt.date) -> str | None:
    if fm.get("durability") != "perishable":
        return None
    last_confirmed = fm.get("last_confirmed")
    ttl_days = fm.get("ttl_days")
    if not last_confirmed or not ttl_days:
        return None
    try:
        checked = _dt.date.fromisoformat(str(last_confirmed))
        expires = checked + _dt.timedelta(days=int(ttl_days))
    except (TypeError, ValueError):
        return None
    if expires < today:
        rel = md.relative_to(REPO)
        return f"{rel}: perishable fact expired on {expires.isoformat()} (last_confirmed {checked.isoformat()}, ttl_days {ttl_days})"
    return None


def main() -> int:
    registry = load_registry()
    schemas = entity_schemas(registry)
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    today = _dt.date.today()

    for entity_type, md in iter_entity_files():
        checked += 1
        try:
            text = md.read_text()
            fm = parse_frontmatter(text, md)
        except ValueError as e:
            errors.append(str(e))
            continue

        # id must match filename (minus .md)
        expected_id = md.stem
        fm_id = fm.get("id")
        if fm_id != expected_id:
            errors.append(
                f"{md}: frontmatter id '{fm_id}' does not match filename stem '{expected_id}'"
            )
        if isinstance(fm_id, str) and not ID_RE.match(fm_id):
            errors.append(f"{md}: id '{fm_id}' must be kebab-case (^[a-z0-9][a-z0-9-]*$)")

        # type field must match folder
        if fm.get("type") != entity_type:
            errors.append(
                f"{md}: type '{fm.get('type')}' does not match folder (expected '{entity_type}')"
            )

        # Validate against schema with cross-schema $ref resolution
        validator = Draft202012Validator(schemas[entity_type], registry=registry)
        for err in sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path)):
            path = "/".join(str(p) for p in err.absolute_path) or "<root>"
            errors.append(f"{md}: {path}: {err.message}")

        warning = freshness_warning(md, fm, today)
        if warning:
            warnings.append(warning)

    if errors:
        print(f"lint: {len(errors)} error(s) across {checked} file(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"lint: WARNING: {w}")
    print(f"lint: OK ({checked} file(s) validated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
