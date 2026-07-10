# Intake Interview — Design Notes

Synthesized from mining ~60 real Claude Code sessions in which one user organically built a
personal professional knowledge base (KB) and ran a job-application engine on top of it.
Four mining reports (local-only, `research/mining/`) catalogued every moment the user had to
steer, correct, or supplement the AI's picture of them. These notes generalize those findings
into a design for a reusable, self-guided intake interview.

## The core finding

A first-pass "tell me about your career" interview reliably produces a shallow KB. The
valuable material surfaced through four mechanisms, none of which a naive intake has:

1. **Open-ended monologue → AI structuring.** The richest disclosures came from long,
   unstructured (often voice-transcribed) rambles answering an open prompt — not short
   answers to narrow questions. The AI's job is to structure afterward, then confirm.
2. **The explicit "probe me where we haven't looked" ask.** The single largest content gap
   in the source project (an entire category of informal community/DevRel work) was closed
   a month in, only because the AI was directly asked to probe uncovered directions.
3. **Scenario forcing-functions.** Dormant facts (metrics, relationships, whole projects)
   only surfaced when a concrete downstream task demanded them — a real job posting, a
   reference letter, an application's essay question. The interview should simulate these.
4. **A durable gap backlog across sessions.** One sitting never suffices. The process needs
   a GAPS file, deferred-interview queue, and a recurring check-in cadence.

## Interview architecture

- **Multi-session by design.** Session 1 gets breadth; scheduled deep-dives get depth.
  Open questions park in a `GAPS.md`-style backlog that every session re-surfaces.
- **Monologue-first, then structure, then confirm.** Each module opens with one broad
  prompt inviting a long spoken/typed ramble; the AI structures it into KB entities, then
  plays back a "here's what I heard — confirm or correct" summary (critical for voice
  input, which introduces factual errors like swapped titles).
- **Batch gap discovery.** Users prefer "tell me ALL the remaining gaps at once" over
  one-at-a-time questioning.
- **End every session with two rituals:** (a) "what haven't we covered that you didn't
  realize was important?" and (b) a scenario probe ("if you had to answer a culture-fit
  essay question right now, what would we be missing?").
- **Expect asynchronous appends.** New certs, roles, and facts arrive between sessions —
  there must be a fast "log this new fact" path outside the full interview.

## Modules (question banks)

### 1. Role history — beyond the resume line
- Internal title vs. how you'd describe the role to an outsider (they often differ).
- The "job under the job": every distinct function actually owned, tagged separately
  from the umbrella title.
- Brand vs. legal employer, plus entity renames over time (startups especially).
- Why you left — every role, asked directly (users volunteer burnout/dysfunction/no-headcount
  stories only when tangentially triggered, and they're motivationally load-bearing).
- Title-inflation ceiling: the most senior title you're comfortable being presented as,
  vs. what's on LinkedIn — captured once, not renegotiated per draft.

### 2. Evidence & signature case studies
- 2-3 flagship achievements, each forced through: "what's the number that makes this land?"
  and "was it actually adopted/used, or just produced?" — with before/after metrics,
  scale/pricing figures, and any client-facing quote, pre-packaged for reuse.
- Attribution boundaries for collaborative work: which parts did YOU do?
- Self-ratings anchored to external benchmarks (cert levels, test scores), because
  first-pass self-assessments run conservative and get corrected later.
- Public-evidence inventory: GitHub, LinkedIn, blog, talks — what exists, what to surface,
  what to hide, and why.

### 3. Informal & non-traditional work
- "Any work that doesn't look like a job title but involved real responsibility —
  communities, side projects, unpaid, gig?" (In the source data this was the single
  biggest late-discovered category.)
- Adoption/evangelism stories: "describe a time you taught or convinced someone to adopt
  a tool or workflow — even informally." Powerful for advocacy/enablement roles, never
  surfaced by resume-shaped questions.
- Terminology translation: workshop the user's raw descriptions into market-standard
  labels (is this "community manager" or "DevRel"?), save the canonical label, and record
  the user's own preferred terms for fast-moving fields.

### 4. Relationships & references
- For key contacts: not just role/title, but how the relationship actually works —
  cadence, channel, mentor/sounding-board dynamics, provenance.
- Source-of-truth precedence: whose account wins when self-report and a testimonial
  conflict? (Establish once, up front.)
- Reference-disclosure policy: when may references/referrers be mentioned unprompted?

### 5. Positioning, voice & claims policy
- Self-presentation ethos: what to lead with; topics/gaps never to raise unprompted
  (e.g., a "lead with strength, never justify weaknesses" rule).
- Claims policy: the user's explicit line between confident framing and fabrication —
  a durable per-user honesty policy the drafting engine applies everywhere.
- Reputation-sensitive facts: ask directly "what here could read badly, and how do you
  want it framed?" — store both the raw fact and the public-safe framing, including
  anonymization boundaries per employer.
- Authentic-voice calibration: which "AI-sounding" words are actually part of the user's
  real vocabulary (so tone filters don't over-correct), with concrete permitted examples.
- Output-variation needs: if the KB feeds multiple artifacts (letters, CV, LinkedIn),
  identical templates/phrasing across them is a credibility risk — capture variation rules.

### 6. Constraints & fit preferences
- Hard gates, captured exactly: years of experience (a number, not a range), work
  authorization per country, physical-presence patterns (separate question from
  authorization), firm relocation dates, instant disqualifiers.
- Soft preferences as weighted trade-offs, not checkboxes: comp/remote/effort/domain as
  a balance model with the user's own numeric anchors ("what salary makes you look twice
  vs. drop everything?"). Users explicitly reject hard-floor models here.
- Domain priorities and motivation tiers, including "on the radar" applications the user
  wants to make for visibility even without perfect fit.
- Standing goals hierarchy: how the job search ranks against other tracks (own venture,
  study, etc.), since it shapes triage.

### 7. Motivation & personality bank
- "What do you optimize for? What do you refuse to automate? What's a quirky true thing
  about you?" — fodder for culture-fit essays that is never resume material and otherwise
  gets improvised under deadline pressure.

## Output contract

The interview writes into: (a) structured KB entities (schema-validated markdown), and
(b) a small set of canonical **positioning-rules documents** the downstream engine always
reads (voice, claims policy, presentation ethos, disclosure rules, formatting standards).
The source project showed corrections recurring across sessions precisely when a stated
rule had no durable home — every settled decision must be written back somewhere the
engine re-reads, or the user will restate it forever.

Separately, the engine (not the person-KB) needs a "verified constraints ledger" for
job-board realities — "remote" with hidden radius requirements, US-only gates, listing
liveness — a standing per-listing verification checklist.
