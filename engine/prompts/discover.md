# prompt: discover

You are the Discover stage. Goal: find candidate opportunities matching the lens
and hand them to `run.discover_write` as a list of candidate dicts.

Inputs: the lens (`provider.get_lens()`) and `sources.md`.

For the requested lanes:
- Lane A: fetch each feed (WebFetch). Parse out role postings. In HN hiring
  threads, job-SEEKER comments are not opportunities — drop "SEEKING WORK"
  titles AND the "Location: / Remote: / Willing to relocate:"
  who-wants-to-be-hired template (leaked once, 2026-06-12).
- Lane A2: do NOT hand-fetch these boards. Run the deterministic registry fetch —
  `fetch.fetch_registry("sources/ats.yaml", api_keys=lens.get("api_keys"))` (python3)
  — merge its candidates, and log its full per-source report (fetched/kept/error;
  keyed lanes report `skipped: no key` when unregistered).
- Lane B: only if the matching key exists in `lens["api_keys"]`; else skip and log.
  (Adzuna/Jooble are already wired through the Lane-A2 registry fetch above.)
- Lane C: run the web-search packs (WebSearch), seeded by the lens compass + soft_weights.
- Lane D: not fetched here — handled by `run.ingest_inbox`.
- Lane E: surface as a single "register here" lead per platform (source `lead:<platform>`).

Emit each candidate as:
`{source, url, org, title, description}`  (description = the raw posting text)

Do NOT extract/score here. Do NOT filter — that is the deterministic stage's job.
Log per-source counts (no silent caps): report how many each source returned.
Then call `discover_write(candidates, "opportunities")`.
