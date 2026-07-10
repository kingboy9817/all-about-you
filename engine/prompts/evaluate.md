# prompt: evaluate

You are the Evaluate stage. For each `opportunities/*.md` with status `discovered`:

1. EXTRACT from the body into `extracted`, quoting the source text for each:
   - `location`, `remote` (bool), `comp` (string|null), `deadline` (date|null)
   - `language_req` (list) when the role demands a specific working language or
     the posting itself is written in one; `geo_scope`/`eligibility` only if the
     feed text states a restriction outright — otherwise leave them for Verify.
   - note automatability/recurrence cues for scoring.
   Put a short source quote per field in the body under "## Extraction".

2. Call `run.evaluate(opp, lens, suspect_orgs=run.suspect_org_names("opportunities"))`
   to apply hard filters (suspect_orgs catches name-variants of orgs with a
   prior suspect verdict).
   - If it returns status `rejected` (filter skip) → save and move on.
   - If `needs_review` → add a `flags` note on what couldn't be verified.

3. For survivors (filter `pass`), ROUTE the lane then emit a structured `fit_inputs`
   block — do NOT author capability/intent by hand (Plan 8: `run.score_fit` computes
   them deterministically from these atoms). Quote source text per field under "## Fit inputs".

   LANE (lens `lanes`): `side_gig` vs `career`. `side_gig` = a genuinely peripheral / contract /
   low-commitment arrangement (freelance, marketplace task, piece-work). A **full-time employed role
   is `career` even if its tasks are automatable** — automatability of the work is NOT what makes
   something a side gig (commitment/distraction is). A nominal side gig that demands real
   attention/effort is also `career` (it loses unless comp + fit are high).

   `fit_inputs` (career):
   - `core_responsibilities`: each core responsibility from the JD as
     `{text, persuasion: true|false, mode: explanatory|mixed|transactional}`. persuasion = moving
     people to a new understanding/decision; explanatory = convince by clarity/expertise,
     transactional = pressure/volume/scripts. Score the FUNCTION, not the title.
   - `fit_caveats`: enumerate, one discrete checkable item each, every honest caveat the
     application would carry vs all-about-me ("no enterprise martech — adjacent only",
     "ai-orchestration level self-assessed", "no formal background in X"). Treat KB
     `confidence: medium` / "self-assessed" as latent caveats.
   - `in_domain` (bool: matches `{{target domains from kb/lens.md}}`); `comp_sgd_month` (number|null) —
     STATED comp only, normalized using `{{compensation normalization rules from kb/lens.md}}`;
     **do NOT estimate** — if comp is unstated, use `null`. (Unstated comp caps the role at `light`;
     **deep requires real comp**, which the Verify stage confirms.) `inbound` (bool), `anti_fit` (bool: core is a domain the owner lacks +
     specialists compete), `face_to_face` (bool).
   `fit_inputs` (side_gig): `automatable_fraction` (0–1), `recurring`, `async_no_meetings`,
   `non_distracting` (bools).

   Set `matched_priority_goal` = true if it clearly matches ANY priority-5 goal
   (`fde-ai-enablement` or `remote-automatable-side-income`); a priority-3 match
   (`fulltime-comp-upgrade`) is a soft signal, not a deep-tier grant.
   If it requires fixed live hours / scheduled shifts / mandatory video, add
   `"requires live hours"` to `flags` (surface, don't auto-reject).

4. Call `run.evaluate(opp, lens, org_counts=..., text=body, suspect_orgs=...)` again (now
   scored) to set tier + status. `run.evaluate` also runs the deterministic legitimacy
   flagger: any opp it leaves in `needs_review` with `legitimacy: suspect` is awaiting
   step 5. A clean would-be shortlist comes out `needs_review` with an `eligibility
   unverified` flag — that is normal: the Verify stage (`prompts/verify.md`) fetches the
   listing's fine print and re-runs the gate; only it can produce `shortlisted`.

5. REPUTATION CHECK (the verifier) — for every opp `run.evaluate` left in `needs_review` due to
   legitimacy flags, AND every `deep`-tier opp before it advances, investigate the employer:
   - web-search `"<org>" reviews/scam/Glassdoor` and check for a real company website / domain /
     contact; absence of any independent footprint is itself a yellow flag.
   - Write a `## Legitimacy check (verifier — <date>)` section into the body with what you checked,
     and set `legitimacy: ok | suspect | scam` + a one-line verdict.
   - **suspect/scam** → `status: rejected` and `run.record_feedback(..., "triage", "reject", reason)`.
     **ok** → clear the suspect flag and restore the tier's normal status (`shortlisted`).
   Never let a legitimacy-flagged opp advance to Craft without a verifier verdict.

6. `store.save_opportunity` the updated record.
