# Interview README

Populates: every relevant `kb/` entity folder, `kb/lens.md`, `kb/compass.md`, `kb/positioning-rules/*`, and `kb/GAPS.md`.

You are running a multi-session intake interview to build a reusable professional KB. Do not treat this as a questionnaire. The useful material comes from rambling, correction, simulated pressure, and same-session write-back.

## How to run it

Use one prompt file per session. Paste the prompt into any AI assistant, answer by voice or typing, and let the assistant structure the mess afterward.

Start every module with a monologue-first pass:

> Talk for as long as you need. Do not make it neat. Tell the story, include side paths, name doubts, and give rough numbers even if they are ugly.

After the monologue, the assistant must play back a confirm-back summary:

> Here is what I heard. Confirm, correct, or mark uncertain items. Voice input lies, so check titles, dates, names, metrics, and causality.

Use batch gap discovery. The assistant should ask for all remaining gaps at once, not drip one question at a time.

## End every session

Run these two rituals before writing files:

1. Ask: "What have we not covered that you did not realize was important?"
2. Run a scenario probe: "If you had to answer a culture-fit essay or application question right now, what would the KB be missing?"

Then write back in the same session. Chat memory does not count. Any confirmed fact goes into the relevant `kb/` file. Any open question goes into `kb/GAPS.md`.

## Output rules

Write structured markdown files with schema-valid YAML frontmatter. Put hard filters, soft weights, tier thresholds, and eligibility in `kb/lens.md`; put the stable search north star in `kb/compass.md`. Use `last_confirmed`, `durability`, and `ttl_days` for facts that can go stale. Use fictional examples only if you are testing the template.

Append unresolved questions to `kb/GAPS.md` with date, source session, and why the fact matters.
