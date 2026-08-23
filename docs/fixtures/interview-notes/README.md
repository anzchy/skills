# interview-notes fixtures

Two sanitized memo + transcript pairs, used by the verification plan in
`docs/plans/20260823-plan-jack-work-interview-notes.md` §B§7. Not installed — `docs/` is
excluded from the plugin tree.

**Always copy a fixture to a scratch directory before running the skill on it.** Two
reasons: the run mutates the memo, and check 10 specifically requires a **non-git**
directory — the whole point is proving the guarantee holds where `git diff` cannot see
anything.

```bash
WORK=$(mktemp -d)
cp docs/fixtures/interview-notes/zh-parity/* "$WORK"/
cd "$WORK"   # not a git repo — this is deliberate
```

## `zh-parity/` — gates build step 2 (check 10)

A memo with two existing Q&A entries (so the style rule has evidence to read), full-width
markers, a hedge phrase already in use, and an **intentional numbering gap** (`## 访谈 1`
then `## 访谈 4`) to exercise the do-not-renumber rule.

The transcript covers both themes already in the memo, plus two that are not (良率,
设备自制率), plus chit-chat that must be discarded.

Assert:

1. `diff` of snapshot vs. result emits **only `>` lines**.
2. The `## 访谈 4` heading is untouched and unrenumbered.
3. Then re-run instructing the skill to reword an existing answer — it must **auto-restore
   from the snapshot** and report the offending line, not leave the edit in place.

## `zh-rerun/` — gates build step 3 (check 11)

The memo already covers the transcript's quality theme, but words it as
「出货合格的比例」 where the transcript says 「良品率」 — **no shared keyword**, so the
Phase 4.1 keyword grep alone will miss it and a naive implementation appends a duplicate.

Assert: run twice back to back; the second run's candidate ledger is **entirely
`equivalent`**, and `shasum` of the memo is identical after run 1 and run 2.
