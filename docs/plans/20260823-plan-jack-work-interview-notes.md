# Plan：将 `interview-notes-enricher` 移植为 `jack-work` 插件的 `interview-notes` Skill

**日期**：2026-08-23（v1） · **修订**：2026-08-23（v2，范围收缩）
**状态**：可执行。4 项待定决策已在 v2 中拍板（见下节），重设计部分推迟至 0.2.0
**来源**：`analyst-pro-plugins/analyst-dd/commands/interview-notes-enricher.md`
**生成方式**：`/jack-prompting:jack-prompt-master`（3 轮，7/7）精炼提示词 → Opus subagent 只读执行 → `/cc-suite:review-plan` 评审 → 按 must-fix 收缩
**只读声明**：本计划本身未在任何仓库写入、创建、移动或删除文件

---

## 修订说明（v2）— 收缩为 parity-first

v1 经 Codex 五维评审（`gpt-5.6-sol` · effort high · thread `01a02d9f-431b-75c0-9dae-9b8d2c343690`）判定 **NEEDS REVISION**，23 条 finding。v2 按"最小改动"处理：修 5 条 must-fix，把重设计推到 0.2.0，其余 should-fix 就地修正并在正文标注。

**v1 的核心问题**：名义上是移植，实际同时重构了语言处理、说话人归属、问题重建、话题拆分、验证五件事。一旦跑出问题，无法区分是移植错了还是重设计错了（Codex R5#1）。

### 本次（v0.1.0）范围

| 交付 | 说明 |
|---|---|
| `SKILL.md` — 源命令的**行为等价移植** | B§2 覆盖矩阵中所有 Kept / Generalized 条目，`:132` 一行除外（见 B§4a） |
| `references/profile-zh.md` | 中文约定**逐字**外移（用户明确要求的泛化第一步）。只搬不改写，否则 parity 无从校验 |
| **不破坏保证**（新增 · must-fix） | 见 B§4a。替换源命令那个会静默误报的 `git diff` 检查 |
| **候选账本 + 幂等保证**（新增 · must-fix） | 见 B§4b |
| 注册三件套 | `plugin.json` · 根 `README.md` · `marketplace.json` |
| 两个 fixture | 中文 parity、重跑幂等 |

### 推迟到 0.2.0

| 推迟项 | v1 出处 | 理由 |
|---|---|---|
| `references/profile-en.md` | B§1 row 5 | 第二语言分支在 parity 未证明前无从验证（原 OQ 5） |
| `references/detection.md` + 六观察量 fingerprint 机制 | B§1 row 6 · B§4 | 同上。且 v1 的 row 6 是"超过 40 行才建文件"的条件创建，与验证 check #1"rows 1–7 必须存在"直接矛盾（Codex A4#2） |
| `--profile <name>` 覆盖参数 | B§4 步骤 5 | 只有一个 profile 时无意义；顺带消除 `$ARGUMENTS` 的解析歧义（Codex A4#4） |
| B§5 全部五项借鉴改进 | B§5 | 见该节标注。其中"重建隐含问题"与"标注推断的说话人"和 frontmatter 承诺的 no-fabrication 直接冲突，需要先定义 provenance 机制（Codex I1#2） |

> **范围说明（需用户知悉）**：v1 的"泛化"是用户明确要求的。v2 保留了泛化的第一步（中文约定外移到 `profile-zh.md`），但把**第二个 profile 和 fingerprint 选择器**推到 0.2.0。v0.1.0 改用源命令 `:85` 的原始形态作为风格规则：**读现有条目 → 照它写 → 偏差记进报告**。这是 detect-then-match 的最小可用版本，不需要 profile 选择器。若希望 `profile-en.md` 仍在本次交付，说一声即可恢复 B§1 row 5 与 B§4 的完整 fingerprint 流程。

### 构建顺序（带验收闸门）

1. 建 `SKILL.md` + `profile-zh.md`，只做行为等价移植 → **闸门**：B§7 check 7 + check 12（覆盖矩阵逐条对账 + `profile-zh.md` 逐字比对）
2. 实现 B§4a 不破坏保证 → **闸门**：B§7 check 10（非 git 目录下故意触发破坏性编辑，必须自动还原）
3. 实现 B§4b 候选账本 → **闸门**：B§7 check 11（同一输入连跑两次，第二次零新增）
4. 建 `plugin.json` + 根 `README.md` → **闸门**：`claude plugin validate --strict`
5. 追加 `marketplace.json` 条目 + 顶层版本 `0.2.4 → 0.2.5`
6. `/marketplace-release` 统一处理 CHANGELOG + tag

第 2、3 步必须早于第 5 步：**行为未证明前不注册**（Codex R5#3）。

---

## A. Public interview-notes skills — ranked

**Search formulations actually run**（WebSearch unless marked; `gh` = GitHub CLI authenticated as `anzchy`, results read from the public API）:

1. `claude code skill interview notes transcript to memo`
2. `claude code plugin meeting notes transcript summarize SKILL.md github`
3. `github "SKILL.md" meeting notes transcript speaker diarization Q&A extraction claude`
4. `访谈纪要 整理 claude code skill 提示词 github`
5. `"user research" interview transcript synthesis claude code skill incremental append github`
6. `gh search repos "claude skill interview transcript memo"` → 0 results
7. `gh search repos "interview transcript claude skill"` → 0 results
8. `gh search repos "meeting notes claude code plugin"` → 0 results
9. `gh search code "访谈纪要 extension:md"` → 20 hits (highest-yield query of the set)
10. `gh search code "interview transcript filename:SKILL.md"` → 20 hits
11. `gh search code "\"already in the memo\" filename:SKILL.md"` → 9 hits
12. `gh search code "\"additive only\" filename:SKILL.md"` → 20 hits (all software-engineering skills; no notes tooling)
13. `gh search code "\"访谈\" \"Q：\" filename:SKILL.md"` → 11 hits
14. `gh search code "访谈纪要 path:.claude/commands"` → **0 hits**（this space has no slash-command prior art）
15. `gh search code "transcript \"do not delete\" filename:SKILL.md"` → 15 hits
16. WebFetch on `dgalarza/claude-code-workflows/plugins/meeting-transcript/README.md` and `claude-office-skills/skills/meeting-notes/SKILL.md`
17. Direct `gh api repos/{owner}/{repo}` + `gh api .../contents/.../SKILL.md` reads for every row below

Note on coverage: `gh search repos` returned empty for all three natural-language repo queries, so repo-level discovery came from WebSearch and code search. Several search-snippet results (`sgharlow/claude-code-recipes` Recipe-090, `AntaresYuan/claude-skill-interview-sim`, `nord342/claude-meeting-notes`, `GarisonLotus/m4a-audio-meeting-transcription`, `glebis/claude-skills`, `laolaoshiren/claude-code-skills-zh`, `yunshu0909/yunshu_skillshub`) are **excluded** — either the artifact page was not opened, or they are audio-transcription / synthetic-interview-generation tools rather than transcript→memo sync. The table is not padded.

| # | Name | Repo / URL | Stars | Stars read on | Last commit | Kind | Relevance to incremental transcript→memo sync | Borrowable idea |
|---|---|---|---|---|---|---|---|---|
| 1 | `meeting-minutes-taker` | https://github.com/daymade/claude-code-skills/blob/main/daymade-audio/meeting-minutes-taker/SKILL.md | 1346 | 2026-08-23 | 2026-08-23 (API `pushed_at`) | claude-skill | **High** — its own `description` names "multiple versions of minutes must be merged without losing content" and "existing minutes need review against the original transcript for missing items", which is exactly the source command's job | Final omission sweep: after drafting, "Compare draft against transcript, add omissions"; plus a source-side speaker-labeling gate before any speaker inference |
| 2 | `interview-qa-minutes` | https://github.com/Jackhammer1024/Skills-for-Primary-Market-/blob/main/interview-qa-minutes/SKILL.md | 0 | 2026-08-23 | 2026-06-05 (API `pushed_at`) | other — Codex CLI skill authored in SKILL.md format | **High** — Chinese investment-research Q&A memo with full-width `Q：/A：`, and Workflow step 7 is literally "if the user provides another version of minutes, compare it against the transcript, add omitted important information into the Q&A version, and avoid duplicating content already covered" | Two rules the source lacks: reconstruct a concise question when the transcript's question is implicit; split one answer covering unrelated topics into separate Q&A pairs |
| 3 | `user-research-cookiy` | https://github.com/cookiy-ai/user-research-skill/blob/main/SKILL.md | 1504 | 2026-08-23 | 2026-08-19 (API `pushed_at`) | claude-skill | Medium — has a "Route B: Synthesize" branch for "has transcripts/notes, needs a report", but produces a report, not an additive edit of an existing memo | Explicit intent-routing table at the top of the skill, with "if ambiguous, ask one clarifying question" |
| 4 | `dd-interview-minutes` | https://github.com/aifinlab/FinClaw/blob/main/skills/dd-interview-minutes/SKILL.md | 228 | 2026-08-23 | 2026-05-13 (API `pushed_at`) | claude-skill | Medium — same domain (尽调访谈纪要, 投行/律所/会所), same `### 3.1 [主题]` + `**问**：/**答**：` shape, but generates a fresh memo each run with no diff-against-existing step | Ships `references/interview-templates.md` and `references/interview-checklist.md` as sibling reference files — direct precedent for putting format conventions outside SKILL.md |
| 5 | `访谈纪要` | https://github.com/ahang1598/doubao-workbuddy-qwenwork-skills/blob/main/qwenwork/experts/consulting-delivery/skills/访谈纪要/SKILL.md | 10 | 2026-08-23 | 2026-08-20 (API `pushed_at`) | other — Qwen/Doubao office-agent skill in SKILL.md format | Medium — Chinese consulting-grade interview memo with an explicit fidelity rule ("忠实于原始记录，不添加受访者未表达的观点"), but one-shot generation | Bilingual frontmatter (`name`/`name_en`, `description`/`description_en`) as an explicit multi-language affordance; four-tier credibility marking (Fact/Claim/Inference/Confidential) |
| 6 | `extract` | https://github.com/dcurlewis/ai-context-system/blob/main/.claude/skills/extract/SKILL.md | 5 | 2026-08-23 | 2026-04-08 (API `pushed_at`) | claude-skill | Medium — an additive-into-existing-files pipeline ("the 3-10 items from a conversation that would change or add to the memory files, not to document everything"), but over conversation memory, not interview transcripts | Framing the run as *triage against an existing document* rather than *summarization*, with an explicit "do NOT run this after…" negative-trigger list |
| 7 | `jtbd-interview` | https://github.com/savvides/jtbd/blob/main/jtbd-interview/SKILL.md | 0 | 2026-08-23 | 2026-04-28 (API `pushed_at`) | claude-skill | Medium — repo turns "customer interview transcripts into structured, version-controlled demand evidence"; the skill preamble enumerates an accumulating `.jtbd/switches/*.yml` store, so state grows across interviews | A shell **preamble block** that probes the working directory (store present? git present? manifest? how many existing records?) and prints the findings before any reasoning starts |
| 8 | `meeting-notes` | https://github.com/claude-office-skills/skills/blob/main/meeting-notes/SKILL.md | 403 | 2026-08-23 | 2026-01-31 (API `pushed_at`) | claude-skill | Low — transcript → decisions/action-items/attendees table; no incremental update, no Q&A turn extraction (confirmed by WebFetch) | Declares supported languages as `en, zh` in the skill itself, then asks the user for format preferences rather than inferring |
| 9 | `meeting-transcript` plugin | https://github.com/dgalarza/claude-code-workflows/blob/main/plugins/meeting-transcript/README.md | 59 | 2026-08-23 | 2026-06-05 (API `pushed_at`) | claude-plugin | Low — WebFetch confirms it "generates a new formatted file rather than incrementally updating existing notes" | Preservation whitelist ("Preserve links — Notion docs, Linear issues, GitHub PRs mentioned; preserve architecture discussions, API names") as a named category of must-not-drop content |
| 10 | `transcript-critic` | https://github.com/jftuga/transcript-critic | 34 | 2026-08-23 | 2026-04-30 (API `pushed_at`) | claude-skill | Low — audio/video → critical analysis with timestamped summaries and evidence notes; upstream of the source's problem, not the same problem | Naming "underdeveloped areas" as a first-class output — a thin-answer signal the source only handles implicitly |
| 11 | `youtube-podcast-transcribe` | https://github.com/MEIQI-Lee/youtube-podcast-transcribe/blob/main/SKILL.md | 3 | 2026-08-23 | 2026-04-12 (API `pushed_at`) | other — OpenClaw agent skill in SKILL.md format | Low — produces "结构化 Q&A 中文文档" preserving 原访谈的问答形式, so it shares the output shape only | Prefers a source that already carries speaker labels over deriving them, and says so as an ordered fallback ladder |

*`Last commit` is reported from the GitHub API's `pushed_at` field, read on 2026-08-23. Per-commit pages were not opened, so the field is labelled precisely rather than claimed as a commit timestamp.*

### What this space does that the source command does not

**Direct evidence (quoted from the public artifact and the source file):**

- **Post-edit omission sweep against the transcript.** `daymade/claude-code-skills` `meeting-minutes-taker` ends its generation step with "Final: Compare draft against transcript, add omissions" and then a separate Step 3 self-review. The source's Phase 6 (`interview-notes-enricher.md:130-139`) verifies only that the *diff is additive* — `git diff -- <MEMO_PATH>` and a report — and never re-reads the transcript to check that nothing was left behind. Recall failure is invisible in the source's verification.
- **Source-side speaker labeling before inference.** `meeting-minutes-taker` Step 1.5 Phase 0 says to "stop and ask the user to label the speakers at the source… then re-export/re-ingest the labeled transcript," and falls back to inference only if the user consents or the source cannot be labeled. The source command jumps straight to inference from names: Q candidates are "lines from investor-side or interviewer speakers (typically named `XXX 公司`, or just a name like `成勇`, `岳磊磊`)" (`interview-notes-enricher.md:108`). It has no branch for a transcript labelled `发言人1 / Speaker 2`.
- **Reconstructing an implicit question.** `Jackhammer1024/.../interview-qa-minutes/SKILL.md` Editing Rules: "When a question is unclear in the transcript, reconstruct a concise question from the answer's topic." The source only recognises Q candidates that are explicit questions — "ending in `？`/`?`, or starting with '那 / 你们 / 比如说 / 现在 / 能不能 / 是不是 / 有没有 / 怎么 / 如何'" (`:108`) — so a volunteered answer with no matching question is silently dropped.
- **Splitting a multi-topic answer.** Same file: "When one answer covers multiple unrelated topics, split it into separate Q&A pairs under the right themes." The source only merges — "Merge multi-turn answers on the same topic into one `A：` block" (`:110`) — with no inverse operation, which matters because Phase 4 places each candidate under one `### N.M` sub-section (`:121`).
- **Cross-memo dedup as a named workflow step.** `interview-qa-minutes` Workflow step 7 makes "compare it against the transcript…, add omitted important information…, and avoid duplicating content already covered" a first-class step. The source has the same intent but expresses it as a keyword grep heuristic — "Grep the current memo section for the same theme (by keyword, not exact string)" (`:119`) — with no rule for near-duplicates that share no keyword.
- **Reference files as the home for format conventions.** `aifinlab/FinClaw` ships `skills/dd-interview-minutes/references/interview-templates.md` and `.../references/interview-checklist.md` alongside its SKILL.md. The source hard-codes all Chinese conventions inline in its Style Contract (`:69-85`) and Phase 3 (`:108`), so they cannot be swapped for another language.
- **Explicit multi-language declaration.** `ahang1598/.../访谈纪要/SKILL.md` carries paired `name`/`name_en` and `description`/`description_en` frontmatter; `claude-office-skills` `meeting-notes` declares `"en, zh"`. The source's frontmatter declares no language and its `description` mixes Chinese triggers into an English sentence (`:3`), while its body assumes Chinese headings throughout (`:48, :65, :95, :102`).
- **Working-directory probe as a shell preamble.** `savvides/jtbd` `jtbd-interview` opens with a bash block that detects `.jtbd/`, git, gstack, reads a manifest and counts existing records before any reasoning. The source's preflight does check cwd and writability (`:19, :23`) but its auto-detection lives inside Step 0's prose (`:29-41`) and its findings are never printed as a single structured block before the AskUserQuestion.

**Inference (not directly stated by the public artifact):**

- A four-tier credibility scheme (`ahang1598`: Fact/Claim/Inference/Confidential) is *more granular* than the source's single hedge marker `访谈口径是…` (`:81, :145`), but it would likely violate the source's own rule that "New Q&A must look indistinguishable from existing entries" (`:83`) if applied to a memo that has only ever used one hedge form.
- The absence of any `gh search code "访谈纪要 path:.claude/commands"` hit suggests — but does not prove — that this space has converged on the skill format rather than slash commands, which is consistent with the port target chosen here.

---

## B. Conversion plan

### Collision gate — PASSED

**Observed 2026-08-23:** `ls plugins` returns `jack-engineering/ jack-git/ jack-html-preview/ jack-prompting/ songy-course-exporter/ writing-truth/` — no `jack-work`. `grep -rn "jack-work" .` over the repo returns nothing, and the live `.claude-plugin/marketplace.json` `plugins[]` array contains exactly six entries, none named `jack-work`. No collision; registration metadata is proposed below.

**Snapshot verification:** `find plugins -type d -name commands` returns nothing（确认目标形态为 skill 而非 command）。`find plugins -name SKILL.md` returns exactly 16 files。Marketplace top-level `version` live-read as `0.2.4`。

### Live source inventory — `analyst-dd/commands/interview-notes-enricher.md`

Read in full via `cat -n`. Frontmatter is `:1-7` and contains exactly **five** keys — `name`, `description`, `argument-hint`, `model`, `allowed-tools`. `:21` confirms verbatim: *"this command does not consume any `${CLAUDE_PLUGIN_ROOT}/knowledge/` files. Skip this check."* — 因此**没有任何 reference file 需要一并移植**。

| Line | Item |
|---|---|
| `:1-7` | Frontmatter (5 keys) |
| `:9` | HTML comment — build-provenance marker ("manual-handwritten mode… Do NOT regenerate via build-from-source.ts") |
| `:11` | H1 `# Interview Notes Enricher` |
| `:13` | One-line lede |
| `:15-23` | `## Failure Mode Preflight (hard-fail by default)` — 3 numbered checks |
| `:25-67` | `## Step 0: Parameter Collection (replaces 矽睿-hardcoded values)` — 4 numbered items |
| `:69-85` | `## Style Contract (match the existing memo exactly)` — 6 bullets + a fallback paragraph |
| `:87-89` | `## Workflow` — wrapper heading + ordering rule |
| `:91-97` | `### Phase 1 — Scope` — 5 rules |
| `:99-102` | `### Phase 2 — Read` — 2 rules |
| `:104-113` | `### Phase 3 — Extract Candidate Q&A from Transcript` — 4 bullets + a no-write rule |
| `:115-121` | `### Phase 4 — Diff Against Memo` — 3 rules |
| `:123-128` | `### Phase 5 — Apply Edits` — 4 rules |
| `:130-139` | `### Phase 6 — Verify & Report` — 2 rules + brevity note |
| `:141-148` | `## Editing Rules (hard constraints)` — 6 rules |
| `:150-158` | `## Common Pitfalls` — 7 bullets |
| `:160-165` | `## Completion Criteria` — 4 bullets |
| `:167-171` | `## Output Location` — 2 paragraphs |

### B§1 — Files to create

| # | Repo-relative path | Action | Purpose |
|---|---|---|---|
| 1 | `plugins/jack-work/.claude-plugin/plugin.json` | create | Plugin manifest (`name`, `version: 0.1.0`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`) — required by `README.md:65` step 1 |
| 2 | `plugins/jack-work/README.md` | create | Plugin-level readme. **Corrected (Codex I1#4):** 4 of the 6 live plugins have one (`jack-html-preview` and `songy-course-exporter` do not) — desirable documentation, not an invariant |
| 3 | `plugins/jack-work/skills/interview-notes/SKILL.md` | create | The ported skill — transcript→memo additive sync (user-stated placement) |
| 4 | `plugins/jack-work/skills/interview-notes/references/profile-zh.md` | create | The Chinese memo conventions lifted **verbatim** out of the source's inline text. Relocation only — no rewording, so B§2 parity stays checkable |
| 5 | `docs/fixtures/interview-notes/` | create | **New in v2.** Two sanitized fixture pairs (memo + transcript) driving B§7 checks 10–11. Lives under `docs/` because `README.md` marks that tree "not installed" — fixtures must not ship to users |
| 6 | `.claude-plugin/marketplace.json` | update | Append the `jack-work` entry and bump the top-level `version` — required by `README.md` step 2 |
| 7 | `README.md` (repo root) | update | The root README carries a plugin table (`README.md:22`), an install list (`:32-36`, mirrored in Chinese at `:98-102`) and a repository-structure block (`:44-56`); leaving `jack-work` out would make three sections stale |

**Removed from v1:** rows 5–6 (`profile-en.md`, `detection.md`) → deferred to 0.2.0. Row 9 (`CHANGELOG.md`) → **owned by `/marketplace-release`**, which sets marketplace version + CHANGELOG heading + git tag atomically. v1 both claimed this file and delegated it, while verification still required it (Codex I1#1).

Files **not** created: no `knowledge/` dir (the source consumes none — `:21`); no `commands/` dir (none exists anywhere under `plugins/`); no scripts.

**`references/` vs `reference/` — the pick.** Live evidence: `references/` at `plugins/jack-prompting/skills/jack-meta-think/references/` and `plugins/jack-prompting/skills/jack-prompt-master/references/`; `reference/` at `plugins/jack-prompting/skills/jack-loop-prompt/reference/` and `plugins/jack-html-preview/reference/`. **Corrected in v2:** the `jack-html-preview` one sits at *plugin root*, not as a skill sibling — among skill-level siblings it is 2 `references/` vs 1 `reference/`, not the tie v1 conceded. Tie-breakers: (a) `git log --diff-filter=A` dates the `jack-prompt-master/references` tree to **2026-08-23** versus **2026-08-22** for `jack-loop-prompt/reference` — `references/` is the more recently authored convention; (b) external convention agrees — `anthropics/knowledge-work-plugins` uses `skills/create-cowork-plugin/references/`, and `aifinlab/FinClaw` uses `skills/dd-interview-minutes/references/`. **Pick: `references/`.** 仓库自身的不一致未解决，见 Open questions。

### B§2 — Source-to-target coverage matrix

| Source item | Source citation | Target location | Treatment | Reason |
|---|---|---|---|---|
| Build-provenance HTML comment ("manual-handwritten mode… do not regenerate via build-from-source.ts") | `:9` | — | **Dropped** | Names a build pipeline (`build-from-source.ts`) that exists in `analyst-pro-plugins`, not here; every `SKILL.md` here is hand-written |
| H1 title `# Interview Notes Enricher` | `:11` | `SKILL.md` H1 → `# interview-notes` | **Generalized** | Every skill here titles its H1 with the skill's `name` (`jack-meta-think:6`, `rhetoric-lens:6`, `jack-html-preview:7`) |
| Lede: "Incrementally sync raw interview transcripts into a consolidated Q&A memo. Strictly additive…" | `:13` | `SKILL.md` opening paragraph | **Generalized** | Kept as the skill's thesis, with "Q&A memo" widened from the Chinese `Q：/A：` shape to "whatever Q&A shape the memo already uses" |
| Preflight 1 — cwd readable via `pwd && ls -la`, hard-fail if empty | `:19` | `SKILL.md` § Preflight | **Kept** | Still needed; the skill edits a file in the user's cwd |
| Preflight 2 — "does not consume any `${CLAUDE_PLUGIN_ROOT}/knowledge/` files. Skip this check." | `:21` | — | **Dropped** | A no-op inherited from the `analyst-dd` command template |
| Preflight 3 — cwd writable via `.analyst-write-test` | `:23` | `SKILL.md` § Preflight | **Generalized** | Probe filename changed from `.analyst-write-test` (names the wrong plugin) to `mktemp` + `trap` cleanup — see B§4a item 5 |
| Step 0.1 — auto-detect memo file by `*纪要*final*.md *纪要-final.md *memo*.md *interview*.md`, pick largest | `:29-34` | `SKILL.md` § Step 0, Chinese globs → `references/profile-zh.md` | **Generalized** | Language-neutral globs stay in SKILL.md; `*纪要*` moves to the zh profile |
| Step 0.2 — auto-detect transcripts by `20YYMMDD-*访谈.md`, `*交流.md`, `*interview*.md` | `:36-41` | Same split as 0.1 | **Generalized + fixed (v2)** | The date-prefix pattern is language-neutral and stays. **Fix (Codex C2#4):** `*interview*.md` is used by *both* 0.1 and 0.2, so the memo can match its own transcript glob. Transcript expansion must exclude the selected `MEMO_PATH` and reject duplicate paths, and the preflight must print every candidate with its size before the confirmation question |
| Step 0.3 — `AskUserQuestion` block D1 with A/B pros-cons and Net line | `:43-60` | `SKILL.md` § Step 0 | **Generalized** | The verbose ELI10/Stakes/Net scaffold is an `analyst-dd` house style not seen in any `jack-cheng-skills` SKILL.md — compressed to a plain two-option question |
| Step 0.3 — collect `MEMO_PATH`, `TRANSCRIPT_GLOB`, `PROJECT_NAME` | `:62-65` | `SKILL.md` § Step 0 | **Kept** (MEMO_PATH / TRANSCRIPT_GLOB); **Dropped** (PROJECT_NAME) | The source itself marks `PROJECT_NAME` "informational only" (`:65`) — collected and never used |
| Step 0.4 — `$ARGUMENTS` non-empty ⇒ scope to that interviewee; else second AskUserQuestion before batch | `:67` | `SKILL.md` § Inputs | **Kept** | See §3 for the full `$ARGUMENTS` trace |
| Style Contract — full-width `：` in Q/A markers | `:73` | `references/profile-zh.md` | **Relocated** | Chinese conventions live in a named profile |
| Style Contract — bold Q line / plain A line, exact `**Q：<问题>？**` + `A：<回答…>` block | `:74-79` | `references/profile-zh.md` | **Relocated** | Same |
| Style Contract — sub-sections `### N.M 主题`; place under the most relevant existing sub-section | `:80` | Placement rule → `SKILL.md`; heading regex → `references/profile-zh.md` | **Generalized + Relocated** | The *placement discipline* is language-agnostic; the *heading shape* is not |
| Style Contract — `访谈口径是…` / `访谈口径约…` hedge prefix | `:81` | Hedge *concept* → `SKILL.md`; the two Chinese strings → `references/profile-zh.md` | **Generalized + Relocated** | Every profile needs a hedge phrase; only Chinese needs these exact words |
| Style Contract — keep figures (`亿元 / 万美金 / %`) verbatim; do not round or convert | `:82` | `SKILL.md` § Editing rules | **Generalized** | Rule is universal; the unit examples become profile examples |
| Style Contract — no emojis; no "补充"/"新增" headings; new Q&A indistinguishable from existing | `:83` | Rule → `SKILL.md`; the two Chinese heading words → `references/profile-zh.md` | **Generalized + Relocated** | Same split |
| Style Contract fallback — if the memo uses a different style, match it and record the deviation | `:85` | `SKILL.md` § Detect-then-match | **Generalized** | This is the seed of the whole generalization (see §4) — promoted from a footnote to the governing rule |
| `## Workflow` wrapper — "Follow these phases in order… do not skip ahead" | `:87-89` | `SKILL.md` § Workflow | **Kept** | Ordering discipline is the skill's spine |
| Phase 1.1 — confirm interviewee(s) from `$ARGUMENTS`/AskUserQuestion | `:93` | `SKILL.md` Phase 1 | **Kept** | — |
| Phase 1.2 — Glob transcripts matching Chinese name OR pinyin OR role keyword | `:94` | Matching *strategy* → `SKILL.md`; "pinyin" → `references/profile-zh.md` | **Generalized + Relocated** | Pinyin is a Chinese-specific romanization step |
| Phase 1.3 — Grep memo for `## 访谈 \d+ \| <name>` or `## .*<name>.*\|`; "be liberal" | `:95` | Liberal-grep instruction → `SKILL.md`; both regexes → `references/profile-zh.md` | **Generalized + Relocated** | The regexes encode `访谈`; the liberality rule does not |
| Phase 1.4 — multiple transcripts match ⇒ ask the user | `:96` | `SKILL.md` Phase 1 | **Kept** | — |
| Phase 1.5 — no transcript matches ⇒ hard-fail listing unmatched names + the glob searched | `:97` | `SKILL.md` Phase 1 | **Kept** | — |
| Phase 2.1 — read the whole transcript, chunking if needed; coverage before editing | `:101` | `SKILL.md` Phase 2 | **Kept** | — |
| Phase 2.2 — read the memo section from `## 访谈 N \| <name>` to the next `## 访谈` or `---` | `:102` | Boundary *concept* → `SKILL.md`; Chinese delimiters → `references/profile-zh.md` | **Generalized + Relocated** | "Read to the next same-level heading or horizontal rule" is language-agnostic |
| Phase 3 — Q candidates: interviewer-side speakers, `？`/`?` endings, openers `那 / 你们 / 比如说 / 现在 / 能不能 / 是不是 / 有没有 / 怎么 / 如何` | `:106-108` | Speaker-role heuristic → `SKILL.md`; punctuation + nine openers → `references/profile-zh.md` | **Generalized + Relocated** | The opener list is the single most language-bound rule in the file |
| Phase 3 — A candidates: response immediately following, possibly spanning turns | `:109` | `SKILL.md` Phase 3 | **Kept** | — |
| Phase 3 — merge multi-turn same-topic answers into one `A：` block, preserving wording | `:110` | `SKILL.md` Phase 3 (marker parameterized by profile) | **Generalized** | Merge rule universal; marker glyph is not |
| Phase 3 — discard chit-chat, scheduling, AV setup, off-topic asides | `:111` | `SKILL.md` Phase 3 | **Kept** | — |
| Phase 3 — produce `(question_theme, transcript_quote)` pairs in context; do not write yet | `:113` | `SKILL.md` Phase 3 | **Kept** | — |
| Phase 4.1 — Grep memo by keyword (not exact string); equivalent content ⇒ skip | `:119` | `SKILL.md` Phase 4 | **Kept** | — |
| Phase 4.2 — thinner existing answer + concrete transcript detail ⇒ queue addition under the same Q, or a follow-up Q | `:120` | `SKILL.md` Phase 4 | **Kept** | — |
| Phase 4.3 — theme absent ⇒ new Q&A under the most relevant `### N.M` sub-section | `:121` | `SKILL.md` Phase 4 | **Generalized** | Sub-section shape resolved from the active profile |
| Phase 5.1 — `Edit` with enough surrounding context; insert where it logically belongs, not at the end | `:125` | `SKILL.md` Phase 5 | **Kept** | — |
| Phase 5.2 — keep transcript wording; light filler cleanup (`那个 / 就是 / 对对对`) allowed; no summarizing rewrite | `:126` | Rule → `SKILL.md`; filler list → `references/profile-zh.md` | **Generalized + Relocated** | Filler words are per-language by definition |
| Phase 5.3 — never delete or rewrite existing lines unless the user asks for a factual correction | `:127` | `SKILL.md` Phase 5 | **Kept** | Core invariant |
| Phase 5.4 — do not renumber sub-sections or `## 访谈 N` headings; preserve intentional gaps | `:128` | `SKILL.md` Phase 5 | **Generalized** | "Do not renumber; preserve gaps" is universal; the heading token is not |
| Phase 6.1 — `git diff -- <MEMO_PATH>` additive-only check; skip if not a git repo | `:132` | `SKILL.md` Phase 6 | **Replaced (v2)** | The condition is unsound: an untracked or out-of-worktree memo yields an empty diff and a false "✓ additive". Superseded by the snapshot check in **B§4a**; `git diff` is retained only as supplementary display |
| Phase 6.2 — report: section updated, count added, one-line summaries, style deviations | `:133-137` | `SKILL.md` Phase 6 | **Kept** | — |
| Phase 6 — "Keep the report brief; the diff is the source of truth" | `:139` | `SKILL.md` Phase 6 | **Kept** | — |
| Editing Rule — **Additive only** by default; removals require explicit instruction | `:143` | `SKILL.md` § Hard constraints | **Kept** | — |
| Editing Rule — **One section at a time**; no batch multi-interviewee edits unless asked | `:144` | `SKILL.md` § Hard constraints | **Kept** | — |
| Editing Rule — **Wording fidelity**; prefer transcript phrasing; mark ambiguity with `访谈口径是…` | `:145` | Rule → `SKILL.md`; the phrase → `references/profile-zh.md` | **Generalized + Relocated** | — |
| Editing Rule — **Style match**; detect the memo's Q/A marker style and match exactly | `:146` | `SKILL.md` § Detect-then-match | **Generalized** | "Full-width `：` is most common" becomes a *profile-zh* default, not a global default |
| Editing Rule — **Traceability**; every new Q&A backed by specific transcript text | `:147` | `SKILL.md` § Hard constraints | **Kept** | — |
| Editing Rule — **No fabrication**; do not infer numbers, dates, or names not in the transcript | `:148` | `SKILL.md` § Hard constraints | **Kept** | — |
| Pitfall — mixing half-width and full-width colons in one memo | `:152` | `SKILL.md` § Pitfalls, restated as "mixing two marker styles"; colon example → `references/profile-zh.md` | **Generalized + Relocated** | — |
| Pitfall — appending new Q&A at the bottom instead of the relevant `### N.M` sub-section | `:153` | `SKILL.md` § Pitfalls | **Generalized** | Sub-section token profile-resolved |
| Pitfall — summarizing a 5-minute answer into one sentence | `:154` | `SKILL.md` § Pitfalls | **Kept** | — |
| Pitfall — treating interjections (`嗯`, `对对对`, `好的`) as questions | `:155` | Rule → `SKILL.md`; the three tokens → `references/profile-zh.md` | **Generalized + Relocated** | — |
| Pitfall — rewriting existing Q&A as an `Edit` side effect; scope `old_string` to the anchor only | `:156` | `SKILL.md` § Pitfalls | **Kept** | — |
| Pitfall — renumbering around an intentionally-skipped section number | `:157` | `SKILL.md` § Pitfalls | **Kept** | — |
| Pitfall — assuming the memo is in a git repo | `:158` | `SKILL.md` § Pitfalls | **Kept** | — |
| Completion — scoped interviewee section updated in place | `:162` | `SKILL.md` § Completion criteria | **Kept** | — |
| Completion — all added content traceable, naming the source transcript filename per addition | `:163` | `SKILL.md` § Completion criteria | **Kept** | — |
| Completion — all pre-existing content preserved byte-for-byte | `:164` | `SKILL.md` § Completion criteria | **Kept** | — |
| Completion — final response states interviewee name, sub-sections touched, added-theme bullets | `:165` | `SKILL.md` § Completion criteria | **Kept** | — |
| Output Location — edits the memo in place at `MEMO_PATH`; "the memo file is the user's, not a plugin artifact" | `:169` | `SKILL.md` § Output | **Generalized** | The "per-domain output dir" clause is an `analyst-dd` concept with no counterpart here |
| Output Location — if the user wants the original preserved, ask them to commit or back up first | `:171` | `SKILL.md` § Output | **Kept** | — |

### B§3 — Frontmatter and invocation mapping

| Source key | Observed value | Treatment | Target location | Reason |
|---|---|---|---|---|
| `name` | `interview-notes-enricher` (`:2`) | **kept**, renamed to `interview-notes` | `SKILL.md` frontmatter | Skill `name` matches its directory in all 16 live examples |
| `description` | The 5-line trigger paragraph at `:3` | **kept**, rewritten | `SKILL.md` frontmatter | Rewrite must (a) drop the Chinese-only assumption while keeping the Chinese trigger words `整理 / 补充 / 扩写 / 继续 / 更新 访谈纪要` — the repo already mixes languages here (`rhetoric-lens:3`, `jack-meta-think:3`), and (b) name the additive contract |
| `argument-hint` | `"[interviewee name — optional, defaults to all]"` (`:4`) | **kept**, reworded | `SKILL.md` frontmatter | Live evidence: `jack-audit-fable/SKILL.md:4` and `jack-review-plan-fable/SKILL.md:4` both carry it. **v2:** the `--profile zh\|en` flag v1 put here is dropped — it advertised `profile-en.md`, which OQ 5 left open to being cut (Codex A4#1/A4#2) |
| `model` | `sonnet` (`:5`) | **dropped** | — | `grep -n '^model:'` returns **zero** hits across all 16 live skills. No precedent in this repo |
| `allowed-tools` | `Read, Write, Edit, Grep, Glob, AskUserQuestion, Bash` (`:6`) | **kept**, as a YAML list, minus `Write` | `SKILL.md` frontmatter | Live: `jack-auto-fix/SKILL.md:6` and `jack-audit-branches/SKILL.md:8` declare it as a block list. `Write` dropped because the source edits in place and creates nothing (`:169`); granting `Write` contradicts the additive-only invariant at `:143` |
| *(added)* `version` | not present in source | **new key** | `SKILL.md` frontmatter, `version: 0.1.0` | Required by `CLAUDE.md` and `README.md:57`. Present in 8 of 16 live skills |

**`disable-model-invocation`** is *not* proposed. `jack-ask/SKILL.md:4` and `jack-loop-prompt/SKILL.md:5` set it, but both are explicitly manual-only tools. The source's `description` (`:3`) is written to fire on natural-language triggers.

**`$ARGUMENTS` trace.** Three occurrences in the source:

- `:47` — inside the AskUserQuestion display block: `Project/branch/task: $ARGUMENTS (or "all interviewees" if blank)`
- `:67` — the scoping rule: *"If `$ARGUMENTS` is non-empty, scope all subsequent phases to that interviewee only. Otherwise prompt the user via a second AskUserQuestion before processing all interviewees in batch (rarely the right default — usually one-at-a-time)."*
- `:93` — Phase 1 step 1, re-reading the scope from `$ARGUMENTS` or Step 0

**How input reaches a skill here.** `$ARGUMENTS` is the live mechanism, used by 7 of 16 skills: `jack-html-preview/SKILL.md:11`, `jack-loop-prompt/SKILL.md:12`, `jack-meta-think/SKILL.md:43`, `jack-prompt-master/SKILL.md:65,70,72`, `jack-audit-fable/SKILL.md:27,46`, `jack-review-plan-fable/SKILL.md:32,37`, `dissect-author-mind/SKILL.md:11`. The `$ARGUMENTS` token ports across unchanged.

Proposed handling (all three branches):

- **A named interviewee** — the skill body reads `$ARGUMENTS`. Repo precedent for arg-parsing: `jack-audit-fable/SKILL.md:46` ("Parse `$ARGUMENTS` for `--full` or `--mini`…"), `jack-review-plan-fable/SKILL.md:37`.
- **When none is named**, do not batch. Repo precedent: `jack-meta-think/SKILL.md:43` — empty `$ARGUMENTS` triggers an `AskUserQuestion`, and a still-empty answer prints a usage line and exits. Proposed adaptation: Step 0 enumerates the memo's interviewee sections and offers them as `AskUserQuestion` options — strictly better than the source's free-text second question at `:67`, because the options are read from the memo the skill just parsed.
- **Multiple interviewees — resolved in v2 (original OQ 6).** v0.1.0 treats the **whole of `$ARGUMENTS` as exactly one interviewee name**. No space-splitting, no flags, no list syntax. If the name matches more than one memo section, `AskUserQuestion` with the matches as options; to process a second person, invoke the skill again. This preserves `:67` and `:144` verbatim and removes the parsing ambiguity v1 introduced — a space-separated name list collides with English names containing spaces and with `--profile` (Codex A4#4). Repeatable `--interviewee` flags are the 0.2.0 shape if batching is ever wanted.

### B§4 — Generalization（v2：只做第一步）

**Decision (user-stated):** generalize the skill; Chinese is the default; the Chinese conventions move into a named, auto-detected profile in the reference dir.

**v2 范围**：本次只交付泛化的**第一步** —— 中文约定逐字外移到 `references/profile-zh.md`，SKILL.md 的规则不再内嵌中文字符串。下面步骤 1–5 描述的 fingerprint / profile 选择器机制**整体推迟到 0.2.0**（Codex I1#3 指出：两个 profile 加"主导文种"判断是双语，不是 language-agnostic；A4#2 指出机制本身没有 schema 和阈值，无法一致执行）。

**v0.1.0 实际采用的风格规则** —— 源命令 `:85` 的原始形态，不加机制：

> 读至少两条完整的现有 Q&A 条目，照它们的写法写新条目（冒号字形、Q 行强调方式、小节标题形状、既有的模糊限定语）。若 memo 的写法与 `profile-zh.md` 的默认值不一致，**以 memo 为准**，并把偏差记进 Phase 6 报告。若现有条目少于两条，或 memo 混用了两种标记风格，**停下来 `AskUserQuestion`**，把读到的证据一并展示 —— 不猜，因为 Phase 5 写的是用户自己的文件。

这段规则不需要 profile 选择器：只有一个 profile，`profile-zh.md` 提供默认值，memo 永远优先。

<details>
<summary>以下 fingerprint 机制推迟到 0.2.0（v1 原文保留备查）</summary>

Proposed control flow in `SKILL.md`:

1. **Fingerprint the memo** (Phase 0.5, new). Sample existing entries and record six observables: (a) script/language of the body text, (b) colon glyph in the Q/A markers (`：` vs `:`), (c) Q-line emphasis (bold vs plain), (d) the `##` interview-heading regex and its separator, (e) the `###` sub-section numbering shape, (f) the hedge phrase already in use, if any.
2. **Select a profile** from `references/` by matching that fingerprint. `profile-zh.md` is the **default** when the memo body is predominantly Chinese.
3. **The memo always wins over the profile.** A profile supplies defaults *only for observables the memo does not exhibit*. Where they disagree, follow the memo and record the deviation in the final report. This is the source's own rule at `:85`, promoted.
4. **Ambiguous detection** — the memo is empty, has fewer than two existing Q&A entries, or mixes two marker styles: do **not** guess. `AskUserQuestion` with the candidate profiles as options plus "match the first existing entry", echoing the fingerprint evidence. Guessing wrong writes into the user's file, and `:143`/`:127` make writes hard to undo.
5. **User override.** Proposed: `$ARGUMENTS` accepts `--profile <name>` (same parse pattern as `jack-audit-fable/SKILL.md:46`), which pins the profile and skips step 2 but does **not** skip step 3 — an explicit profile still yields to the memo's observed style, because `:83` requires new entries to be indistinguishable from existing ones.

**Chinese conventions relocated to `references/profile-zh.md`:**

| Convention | Source line |
|---|---|
| `## 访谈 N \| 姓名 · 角色` interview heading | `:48`, `:65`, `:95`, `:102`, `:128` |
| `### N.M 主题` sub-section (e.g. `### 1.2-1.3 成本结构与供应链`) | `:80`, `:121`, `:153` |
| Full-width `：` in `**Q：**` / `A：` markers | `:73`, `:74-79`, `:146`, `:152` |
| `访谈口径是…` / `访谈口径约…` hedge | `:81`, `:145` |
| Question openers `那 / 你们 / 比如说 / 现在 / 能不能 / 是不是 / 有没有 / 怎么 / 如何` and `？` | `:108` |
| Interjections that are **not** questions: `嗯`, `对对对`, `好的` | `:155` |
| Filler safe to trim: `那个 / 就是 / 对对对` | `:126` |
| Units kept verbatim: `亿元 / 万美金 / %` | `:82` |
| Forbidden section labels `补充` / `新增` | `:83` |
| Memo-file globs `*纪要*final*.md`, `*纪要-final.md` | `:32` |
| Transcript globs `20[0-9][0-9][01][0-9][0-3][0-9]-*访谈.md`, `*交流.md` | `:39`, `:41` |
| Pinyin as an alternate name-matching key | `:94` |
| Section boundary: next `## 访谈` or `---` | `:102` |

**Before / after excerpt.**

*Before* — the source's Style Contract opening, quoted from `interview-notes-enricher.md:71-73` (observed):

```markdown
Read 5-10 lines of the existing memo to detect its style. Most memos in this format use:

- **Full-width colons** (`：` not `:`) in Q and A markers
```

…with the escape hatch deferred to `:85` (observed):

```markdown
If the memo uses a different style (e.g., half-width `:` markers, plain-text Q lines), match that style instead — but record the deviation in the final report.
```

*After* — **proposed**, not observed:

```markdown
## Phase 0.5 — Fingerprint, then match

Read at least two complete existing Q&A entries from the memo — not 5-10 lines,
whole entries — and record the fingerprint:

| Observable        | How to read it                                            |
|-------------------|-----------------------------------------------------------|
| body script       | dominant script of the answer text                        |
| Q/A colon glyph   | copy the exact character used after Q and A                |
| Q-line emphasis   | bold, plain, or numbered                                  |
| interview heading | the literal `##` line, with its separator characters       |
| sub-section shape | the literal `###` line, with its numbering                 |
| hedge phrase      | the phrase already used for interviewer interpretation     |

Load the matching profile from `references/` (`profile-zh.md` is the default for a
Chinese-script memo). **The memo outranks the profile**: a profile fills in only the
observables the memo does not exhibit. Where they disagree, follow the memo and record
the deviation in the Phase 6 report.

If fewer than two entries exist, or the memo mixes two marker styles, stop and
`AskUserQuestion`, showing the fingerprint you read. Do not guess — Phase 5 writes
into the user's own file and the edit is additive-only (see Hard constraints).
```

Everything under "*After*" is **proposed design**, contingent on the profile files in B§1 rows 4–6 existing.

</details>

---

### B§4a — 不破坏保证（新增 · must-fix · 替换源命令的 `git diff` 检查）

**为什么必须换。** 源命令 Phase 6.1（`:132`）用 `git diff -- <MEMO_PATH>` 证明"只增不删"，条件是"skip if not a git repo"。这个条件不充分（Codex F3#1 + C2#1）：

- memo 在 git 仓库内但**未被追踪** → `git diff` 返回空 → 技能报告"✓ 纯增量"，而文件可能已被改坏
- memo 在 worktree 之外 → 报错或返回空
- 非 git 目录 → 检查被跳过，**没有任何替代**

唯一的安全网**恰好在最需要它的场景里静默通过**。memo 是用户自己的文件，`:143` / `:127` 要求编辑不可逆地保守，误报的代价是真实数据损坏。

**替代机制**（Phase 2 之后建立，Phase 6 校验）：

1. **快照**：读完 memo 后立刻 `cp "$MEMO_PATH" "$SNAP"`，`SNAP` 由 `mktemp` 生成。快照失败 = 硬失败，不进入 Phase 5。
2. **只插入校验**：Phase 5 结束后，验证快照的每一行都按原顺序出现在新文件中（新文件是快照的 supersequence）。判据：`diff "$SNAP" "$MEMO_PATH"` 的输出**只含 `>` 行，不含 `<` 或 `c`**。
3. **自动还原**：出现任何 `<` 或 `c` → `cp "$SNAP" "$MEMO_PATH"`，报告被改动的行，终止。不询问、不部分保留 —— `:143` 的 additive-only 是硬约束。
4. **git 检查降级为附加信息**：仅当 `MEMO_PATH` 落在 worktree 内**且** `git ls-files --error-unmatch "$MEMO_PATH"` 成功时才跑 `git diff` 展示；否则报告写明"memo 未被 git 追踪，已用快照校验"。**git 永远不是唯一证据。**
5. 快照在成功路径上保留到会话结束，路径写进报告，便于手动回滚。

顺带修掉 Codex C2#5 的一半：`mktemp` + `trap` 清理，同时替换源命令 `:23` 那个写死的 `.analyst-write-test` 探针文件名。

对应 B§2 矩阵：`:132` 一行的 Treatment 由 **Kept** 改为 **Replaced**。

---

### B§4b — 候选账本与幂等（新增 · must-fix）

**为什么必须补。** 增量同步的全部价值是"只补缺失的"。源命令唯一的去重手段是 Phase 4.1（`:119`）的关键词 grep —— 不共享关键词的近义重复直接漏过，于是**第二次运行会重复追加**，memo 被逐次污染。v1 的 OQ 9 承认了这点却未解决（Codex C2#2 + R5#4）。

**候选账本**：Phase 3 产出候选后、Phase 5 写入前，先输出一张表，每行一个候选：

| 字段 | 含义 |
|---|---|
| `source` | 转录稿文件名 + 行范围 |
| `theme` | 归一化主题（去语气词、去修饰后的主题短语） |
| `target` | 拟落位的 `### N.M` 小节 |
| `decision` | `new` \| `thinner` \| `equivalent` |
| `evidence` | 判成 `equivalent` / `thinner` 时，memo 中被比对的那条现有条目的引用 |

规则：

- `equivalent` → 跳过，不写入。
- `thinner` → 只追加转录稿中现有条目没有的**具体信息**（数字、时间、名称），不重写现有句子（`:127`）。
- `new` → 按 Phase 4.3 落位。
- **账本先于编辑输出**，编辑严格按账本执行。账本就是可审计的中间产物 —— 没有它，召回失败和重复写入都不可观测。

**等价判定的最小规则**（刻意不写成打分 rubric —— 这本就是判断题，写细不会让模型更一致，只会让 SKILL.md 更长）：两条内容在**同一小节内**、指向**同一主题**、且新候选不含现有条目没有的具体信息时，判 `equivalent`；三者有一不成立就升级为 `thinner` 或 `new`；不确定时**问用户**，不默认写入。

**幂等是验收测试，不是建议**：见 B§7 check 11。

---

### B§5 — Borrowed improvements from A（**整体推迟到 0.2.0**）

> **v2 状态：本节五项全部不在 v0.1.0 交付范围内。** 它们是重设计而非移植，与 must-fix R5#1 的 parity-first 顺序冲突。其中两项另有实质问题需先解决：
>
> - **重建隐含问题** 与 **标注推断的说话人** 引入了转录稿里不存在的生成内容，直接顶撞 frontmatter 承诺的 no-fabrication（`:148`）与 wording fidelity（`:145`）。0.2.0 必须先定义 provenance 机制 —— 答案内容始终源自转录稿，问题可最小重建，且报告里必须有 provenance 台账（Codex I1#2）。
> - **Post-edit omission sweep** 没有终止规则：发现遗漏之后是报告、自动再编辑、还是问用户？v1 未定义（Codex A4#3）。0.2.0 需指定有界不动点：重比对一次 → 只补新证据支持的候选 → 仍有未匹配内容则报告并停止。
>
> 其余三项（说话人标注闸门、多话题拆分、结构化 preflight 探针）无原理问题，按 parity 之后逐项加入。下表原文保留，作为 0.2.0 的输入。

| Idea | Source artifact + URL | Evidence | Target location | Why it improves the port |
|---|---|---|---|---|
| Post-edit omission sweep: after applying edits, re-read the transcript against the *updated* memo section and list anything still unmatched | `meeting-minutes-taker`, https://github.com/daymade/claude-code-skills/blob/main/daymade-audio/meeting-minutes-taker/SKILL.md | "Final: Compare draft against transcript, add omissions"; separate Step 3 self-review | `SKILL.md` Phase 6, before the `git diff` check | The source's only verification is that the diff is additive (`:132`). That catches *destructive* failure and is blind to *recall* failure — the exact failure mode of an incremental sync whose whole value is "add only what's missing" |
| Source-side speaker-labeling gate: if the transcript uses generic labels (`发言人1`, `Speaker 2`), ask the user to relabel at the source before inferring; infer only on refusal, and mark every inferred attribution | `meeting-minutes-taker` (same URL) | Step 1.5 Phase 0: "stop and ask the user to label the speakers at the source… Fall back to Phase A–C only when (a) the user explicitly says to proceed by inference, or (b) the source cannot be labeled" | `SKILL.md` Phase 1, as a gate before Phase 3 | The source's Q-detection keys entirely off named speakers (`:108`). Given a diarized-but-unlabelled transcript it will mis-assign Q and A, and `:148` ("no fabrication") gives it no defined behavior for that case |
| Reconstruct an implicit question from the answer's topic, marked with the profile's hedge | `interview-qa-minutes`, https://github.com/Jackhammer1024/Skills-for-Primary-Market-/blob/main/interview-qa-minutes/SKILL.md | Editing Rules: "When a question is unclear in the transcript, reconstruct a concise question from the answer's topic" | `SKILL.md` Phase 3 | The source recognises only explicit questions (`:108`), so a volunteered answer carrying real numbers is silently dropped — a pure recall loss with no signal. Routing it through the existing `访谈口径是…` hedge (`:81`) keeps `:148` intact |
| Split one answer covering unrelated topics into separate Q&A pairs under the right sub-sections | `interview-qa-minutes` (same URL) | Editing Rules: "When one answer covers multiple unrelated topics, split it into separate Q&A pairs under the right themes" | `SKILL.md` Phase 3, paired with the existing merge rule | The source only merges (`:110`), while Phase 4.3 files each candidate under one sub-section (`:121`). Without a split rule a two-topic answer must be misfiled, and `:153` names exactly that as a pitfall |
| Structured pre-flight probe block that prints what it found (memo candidates, transcript candidates, git present, existing section count) before any question is asked | `jtbd-interview`, https://github.com/savvides/jtbd/blob/main/jtbd-interview/SKILL.md | Preamble bash block detecting `.jtbd/`, git, manifest, and `SWITCH_COUNT`, echoing each as a labelled line | `SKILL.md` § Preflight, absorbing the checks at `:19` and `:23` | The source's auto-detection (`:29-41`) runs inside prose and its results surface only inside the AskUserQuestion at `:43-60`. Printing the evidence first makes the "auto-detection may pick the wrong file" risk the source itself names at `:55` visible before the user answers |

**Material ideas considered and rejected:**

- *Four-tier credibility marking (Fact/Claim/Inference/Confidential)* — `ahang1598/.../访谈纪要` — rejected: adds three new marker forms to a memo that has exactly one hedge (`:81`), breaking "new Q&A must look indistinguishable from existing entries" (`:83`).
- *Thousands-separator normalization of figures* — `interview-qa-minutes` — rejected: directly contradicts `:82` ("keep transcript figures verbatim; do not round or convert").
- *`.docx` output with 楷体 / 小四 / 1.5x spacing* — `interview-qa-minutes` — rejected: the skill edits one Markdown file in place (`:169`); a second output format is a different tool.
- *Intelligent output-filename generation (`YYYY-MM-DD-<topic>-<type>.md`)* — `meeting-minutes-taker` — rejected: there is no new file; the memo path is user-supplied (`:63`, `:169`).
- *Parallel multi-subagent generation with UNION merge* — `meeting-minutes-taker` — rejected: three independent drafts make sense when authoring from scratch; here the memo already exists and the work is a bounded diff (`:119-121`). The omission sweep above captures the recall benefit at lower cost.
- *Decisions / action-items / owner-due-date table* — `claude-office-skills/meeting-notes`, `dgalarza/meeting-transcript` — rejected: a different document genre. The memo here is Q&A (`:74-79`) and the skill may not invent structure (`:83`).
- *Rewriting answers into first person, banning `受访者认为`-style attribution* — `interview-qa-minutes` — rejected: it is a rewrite, and `:126` forbids rephrasing beyond filler cleanup while `:145` mandates transcript phrasing.
- *Bilingual `name_en` / `description_en` frontmatter* — `ahang1598/.../访谈纪要` — rejected: not a key any of the 16 live `SKILL.md` files uses; the repo's existing practice is one bilingual `description` string (`rhetoric-lens:3`).

### B§6 — Registration

Live re-read of `.claude-plugin/marketplace.json` on 2026-08-23: top-level `"version": "0.2.4"`; `plugins[]` has six entries (`jack-prompting` 0.1.2, `jack-engineering` 0.1.0, `jack-git` 0.1.0, `jack-html-preview` 0.1.0, `songy-course-exporter` 0.1.0, `writing-truth` 0.1.1); no `jack-work`.

**Version transitions**, per `CLAUDE.md`:

| Artifact | From (live) | To | Rule |
|---|---|---|---|
| `plugins/jack-work/.claude-plugin/plugin.json` → `version` | *(does not exist)* | `0.1.0` | "A brand-new skill or plugin still starts at `0.1.0`" |
| `plugins/jack-work/skills/interview-notes/SKILL.md` → `version:` | *(does not exist)* | `0.1.0` | Same |
| `.claude-plugin/marketplace.json` → `plugins[jack-work].version` | *(does not exist)* | `0.1.0` | Must mirror `plugin.json` (`README.md:66`) |
| `.claude-plugin/marketplace.json` → top-level `version` | `0.2.4` | **`0.2.5`** | "only ever add `0.0.1` (patch)" — never minor, regardless of this being a `feat:` |
| No other plugin's version changes | — | — | No existing plugin is renamed or restructured |

**Proposed `plugins/jack-work/.claude-plugin/plugin.json`:**

```json
{
  "name": "jack-work",
  "version": "0.1.0",
  "description": "Knowledge-work skills for research and consulting output: interview-notes incrementally syncs raw interview transcripts into a consolidated Q&A memo, strictly additively.",
  "author": {
    "name": "anzchy",
    "url": "https://github.com/anzchy"
  },
  "homepage": "https://github.com/anzchy/skills",
  "repository": "https://github.com/anzchy/skills",
  "license": "MIT",
  "keywords": [
    "interview",
    "transcript",
    "memo",
    "notes",
    "访谈纪要",
    "会议纪要"
  ]
}
```

**Proposed skill frontmatter for `plugins/jack-work/skills/interview-notes/SKILL.md`:**

```yaml
---
name: interview-notes
description: Incrementally sync raw interview transcripts into one consolidated Q&A memo. Strictly additive — preserves every existing entry byte-for-byte, adds only what is missing, and keeps the transcript's own wording. Reads the memo's existing entries and matches their formatting; Chinese conventions live in references/profile-zh.md. Use when the user asks to 整理 / 补充 / 扩写 / 继续 / 更新 访谈纪要, to sync a final memo with raw transcripts, or to merge an interview transcript into an existing interview memo without rewriting it.
argument-hint: "[interviewee name — optional, defaults to asking]"
version: 0.1.0
allowed-tools:
  - Read
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
  - Bash
---
```

**Exact `jack-work` entry to append to `.claude-plugin/marketplace.json` `plugins[]`** (placed after `writing-truth`; the array is not otherwise reordered):

```json
{
  "name": "jack-work",
  "version": "0.1.0",
  "description": "Knowledge-work skills for research and consulting output: interview-notes incrementally syncs raw interview transcripts into a consolidated Q&A memo, strictly additively.",
  "source": "./plugins/jack-work",
  "category": "productivity",
  "keywords": [
    "interview",
    "transcript",
    "memo",
    "notes",
    "访谈纪要",
    "会议纪要"
  ]
}
```

**Top-level edit to the same file:** `"version": "0.2.4"` → `"version": "0.2.5"`. Nothing else in that file changes.

`"category": "productivity"` matches the four existing productivity plugins; `"source": "./plugins/jack-work"` matches the `metadata.pluginRoot` convention and `README.md:66`. `defaultEnabled` is deliberately omitted — only `songy-course-exporter` sets it (to `false`), and this is a general-purpose skill.

### B§7 — Verification plan

**A repo-documented procedure exists** — `README.md:69`, in the "Adding a new plugin" section:

> `claude plugin validate . && claude plugin validate ./plugins/<plugin-name>`, then release with `/marketplace-release`.

So the primary check, run from the repo root once the files exist:

```
claude plugin validate --strict . && claude plugin validate --strict ./plugins/jack-work
```

**v2 adds `--strict`** (Codex F3#4): the installed CLI exposes it specifically to fail on unrecognized fields and missing metadata that the runtime tolerates. Verified 2026-08-23 that the current tree already passes `claude plugin validate . --strict`, so there is no pre-existing debt to clear first. (`claude` is on `PATH` at `/Users/jackcheng/.local/bin/claude` — observed.)

Then release per the same line: `/marketplace-release` (a repo-local skill at `.claude/skills/marketplace-release/SKILL.md` — observed), whose Step 0 semver classification is overridden by `CLAUDE.md` to `+0.0.1`. **It also owns `CHANGELOG.md` and the git tag** — v1 double-claimed those (Codex I1#1); v2 delegates them entirely.

> ⚠️ **Separate repo-level bug, not this port's to fix (Codex F3#3).** `/marketplace-release` (`SKILL.md:123-142`, `:194-204`) instructs appending a new skill to a `skills` array in the plugin manifest, but **no live `plugin.json` has that array** and `README.md:61-63` documents skills as auto-discovered. Running the release workflow may therefore mutate the manifest this plan calls "exact". File it as its own fix — keep auto-discovery, correct the release skill — and eyeball the `plugin.json` diff during this release.

Manual, file-level checks to run alongside it — none of these is a repo-provided command; `jq` is a local tool at `/usr/bin/jq` (observed on `PATH`):

1. **Planned files present.** `ls` each of the seven paths in B§1; rows 1–5 must exist, rows 6–7 must show the new entries. (v1 required rows 1–7 to exist while row 6 was conditionally created — a direct contradiction, now removed with the row.)
2. **JSON parses.** `jq empty .claude-plugin/marketplace.json && jq empty plugins/jack-work/.claude-plugin/plugin.json`.
3. **Source path resolves.** `jq -r '.plugins[]|select(.name=="jack-work").source' .claude-plugin/marketplace.json` prints `./plugins/jack-work`, and that directory exists.
4. **Version rule holds.** `jq -r '.version' .claude-plugin/marketplace.json` is `0.2.5` (was `0.2.4`); `jq -r '.version' plugins/jack-work/.claude-plugin/plugin.json` and `jq -r '.plugins[]|select(.name=="jack-work").version' .claude-plugin/marketplace.json` both print `0.1.0`; the `version:` line in the new `SKILL.md` is `0.1.0`.
5. **Metadata matches current examples.** Diff the new `plugin.json`'s key set against `plugins/jack-prompting/.claude-plugin/plugin.json` (the fullest live example).
6. **No unrelated plugin renamed.** `git diff .claude-plugin/marketplace.json` shows exactly two changes: the top-level `version` line and one appended array element. `jq -r '.plugins[].name'` still lists the original six in their original order, plus `jack-work`.
7. **Every source section is accounted for.** Walk the §2 matrix against the source's own `##`/`###` headings (`grep -n '^#' interview-notes-enricher.md`) and confirm every heading and every bullet under Editing Rules / Common Pitfalls / Completion Criteria has a row with a `Treatment`.
8. **Chinese conventions are not hard-coded as universal.** `grep -n '访谈\|纪要\|：\|那个\|对对对\|亿元' plugins/jack-work/skills/interview-notes/SKILL.md` should return **no** hits outside the `description` trigger words and any block explicitly quoting a profile; every hit belongs in `references/profile-zh.md`.
9. **Human spot-check (UI affordance, not a scriptable assertion).** After a session restart (`README.md:41`), `/plugin` lists `jack-work`, and `/jack-work:interview-notes` is offered.
10. **Preservation gate (fixture `zh-parity/`, gates build step 2).** `docs/fixtures/interview-notes/zh-parity/` — a memo + transcript in a **non-git** directory. Run the skill, then assert `diff snapshot memo` emits only `>` lines. Then run a deliberately destructive variant (instruct it to reword an existing answer) and assert it **auto-restores from the snapshot and reports the offending line** rather than leaving the edit in place. This is the check `git diff` cannot make (B§4a).
11. **Idempotence gate (fixture `zh-rerun/`, gates build step 3).** `docs/fixtures/interview-notes/zh-rerun/` — a memo that *already contains* one of the transcript's Q&A themes under different wording, so the keyword grep alone would miss it. Run twice back to back. Assert: the second run's candidate ledger is **entirely `equivalent`**, and `sha256sum` of the memo is unchanged between run 1 and run 2. Failing this means the skill corrupts the memo progressively — the failure mode B§4b exists to prevent.
12. **Chinese parity, per-row (gates build step 1).** For every **Kept** and **Generalized** row of the B§2 matrix, point at the line of `SKILL.md` or `references/profile-zh.md` that carries it. `profile-zh.md` must be a verbatim relocation — `diff` its strings against the source lines cited in B§4's relocation table; any reworded string is a parity break, not an improvement.

---

## Open questions（v2 状态）

**已在 v2 中解决 —— 不再阻塞：**

| v1 编号 | 原问题 | v2 决议 |
|---|---|---|
| 5 | 是否同时产出 `profile-en.md` | **推迟到 0.2.0。** B§1 row 5 删除。parity 未证明前，第二语言分支无从验证。顺带消除了 `argument-hint` 里 `--profile zh\|en` 与本问题的矛盾 |
| 6 | 多受访者参数的行为 | **一次一人。** 整个 `$ARGUMENTS` 当作单个姓名，不做空格拆分。见 B§3 |
| 7 | 是否保留 `analyst-dd` 的 D1 提问脚手架 | **压缩为普通两选一提问。** 16 个现存 SKILL.md 无一使用该脚手架 |
| 9 | 幂等只被假设，从未被断言 | **已解决。** B§4b 候选账本 + B§7 check 11 验收测试 |
| 10 | 根 `README.md` / `CHANGELOG.md` 是否纳入 | **README 纳入（B§1 row 7）；CHANGELOG 与 git tag 全部交给 `/marketplace-release`。** B§1 row 9 删除 |

**记录性说明 —— 不阻塞执行：**

1. **`references/` vs `reference/` — 仓库自身不一致。** v2 更正了 v1 的"2:2 平局"说法：`plugins/jack-html-preview/reference` 位于插件根目录而非 skill 同级，因此 skill 级实为 2 `references/` vs 1 `reference/`。本次选 `references/`。既有四个目录是否统一、统一到哪个拼写，另议。
2. **Skill frontmatter keys.** v1 提示词的仓库快照有误，实测：`argument-hint`（`jack-audit-fable/SKILL.md:4`、`jack-review-plan-fable/SKILL.md:4`）与 `allowed-tools`（`jack-auto-fix/SKILL.md:6`、`jack-audit-branches/SKILL.md:8`）均在用，`disable-model-invocation` 亦有两例。只有 `model:` 确实零命中。计划采信实测证据。
3. **`version:` 并非普遍存在。** 16 个 live `SKILL.md` 中 8 个有、8 个无。`CLAUDE.md` 与 `README.md` 视其为必需。是否回填那 8 个是独立决策，本次不动。
4. **源文件字节数。** 派发记录 11066 bytes，`ls -la` 报 `10.8K`，171 行。同一文件，无实质漂移，字节数未精确重算。
8. **`PROJECT_NAME`（`:65`）。** Step 0 收集后从未使用，源命令自称"informational only"，标记为 Dropped。若它原本要喂给某个从未接上的标题前缀，那是潜在特性而非死代码。
11. **交付物 A 的覆盖度caveat.** `gh search repos` 对三条自然语言查询全部返回零结果，而 `gh search code` 正常 —— 更像索引或排序限制而非限流，但这意味着 repo 级发现主要依赖 WebSearch。重跑 repo 查询可能补出本次遗漏的条目。
12. **（v2 新增）`/marketplace-release` 与 `skills` 数组不一致。** 该 skill 要求把新 skill 追加进 `plugin.json` 的 `skills` 数组，但所有 live manifest 都没有这个数组，`README.md:61-63` 也写明 skill 是自动发现的。属仓库级 bug，与本次移植无关 —— 单开一条修 `/marketplace-release`，保留自动发现。发布时留意 `plugin.json` 的 diff。

---

## 评审留痕

| 项 | 值 |
|---|---|
| 评审工具 | `/cc-suite:review-plan` |
| 模型 / effort | `gpt-5.6-sol` / `high` |
| Thread ID | `01a02d9f-431b-75c0-9dae-9b8d2c343690` |
| 判定 | **NEEDS REVISION**（23 条 finding：High 12 · Medium 9 · Low 2） |
| v2 处理 | 5 条 must-fix 已修；10 条 should-fix 中 8 条就地修正、1 条另立议题（F3#3）、1 条随 B§5 推迟（I1#2）；8 条判为过度施工不予采纳 |

**判为过度施工、明确不采纳的 finding**（记录理由，避免下次重复讨论）：

- **A4#5 — 为 "equivalent" / "thinner" / "unrelated topics" 写判定 rubric.** 这些本就是 LLM 判断题。写一份"什么算回答更单薄"的评分表不会让模型更一致，只会让 SKILL.md 更长。B§4b 采用三条件最小规则 + 不确定就问用户，到此为止。
- **C2#5 的另一半 — profile 缺失 / `--profile` 非法值的运行时失败路径.** 只有一个 profile 且没有 `--profile` 参数后，这条大部分消失；剩下的"非法值报错并列出合法值"是任何实现都会写的默认行为。（`mktemp` 清理那部分已在 B§4a 采纳。）
- **I1#3 — "language-agnostic" 名不副实.** 纯命名问题，零实现影响。v2 已在文字上改口为"中文约定外移 + memo 优先"。
- **I1#4 的行号偏移部分.** 计划文档是一次性消费品，±2 行的引用偏移不改变任何决策。其中"每个 plugin 都有 README"一条已更正，因为它是 B§1 row 2 的立论依据。
- **R5#5 — 缺任务顺序 / 依赖图.** 顺序已由修订说明的构建顺序小节给出，重复。
- **C2#3 的完整 eval suite.** 缩水为两个 fixture（parity + 幂等）。这是改用户自己 markdown 文件的个人技能，不是生产服务；英文、混合风格、空 memo、通用说话人标签等场景随 0.2.0 的功能一起进 fixture。
