# Check-In

Populates: any stale `kb/` entity file, `kb/positioning-rules/*`, and `kb/GAPS.md`.

You are running a short recurring maintenance session. Keep it targeted. The job is to prevent rot.

## Freshness pass

Scan the KB for frontmatter where:

- `durability: perishable`
- `last_confirmed + ttl_days` is in the past

Ask me to reconfirm only those facts. For each stale fact, ask:

> Is this still true, changed, unknown, or should it be deleted?

If changed, ask for the new fact and evidence. If unknown, leave it in `kb/GAPS.md`.

## New facts

Ask:

> What changed since the last check-in: roles, projects, skills, contacts, credentials, goals, constraints, public artifacts, or reputation-sensitive facts?

For each fact, classify it into:

- Entity update.
- New entity.
- Positioning rule.
- Gap / needs future deep dive.

## End-of-session rituals

Ask:

1. "What have we not covered that you did not realize was important?"
2. "If you had to answer a culture-fit essay or application question right now, what would the KB be missing?"

Then triage `kb/GAPS.md`:

- Close items now answered.
- Keep items that still need facts.
- Promote large items into a future deep-dive session.

## Write-back

Update all confirmed files in the same session. Refresh `last_confirmed` and `last_verified` when a human confirmed the fact. Add `durability` and `ttl_days` if missing.

Append unresolved questions to `kb/GAPS.md` with date, source, and next action.
