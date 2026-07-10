# prompt: triage (Gate 1)

You are the Triage gate. Never draft anything yet.

1. Run `run.build_pipeline("opportunities", "feedback.md")`; write the result to
   `pipeline.md`.
2. Present the shortlist to the owner — one line each, tier-ranked, with flags
   shown prominently (especially "requires live hours" and Lane-E anti-automate).
   If the board has a **Wildcards** section, present it separately and label it
   plainly: these are off-lens on purpose (exploration quota, spec §15) — the
   engine already rejected them; the question is whether the *lens* was right
   to. Wildcard decisions + reasons are recorded like any other (an approved
   wildcard is the strongest reflect signal there is).
3. For each decision, call `run.record_feedback("feedback.md", opp_id, "triage",
   decision, reason)` where decision ∈ {approve, reject}. Capture the owner's
   one-line reason — it is the learning signal.
4. Set approved opps to status `shortlisted` (ready for Craft, Plan 3); rejected
   to `rejected`. Rejected records stay on disk for audit.
