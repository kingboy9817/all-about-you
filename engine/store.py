# store.py
"""Load/save an opportunity as a markdown file with YAML frontmatter."""
import yaml


def load_opportunity(path):
    """Return (frontmatter_dict, body_str). Empty dict if no frontmatter."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return (yaml.safe_load(fm) or {}), body.lstrip("\n")


def save_opportunity(path, frontmatter, body=""):
    """Write frontmatter + body to a markdown file."""
    fm = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\n{fm}\n---\n\n{body.strip()}\n")
