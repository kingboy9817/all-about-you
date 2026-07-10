# Intake Interview Prompt Bank

Companion to [`interview-design.md`](interview-design.md). Where that doc describes the
interview's architecture, this one catalogues the **triggers** — the specific conversational
moves and simulated situations that reliably opened long, information-rich disclosures in
the source transcripts — and turns each into reusable prompts.

## The core insight about triggers

Mining the full transcripts (assistant + user turns) for what immediately preceded every
long monologue showed that **generic open questions almost never opened the tap.** What did:

1. **An artifact in front of the user that was wrong about them.** Drafts that overstated,
   understated, or mis-attributed something triggered dense corrections — and each
   correction cascaded into backstory. People can't answer "tell me about yourself" but
   they cannot *not* correct a wrong description of themselves.
2. **Concrete external demands.** Real application essay questions, a recruiter's message,
   an eligibility gate, a reference-letter request — each forced retrieval of specific
   memories that no amount of open-ended interviewing had surfaced.
3. **Numbered mini-checklists.** "Here are 5 specific questions — answer in order or just
   brain-dump" produced the densest disclosures per prompt, including entire categories
   of undocumented work.
4. **Permission-giving open probes — but only mid-task.** "Floor's yours, the messier the
   better" worked wonderfully *after* a concrete task had warmed up the context, and not
   as a cold opener.
5. **Persona options to reject.** Offering 2-3 contrasting drafts of "who you are" (A/B/C)
   got sharper self-definition through rejection and hybridization than any direct
   "describe yourself" question.

Design consequence: the intake interview should be built as a sequence of **simulated
demands and deliberately-wrong artifacts**, not a questionnaire.

---

## Prompt bank by trigger type

### T1. Mock application essay (simulated external demand — highest yield)
- "Describe the most complex thing you've ever shipped or pulled off — what was hard, and
  what changed as a result (time saved, money, adoption)?"
- "Tell me about a time you convinced someone skeptical or unfamiliar to adopt something
  you believed in. What did you do, and what happened next?"
- "What do you optimize for in life? What should we know about you that isn't on the
  resume?" — then follow with: "what do you think that question is *really* probing for?"
- "Name one project you're proud of and explain why it matters to someone who's never
  heard of your field."

### T2. Deliberately-drafted artifact for correction ("strawman bio")
- Draft a one-page bio/CV from whatever is known so far — knowingly incomplete — and ask:
  "Read this aloud. Mark anything that's wrong, missing, or makes you wince."
- "I made three judgment calls writing this. Push back on any — and tell me what I got
  wrong about how you actually think."
- "What's the one metric or outcome that actually proves this was impressive — and is it
  in here?"
- "Rewrite the sentence you disagree with most in your own words, and say why the
  original doesn't fit."

### T3. Numbered mining-list (structured brain-dump)
- "Here are 4-6 specific questions about [period/project] — answer in any order, or just
  brain-dump everything you remember."
- "Give me numbers wherever you can: how many, how often, how big — rough guesses unlock
  detail."
- "Tell me about one specific moment where feedback, a decision, or a crisis changed what
  actually got shipped or said."

### T4. Reference-letter simulation (third-party lens)
- "Someone has to vouch for you in their own words. Who would it be, and what would they
  say if they were being completely honest rather than diplomatic?"
- "Walk me through that relationship: how'd you meet, what have they personally watched
  you do, what do they actually believe about you?"
- "If they get one sentence on why you're good at this, what's the sentence — and what
  story proves it?"

### T5. Self-audit of an existing public artifact
- "Open your LinkedIn/CV/site right now. What's embarrassing about it? What does it say
  about you that isn't true anymore — and why did it go stale?"
- "If a recruiter read this cold, what would they wrongly assume, and what's actually
  going on?"

### T6. Opportunity critique (real or sample job posting)
- "Here's a posting — walk through it line by line: which requirements map to something
  you've actually done, and which would you have to stretch for?"
- "Critically appraise your real chances. Don't be nice — name the actual holes. Then:
  what evidence, contact, or credential do you have that patches each one?"
- "Is there anything happening in your life right now (move, deadline, finances,
  relationship) that reframes how urgent or realistic this is?"

### T7. Persona options (define-by-rejection)
- Present 2-3 contrasting one-paragraph personas built from the data so far ("the
  relentless optimizer," "the translator," "the builder's builder") and ask: "Which is
  most wrong? Which parts of each are true? Build the hybrid."
- "If you never had to worry about money, what part of your work would you keep doing
  for free?"
- "Which past roles or communities do you tell stories about unprompted — why do those
  stick?"

### T8. Eligibility/constraint checklist (dense factual pass)
- "Every country you're legally authorized to work in vs. countries you merely spend time
  in — don't round these together."
- "Real tolerance for odd hours/time zones, in numbers, not vibes."
- "Every language you could work in professionally — flag any that are one-directional
  (speak but not write, read but not present)."
- After any factual pass, return a numbered list of every assumption made so far and ask
  for item-by-item confirm/correct.

### T9. Correction cascade follow-ups (pull the thread)
- Any time the user corrects a fact, ask: "Is there context around that correction that
  changes the bigger picture?"
- "You reacted to that phrasing — what's underneath the reaction?"
- "Before this ever goes external: is there anything you'd rather we never say out loud,
  and what's the private true version?"

---

## The hidden-hats module (recognition over recall)

Problem observed in the source data: an entire category of the user's professional history
(informal community leadership, crisis communications, partner relations) went undocumented
through *multiple* dedicated deep-dive interviews, surfacing only a month later under
application pressure — because the person didn't categorize it as "work worth mentioning."

"Do you wear other hats?" fails because it demands **recall** of things the person has
never labeled. The fix is **recognition**: name specific shadow-jobs and ask "have you
ever...?" — people instantly recognize experiences they could never retrieve.

Sample probes (each names a real job family):
- "Have you ever been the person new joiners got sent to, even though onboarding wasn't
  your job?" *(training/enablement)*
- "Ever calmed down angry users/customers/community members during an outage, scandal, or
  panic?" *(crisis communications)*
- "Ever written the doc, guide, or template everyone actually uses?" *(technical writing)*
- "Ever been pulled into a sales call or demo because you could explain the thing?"
  *(sales engineering / solutions)*
- "Ever screened candidates, sat in interviews, or trained your own replacement?"
  *(hiring/management)*
- "Ever run the Discord/Slack/forum — moderating, recruiting mods, setting rules?"
  *(community & platform ops)*
- "Ever been the unofficial spokesperson — the one who wrote the announcement or faced
  the users when something changed?" *(PR/comms)*
- "Ever translated — between languages, or between technical and non-technical people?"
  *(localization / developer relations)*
- "Ever kept an important relationship warm on the org's behalf — a partner, investor,
  big customer?" *(partnerships/BD/IR)*
- "Ever organized the offsite, the meetup, the launch event?" *(events/programs)*
- "Ever built a spreadsheet, script, or workflow the team came to depend on?"
  *(internal tooling/automation)*
- "Ever quietly checked others' work before it went out?" *(QA/editorial review)*

Follow each hit with the shadow-org-chart question: **"Regardless of titles, who did
people actually come to for X — and was that you?"** Then immediately workshop the
market-standard label ("that's called developer relations / solutions engineering /
program management") and record the canonical term, because unlabeled experience is
unsearchable experience.

---

## Freshness rules (anti-staleness architecture)

Recurring failure in the source data: corrections stated once kept resurfacing in drafts
("not relocating — based here"), and status lines in documents rotted silently (a README
declaring "no code yet" a month after the code shipped). Retrieval alone doesn't fix rot.
Rules:

1. **Every KB fact carries `last_confirmed` and provenance** (who said it, when, in what
   context) in frontmatter.
2. **Classify facts as durable vs. perishable.** Degrees earned: durable. "Currently
   based in…", "status: in progress", proficiency levels, comp expectations: perishable,
   each with a TTL. Check-ins re-confirm only what's past TTL — cheap and targeted.
3. **Same-session write-back is mandatory.** Any correction the user makes mid-task gets
   written to the KB (and the positioning-rules doc if it's a rule) before the session
   ends. A correction that lives only in chat history will be re-made forever.
4. **Never hand-copy status into derived artifacts.** README status lines, LinkedIn
   summaries, bios are generated from (or explicitly pointered to) the KB — a status
   sentence that lives in two places is already stale in one of them.
5. **Downstream tasks feed back.** Every fact the engine's applications force the user to
   supply on the spot is a KB gap by definition — the engine files it to the gap backlog
   automatically, closing the loop that the source project ran by hand.
