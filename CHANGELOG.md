# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.5] - 2026-08-23

### Added
- **jack-work plugin 0.1.0 — `interview-notes`.** New plugin for knowledge-work output: incrementally syncs raw interview transcripts into one consolidated Q&A memo, strictly additively (never rewrites existing entries). Ships a Chinese profile (`references/profile-zh.md`) and zh fixtures under `docs/fixtures/interview-notes/`. Install with `/plugin install jack-work@jack-cheng-marketplace`.

### Changed
- **jack-prompt-master 0.1.3 — self-contained.** Phase 2 intent extraction no longer invokes the user-scope `~/.claude/skills/prompt-master` skill; the 9-dimension intent table now ships inside the plugin as `references/intent-dimensions.md`, so the skill works wherever the `jack-prompting` plugin is installed. `jack-prompting` plugin 0.1.2 → 0.1.3.
- `.gitignore` now excludes `.prompts/` run checkpoints and nlpm history.

---

## [0.2.4] - 2026-08-23

### Added
- **jack-prompt-master 0.1.2 — task classification, reconnaissance and an interview gate.** Phase 2 now classifies the draft as *implementation* (7 rubric criteria) or *diagnosis* (9 criteria), runs bounded project-local reconnaissance on the paths the draft names, and opens a decision-impact-gated interview (`JPM_INTERVIEW=ask|auto`) only when an answer would change the prompt.
- Reference material under `docs/references/`: the 和菜头 article on directing AI repair work, and a comparison of its questioning approach against Claude Code prompt best practices. Plan notes for the jack-loop-prompt refinement under `docs/plans/`.

### Changed
- jack-prompt-master Round 1 enforces a hard **provenance rule** — no invented defaults; every concrete fact in the rewritten prompt must be one the recon step observed.
- jack-prompt-master Round 2 adds an **intent gate** (`intent_drift`), and the `jq` envelope check is parametrised on the criterion count so it works for both task classes.
- Rubric reworked: `provenance` replaces `role_clarity`; `timeline_repro` and `ruled_out` apply to diagnosis prompts; `verifiability` now requires an actually-observed test command.
- jack-prompting plugin 0.1.2 — bump so `/plugin update` delivers the new jack-prompt-master.

### Documentation
- The jack-prompting plugin description, its README skill blurb, and jack-meta-think's two cross-references all described jack-prompt-master as a "tournament" with parallel Claude + Codex candidates. They now describe the two-round self-refinement flow with the optional Codex round.

---

## [0.2.3] - 2026-08-23

### Changed
- **Breaking (jack-prompt-master 0.1.1):** the Claude↔Codex tournament is replaced by a 2+1 self-refinement flow. Round 1 is an inline Claude rewrite against the 9-dimension intent block and 7-criterion rubric; Round 2 is a mandatory "Grill yourself" adversarial review in an isolated Fable subagent that quotes evidence per criterion and rewrites to v2 (strict JSON validated with `jq`, one retry then degrade); Round 3 is an optional, user-gated Codex critique plus inline synthesis (`JPM_CODEX_ROUND`). The `MAX_ITER`, `PASS_THRESHOLD`, `JUDGE_RETRY` and synthesizer knobs are gone. Typical cost drops to ~12k–28k tokens when stopping at v2, versus ~40k–125k before.
- jack-prompting plugin 0.1.1 — bump so `/plugin update` delivers the new jack-prompt-master.

### Added
- `CLAUDE.md` at the repo root: all version bumps in this repo move the number by `0.0.1` only, regardless of change class.
- jack-prompt-master: `references/grill-prompt.md`.

### Removed
- jack-prompt-master: `references/judge-prompt.md`, `references/heuristic.sh`, `references/fallback-voice.md` — no longer dispatched by the new flow.

---

## [0.2.2] - 2026-08-22

### Changed
- **Breaking:** the single `anzchy-skills` plugin is split into install-what-you-need plugins under `plugins/`: `jack-prompting`, `jack-engineering`, `jack-git`, `jack-html-preview`, `songy-course-exporter` (disabled by default); `writing-truth` moves to `plugins/writing-truth`. Skill namespaces change from `/anzchy-skills:<skill>` to `/<plugin>:<skill>` — reinstall with `/plugin install <plugin>@jack-cheng-marketplace`.
- `marketplace.json` now sets `metadata.pluginRoot` and carries a marketplace `version` (= repo tag). New plugins start at 0.1.0.
- jack-ask 0.2.0: routes across all jack-* plugins, prints the namespaced command plus an install hint when the plugin is missing.
- writing-truth 0.1.1 / dissect-author-mind 0.1.1: call `/jack-html-preview:jack-html-preview` instead of the old namespace.

### Documentation
- README rewritten for the multi-plugin layout; per-plugin READMEs; marketplace-release skill updated.

---

## [0.2.1] - 2026-08-22

### Changed
- anzchy-skills plugin version 0.2.0 → 0.2.1 in `plugin.json` and `marketplace.json`, so `/plugin` users receive the jack-meta-think 0.2.0 update; the repo tag now tracks the plugin version.
- anzchy-skills: `songy-course-exporter` registered in the `plugin.json` skills list; marketplace description updated to thirteen skills.

### Documentation
- marketplace-release skill: release flow now bumps plugin manifest versions per the official Claude Code plugin docs.

---

## [0.1.0] - 2026-08-22

First tagged release of the skills hub (`npx skills@latest add anzchy/skills`).

### Added
- Repo converted to a Claude Code plugin marketplace with two plugins: `anzchy-skills` and `writing-truth`.
- jack-meta-think 0.2.0: diagnose the question before writing the prompt; new investment / M&A domain case library (`references/case-investment-cross-border-ma.md`) with a domain 追问库.
- jack-ask, jack-prompt-master (with README pointing upstream to jack-meta-think), jack-loop-prompt 0.1.2 (close-the-loop improvements from a real run + model routing).
- Engineering skills: jack-audit-fable, jack-review-plan-fable, jack-auto-fix, jack-audit-branches, gh-commit, gh-pr, gh-release.
- Productivity: jack-html-preview (one-file interactive HTML explainers); misc: songy-course-exporter.
- writing-truth plugin: dissect-author-mind, logic-template-lens, rhetoric-lens.

### Changed
- anzchy-skills: skills grouped into buckets (prompting / engineering / productivity / misc) with a router README; plugin manifest metadata completed.

### Documentation
- Added the reference text jack-meta-think derives from under `docs/references/`.

---

[Unreleased]: https://github.com/anzchy/skills/compare/v0.2.5...HEAD
[0.2.5]: https://github.com/anzchy/skills/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/anzchy/skills/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/anzchy/skills/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/anzchy/skills/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/anzchy/skills/compare/v0.1.0...v0.2.1
[0.1.0]: https://github.com/anzchy/skills/releases/tag/v0.1.0
