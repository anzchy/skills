# jack-work

Install: `/plugin install jack-work@jack-cheng-marketplace` · invoke as `/jack-work:<skill>`.

Knowledge-work skills for research and consulting output — the writing you do *around* an engagement rather than the code.

The organising idea is **additive-only**: these skills grow a document you already trust instead of regenerating it. Nothing here rewrites your prose, and every run is safe to repeat.

## Model-invoked

- **[interview-notes](./skills/interview-notes/SKILL.md)**: Incrementally sync raw interview transcripts into one consolidated Q&A memo. Strictly additive — every existing entry survives byte-for-byte, only what is missing gets appended, and additions keep the transcript's own wording. Two mechanisms enforce that: a snapshot-and-diff **non-destruction guarantee** that auto-restores the memo if any edit modifies or removes an existing line, and a **candidate ledger** that decides `new` / `thinner` / `equivalent` before writing, so a second run on the same inputs changes nothing. Chinese formatting conventions live in [`references/profile-zh.md`](./skills/interview-notes/references/profile-zh.md).

- **[jc-basic-report](./skills/jc-basic-report/SKILL.md)**: Turn a company BP plus public sources into a VC 项目基本信息报告 — one self-contained HTML following a fixed outline (投资要点 → 概念 → 公司概况与 BP 核验 → 产品与技术指标 → 市场与竞品 → 团队 → 经营 → 估值 → 风险 → 附录). Kami parchment design, charts from JSON specs, a collapsible sidebar TOC, and highlight / underline / note annotations stored in the reader's browser with JSON export/import. `scripts/build.py` refuses to build while `{{placeholders}}` remain and lists every `[DATA NEEDED]` gap; a Playwright test suite (`tests/`, run against a bundled listed-company sample or any built report via `--report`) checks the build, the TOC and the annotations.
- **[expense-reimbursement](./skills/expense-reimbursement/SKILL.md)**: Reimbursement assistant for three claim types — 市内交通, 出差, 招待. Preflights the attachments, parses ride-hailing trip reports, computes totals, meal subsidy, tax deduction and the RMB amount in words, and fills blank form templates (`templates/`, de-identified) next to the source receipts. Company-specific limits live in `references/rules-*.md`; adapt them and the templates to your own finance policy.

Fixtures for exercising the safety mechanisms by hand are in [`docs/fixtures/interview-notes/`](../../docs/fixtures/interview-notes/README.md).
