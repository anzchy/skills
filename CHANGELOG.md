# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/anzchy/skills/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/anzchy/skills/compare/v0.1.0...v0.2.1
[0.1.0]: https://github.com/anzchy/skills/releases/tag/v0.1.0
