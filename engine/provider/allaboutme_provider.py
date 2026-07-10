# provider/allaboutme_provider.py
"""Reference ProfileProvider: reads a local profile KB via a gitignored provider
config. Evidence retrieval prefers qmd (ranked) when a qmd_collection is
configured, and falls back to a plain markdown glob otherwise or whenever qmd is
unavailable/unhelpful. Holds no personal data itself."""
import glob
import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml

from provider.profile_provider import ProfileProvider

_EVIDENCE_DIRS = ["experience", "projects", "skills", "education", "certificates", "contacts"]
_QMD_COMMANDS = {"search", "vsearch", "query"}
_QMD_TIMEOUT = 30  # seconds — generous enough for `query` (LLM expansion + rerank)
_QMD_TOPN = 12


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:  # missing, is-a-directory, permission — best-effort read
        return ""


def _extract_yaml_block(markdown):
    """Parse the first ```yaml fenced block, or return {}."""
    m = re.search(r"```yaml\s*\n(.*?)\n```", markdown, re.DOTALL)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}


def _frontmatter(markdown):
    if not markdown.startswith("---"):
        return {}
    _, fm, _ = markdown.split("---", 2)
    return yaml.safe_load(fm) or {}


class AllAboutMeProvider(ProfileProvider):
    def __init__(self, config_path="provider.local.yaml"):
        cfg = yaml.safe_load(_read(config_path)) or {}
        kb = cfg.get("all_about_me_path") or cfg.get("kb_path")
        if not kb:
            raise RuntimeError(
                f"provider.local.yaml missing or has no all_about_me_path/kb_path "
                f"(looked at {config_path!r}). Create it with:\n"
                f"  kb_path: /path/to/kb")
        self.kb_path = Path(kb).expanduser()
        if not self.kb_path.is_absolute():
            self.kb_path = (Path(config_path).expanduser().resolve().parent / self.kb_path).resolve()
        if not self.kb_path.is_dir():
            raise RuntimeError(f"KB path does not exist: {self.kb_path}")
        self.api_keys = cfg.get("api_keys", {}) or {}
        # qmd is an optional accelerator. Empty collection => disabled (glob-only).
        self.qmd_collection = (cfg.get("qmd_collection") or "").strip()
        self.qmd_command = (cfg.get("qmd_command") or "query").strip()
        if self.qmd_command not in _QMD_COMMANDS:
            raise RuntimeError(
                f"provider.local.yaml has invalid qmd_command {self.qmd_command!r}; "
                f"expected one of {sorted(_QMD_COMMANDS)}")

    def get_lens(self):
        block = _extract_yaml_block(_read(self.kb_path / "lens.md"))
        goals = []
        for gp in sorted(glob.glob(str(self.kb_path / "goals" / "*.md"))):
            fm = _frontmatter(_read(gp))
            if fm.get("type") == "goal" and fm.get("status", "active") == "active":
                goals.append({"id": fm.get("id"), "summary": fm.get("summary"),
                              "priority": fm.get("priority", 1)})
        return {
            "compass": _read(self.kb_path / "compass.md"),
            "goals": goals,
            "hard_filters": block.get("hard_filters", {}),
            "soft_weights": block.get("soft_weights", {}),
            "tier_thresholds": block.get("tier_thresholds", {"deep": 0.75, "light": 0.5}),
            "eligibility": block.get("eligibility", {}),
            "voice": _read(self.kb_path / "voice.md") or _read(self.kb_path / "positioning-rules" / "voice.md"),
            "api_keys": self.api_keys,
        }

    def search_evidence(self, query):
        """qmd-ranked evidence when a qmd_collection is configured; plain markdown
        glob otherwise — or whenever qmd is unavailable/unhelpful. Enabling qmd can
        only add recall, never remove it (any falsy qmd result falls back to glob)."""
        if self.qmd_collection:
            hits = self._qmd_evidence(query)
            if hits:
                return hits
        return self._glob_evidence(query)

    def _glob_evidence(self, query):
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        hits = []
        for d in _EVIDENCE_DIRS:
            for fp in sorted(glob.glob(str(self.kb_path / d / "*.md"))):
                text = _read(fp)
                if any(t in text.lower() for t in terms):
                    hits.append({"source": str(Path(fp).relative_to(self.kb_path)),
                                 "text": text.strip()})
        return hits

    def _qmd_evidence(self, query):
        """Ask qmd which KB files are most relevant, then read those files from disk
        (truth = markdown — qmd only ranks/selects). Returns [] on ANY failure or zero
        results, so the caller falls back to glob and qmd never leaves us worse off than
        glob in a failure case. argv is a list (no shell), and we strip leading dashes so
        a JD-derived query can't be mis-parsed by qmd as a flag."""
        q = re.sub(r"^[-\s]+", "", query or "")
        if not q:
            return []
        argv = ["qmd", self.qmd_command, q, "--collection", self.qmd_collection,
                "--json", "-n", str(_QMD_TOPN)]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True,
                                  errors="replace", timeout=_QMD_TIMEOUT)
            if proc.returncode != 0:
                return []
            rows = json.loads(proc.stdout or "[]")  # progress goes to stderr; stdout is pure JSON
        except (OSError, ValueError, subprocess.SubprocessError):
            return []  # binary absent, timeout, non-UTF8 / malformed output, etc.
        if not isinstance(rows, list):
            return []
        prefix = f"qmd://{self.qmd_collection}/"
        hits = []
        for row in rows:
            fileurl = row.get("file", "") if isinstance(row, dict) else ""
            rel = fileurl.split(prefix, 1)[-1].strip()
            segs = rel.split("/")
            # Contract + traversal guard: first segment must be a known evidence dir,
            # AND no '..' anywhere (else 'experience/../../etc/passwd' would climb out
            # of the KB despite a valid-looking first segment).
            if not rel or segs[0] not in _EVIDENCE_DIRS or ".." in segs:
                continue
            text = _read(self.kb_path / rel)
            if text.strip():
                hits.append({"source": rel, "text": text.strip()})
        return hits

    def propose_kb_change(self, change):
        inbox = self.kb_path / "lens-proposals"
        inbox.mkdir(exist_ok=True)
        target = str(change.get("target", "unknown")).replace("/", "_")
        h = hashlib.sha1(repr(sorted(change.items())).encode()).hexdigest()[:8]
        path = inbox / f"{target}-{h}.md"
        path.write_text(
            f"---\nsource: all-about-you\ntarget: {change.get('target')}\n---\n\n"
            f"## Proposed change\n\n**Rationale:** {change.get('rationale', '')}\n\n"
            f"**Before:**\n\n{change.get('before', '')}\n\n"
            f"**After:**\n\n{change.get('after', '')}\n", encoding="utf-8")
        return str(path)
