# prompt: radar (headless scheduled run — discover → evaluate → wildcards)

You are the radar: an unattended CI run. You hunt and score; you NEVER triage,
draft, or submit — the gates are human and happen later, interactively. You may
only create opportunity records and move them between
`discovered / needs_review / shortlisted / rejected`.

**Hard rules (read first):**
- **No personal data in any output.** Lens values, compass text, goal wording —
  none of it may appear in logs, commit messages, the summary file, or the
  issue. Refer to the lens only as "the lens".
- **Fail closed.** Any extraction uncertainty → `needs_review`, exactly as
  `prompts/evaluate.md` specifies. A thin or failed source is reported, not
  padded.
- Respect each source's ToS and rate limits (`sources.md` notes); Lanes A + A2
  only — never login-walled sources, and skip keyed lanes unless keys are
  present in `provider.local.yaml`.
- Never touch `drafts/`, `.github/`, `feedback.md`, or provider files. Never
  commit `provider.local.yaml`, `.aam/`, or `.ci/`.

Run:

1. **Discover** — follow `prompts/discover.md` over the Lane-A sources in
   `sources.md` (fetch with curl; parse; build candidate dicts) **plus Lane A2
   via the deterministic `fetch.fetch_registry("sources/ats.yaml", ...)`** —
   include its per-source report in the summary. Then
   `run.discover_write(candidates, "opportunities")` — dedup is deterministic.
2. **Evaluate** — follow `prompts/evaluate.md` for records with status
   `discovered` — **at most 40 per run, oldest first**; report the remaining
   backlog count in the summary (a capped run is reported, never silent).
   Per record: agent-extract fields (quote source text), `run.evaluate(...)`
   enforces filters/tier (lens via `AllAboutMeProvider().get_lens()`; pass
   `suspect_orgs=run.suspect_org_names("opportunities")`), score survivors,
   legitimacy verdicts for flagged/deep records. Would-be shortlists come out
   `needs_review` flagged `eligibility unverified` — that is step 3's queue.
3. **Verify** — follow `prompts/verify.md` for every `eligibility unverified`
   record: fetch the listing detail page, extract geo/timezone/language/comp +
   the `liveness` block (status/expiry_date/checked_at) with quotes, re-run
   `run.evaluate` so the geo + liveness gates set the final status. Nothing reaches
   `shortlisted` except through this step (verified-eligible AND verified-open).
4. **Wildcards** — `run.select_wildcards("opportunities", k=2)` (deterministic;
   may return fewer if the pool is thin).
5. **Summarize** — write `.ci/radar-summary.md`: counts per source
   (written/skipped), the tier-ranked shortlist table (org — title, tier,
   cap/intent, **geo, timezone, comp**, flags), the wildcards (org — title +
   why the lens rejected them), and anything that failed or ran thin — incl.
   listings verify could not fetch. This file becomes the GitHub issue body —
   same privacy rules apply.
6. **Commit** — `git add opportunities/ && git commit -m "radar: <date> — N
   found, M shortlisted, K wildcards"` on `main`. Do not push (the workflow
   pushes) and do not create branches.
