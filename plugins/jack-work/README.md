# jack-work

Install: `/plugin install jack-work@jack-cheng-marketplace` · invoke as `/jack-work:<skill>`.

Knowledge-work skills for research and consulting output — the writing you do *around* an engagement rather than the code.

The organising idea is **additive-only**: these skills grow a document you already trust instead of regenerating it. Nothing here rewrites your prose, and every run is safe to repeat.

## Model-invoked

- **[interview-notes](./skills/interview-notes/SKILL.md)**: Incrementally sync raw interview transcripts into one consolidated Q&A memo. Strictly additive — every existing entry survives byte-for-byte, only what is missing gets appended, and additions keep the transcript's own wording. Two mechanisms enforce that: a snapshot-and-diff **non-destruction guarantee** that auto-restores the memo if any edit modifies or removes an existing line, and a **candidate ledger** that decides `new` / `thinner` / `equivalent` before writing, so a second run on the same inputs changes nothing. Chinese formatting conventions live in [`references/profile-zh.md`](./skills/interview-notes/references/profile-zh.md).

Fixtures for exercising the safety mechanisms by hand are in [`docs/fixtures/interview-notes/`](../../docs/fixtures/interview-notes/README.md).
