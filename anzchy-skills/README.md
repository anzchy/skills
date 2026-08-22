# anzchy-skills

Productivity skills for high-quality AI-assisted coding by [@anzchy](https://github.com/anzchy). Part of the `jack-cheng-marketplace`.

**Status:** v0.2.0 — Claude Code plugin.

## Layout

Skills live in **buckets** under `skills/`. The bucket is a staging convention for humans; the contract is `.claude-plugin/plugin.json`, which lists exactly what ships. A skill in `misc/` is on disk but not in the manifest, so it is not installed.

| Bucket | What lives there | Shipped |
|---|---|---|
| [`skills/prompting/`](./skills/prompting) | Work on the prompt before any code | yes |
| [`skills/engineering/`](./skills/engineering) | Review, audit, commit, PR, release | yes |
| [`skills/productivity/`](./skills/productivity) | Daily non-code workflow | yes |
| [`skills/misc/`](./skills/misc) | Kept around, not promoted | no |

Each bucket has its own README listing every skill in it, grouped by whether you have to type it or the model can reach for it.

## Not sure which one?

```
/anzchy-skills:jack-ask <your rough ask>
```

`jack-ask` reads the ask and hands back one skill name and the exact command. It routes; it never does the work.

## The chain

```
Muddled question → /anzchy-skills:jack-meta-think   → a neutral, answerable question
Weak wording     → /anzchy-skills:jack-prompt-master → tournament-refined prompt
Long autonomous  → /anzchy-skills:jack-loop-prompt   → paste-ready /goal prompt
A plan           → /anzchy-skills:jack-review-plan-fable → buildability review
Code that exists → /anzchy-skills:jack-audit-fable   → 9-dimension audit
Ready to ship    → /anzchy-skills:gh-commit → gh-pr → gh-release
A repo/dir       → /anzchy-skills:jack-html-preview  → one-file interactive explainer
```

Nothing auto-chains. Every step hands you output and stops.

## Note

The writing skills (dissect-author-mind, logic-template-lens, rhetoric-lens) moved to the sibling **`writing-truth`** plugin in the same marketplace.

## License

MIT
