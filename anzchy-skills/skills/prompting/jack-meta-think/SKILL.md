---
name: jack-meta-think
description: Diagnoses the QUESTION before any prompt is written. Scans a raw ask for embedded conclusions, evaluative language, missing timeline, missing identifiers and missing ruled-out factors, then interactively resolves what only the asker can answer (what are you actually trying to find out) and rewrites the ask as a neutral, open-ended question. Domain-general — works for debugging, medical, purchase, relationship and career questions alike, not just coding. Use when the user has a rough ask, a suspicion, or a frustration rather than a draft prompt. Trigger keywords - "我该怎么问", "这个问题这样问对吗", "帮我想清楚我要问什么", "/jack-meta-think", "提问诊断", "diagnose my question". Distinct from /jack-prompt-master, which polishes an already-well-aimed coding prompt.
version: 0.1.0
---

# jack-meta-think

Upstream of every prompt-optimization skill. It does not improve wording — it checks whether the question is aimed at the truth or at agreement, and repairs the aim.

Source of the criteria: 和菜头《关于 AI 时代如何提问》. The full criteria table lives in `references/checklist.md`.

## Core premise

A tournament, a rubric, and a synthesizer will happily polish a false premise into a *very* persuasive false premise. `分析一下这张图里的倭风` and `分析一下这张图里的泰国风` both get a confident, well-argued answer for the same photograph. This skill runs before that happens.

## When to invoke

- The user has a suspicion, a frustration, or a diagnosis-in-disguise, not a draft prompt: "我室友是不是有毛病", "这 bug 肯定是 hydration 导致的", "我该不该辞职".
- The user asks how to ask: "这个问题该怎么问 AI 才有用".
- Any ask where the answer's usefulness depends on a premise nobody has verified.

## When NOT to invoke

- The draft's aim is already correct and only the wording needs work → `/jack-prompt-master` (multi-round tournament, coding, high stakes) or `/prompt-enhance` (one-shot polish).
- The user wants the answer, not a better question. Do not hijack a straightforward request into a Socratic session — say once that the premise looks unverified, then answer.

## Output disposition (explicit)

This skill outputs **a rewritten question**, as a copy-paste block. It does NOT answer the question, does NOT execute anything, does NOT auto-hand-off to another skill. If the rewritten question happens to be a high-stakes coding prompt, the skill *suggests* `/jack-prompt-master` in one line and stops. The user decides.

## Configuration (env overrides)

| Knob | Default | Env override |
| --- | --- | --- |
| MAX_AUQ_CALLS | 2 | `JMT_MAX_AUQ` (1/2/3) |
| SKIP_INTERVIEW | off | `JMT_SKIP_INTERVIEW` (on/off) |

`SKIP_INTERVIEW=on` jumps straight from the scan to a best-effort rewrite with every unresolved gap marked `[待你补充]`. Use it when the user is in a hurry or is not present.

## Phase 0 — Input

If `$ARGUMENTS` is empty, `AskUserQuestion`: "你想问的问题是什么？原话就行，不用整理。" (Header: "原始问题"). Still empty → print `Usage: /jack-meta-think "<你想问的问题>"` and exit.

Preserve the ask **verbatim**. The evaluative words are the evidence — never clean them up before the scan.

## Phase 1 — Criterion scan

Load `references/checklist.md`. Score the raw ask against C1–C7 and emit one table:

| 判据 | 结果 | 证据（引用原话） |
| --- | --- | --- |

Rules for this table:

- Every FAIL MUST quote the exact span from the user's own words that triggered it. No quote, no FAIL.
- C1 (预设结论) and C2 (事实/判断分离) are reported, **never silently repaired**. Whether `他针对我` is an observation or an assumption is not knowable from the text — it is knowable only from the asker. Wrong-guessing it is the exact failure this skill exists to prevent.
- C3 only fires when the ask's core interrogative is 怎么看 / 什么感受 / 好不好. An imperative ("帮我修 X") is not a C3 failure — skip it, do not force a W/W/H shape onto an instruction.
- C4/C5/C6/C7 FAILs become interview questions in Phase 2. Do not invent the missing facts.
- Mark `[不适用]` freely. A question about a concept has no 型号; a question with no 变化 has no timeline.

## Phase 2 — Interview

At most `MAX_AUQ_CALLS` `AskUserQuestion` calls, ≤3 questions each. Order by leverage, not by criterion number.

**Always ask first if C1 or C2 failed** — this is the C9 (意图自检) action, and it is the whole point:

> 你这个问题预设了「X」。你是想**验证 X 成不成立**，还是想**弄清事情为什么变成这样**？

Options: `验证 X` / `弄清原因（推荐）` / `X 是我确认过的事实，不用验证`. The third option is legitimate and must be offered — sometimes the premise really is established, and the skill records it as a stated fact rather than a hidden assumption.

**Ask the C10 (目的层) question only when the ask is locked onto one method:**

> 你要「X」是为了达成什么？如果目标是 Y，X 是唯一的路子吗？

Fires on asks shaped like 「怎么才能节食减肥」— method fixed, goal unexamined. Do not fire it on every ask; asked reflexively it reads as stalling.

**Then fill the C4/C5/C6/C7 gaps** with concrete, answerable questions — 具体型号是什么 / 之前什么时候还是正常的 / 你自己试过什么、结果如何. Never more than what the rewrite actually needs.

Every AUQ call includes an escape option: `跳过，直接按现有信息改写`. Honor it immediately — do not re-ask.

## Phase 3 — Rewrite

Load `references/rewrite-template.md`. Emit, in this order:

1. **诊断摘要** — 3 lines max. What the original ask presupposed, and what it left out.
2. **改写后的问题** — one copy-paste block, built from the template. Neutral narration, timeline, concrete symptoms, ruled-out factors, then a single open-ended What/Why/How closer.
3. **仍然缺失** — any gap the user skipped, marked `[待你补充]` inside the block itself so it stays visible when pasted.
4. If the rewritten question is a high-stakes coding prompt, one line: `→ 想进一步打磨措辞，可交给 /jack-prompt-master`. One line, no elaboration.

## Hard rules

- NEVER answer the user's question in this skill. Producing the answer defeats the diagnosis — the user pastes the rewritten question wherever they want and gets a better answer there.
- NEVER delete a premise the user confirmed as established fact. Move it into the narration as a stated fact, with attribution: 「据我确认，X」.
- NEVER fabricate a symptom, timestamp, model number, or ruled-out factor to fill a gap. `[待你补充]` is the only allowed filler.
- NEVER exceed `MAX_AUQ_CALLS`. If the ask is still under-specified, ship the rewrite with `[待你补充]` markers.
- NEVER score C9/C10 as PASS/FAIL. They are unknowable from text — they are interview actions only.
- Respond in the user's language.

## Reference files

Load on demand:

- `references/checklist.md` — C1–C10 criteria: 原则 / 判定信号 / 反例特征 / 改写动作, with the source passage for each.
- `references/rewrite-template.md` — the structured-question template plus two worked examples (coding + 生活).

## Distinctness vs other prompt skills

- `jack-meta-think` (this skill): upstream, domain-general. Fixes what you are asking.
- `jack-prompt-master`: downstream, coding-only, multi-round tournament. Fixes how you word it.
- `/prompt-enhance`, `prompt-master`: one-shot wording polish.

No auto-chaining in either direction. Each ships a copy-paste block; the user routes it.
