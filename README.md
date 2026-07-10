# all-about-you

**Status: research phase — nothing usable here yet.**

A plug-and-play toolkit for job seekers in the AI era, built around one idea: generic
AI job tools are shallow because they know almost nothing about you. This project ships
three layers:

1. **Intake interview** — a self-guided, multi-session interview you run with any capable
   AI assistant (Claude, ChatGPT, ...) that extracts your professional story into a
   structured knowledge base. This is the heart of the project.
2. **Knowledge base** — schema-validated markdown: one file per role, project, skill,
   contact, credential. Plain files, locally searchable, yours.
3. **Opportunity engine** — discovers openings, evaluates fit against *your* knowledge
   base, drafts tailored materials for your approval, and tracks follow-ups. Reads the
   KB through a narrow provider contract; holds no personal data itself.

The design is being distilled from months of real-world use of two private predecessors
(a personal KB and a job-application engine run on an actual job search). Current working
notes: [`research/interview-design.md`](research/interview-design.md).

No timeline promises yet. Watch the repo if you're curious.
