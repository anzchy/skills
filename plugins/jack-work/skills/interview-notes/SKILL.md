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

# interview-notes

Incrementally sync raw interview transcripts into a consolidated Q&A memo. Strictly
additive: preserve existing content, add only missing items, keep transcript wording.

The memo is **the user's file, not a plugin artifact**. Every rule below exists to make
one guarantee cheap to verify: nothing that was in the memo before this skill ran is
gone after it ran.

## Style profile

The memo's own conventions govern. `references/profile-zh.md` supplies **defaults for
Chinese memos only**, and only for observables the memo does not exhibit.

Before writing anything, read **at least two complete existing Q&A entries** — whole
entries, not 5–10 lines — and copy how they are written: the colon glyph, how the Q line
is emphasized, the sub-section heading shape, and any hedge phrase already in use. Where
the memo and `references/profile-zh.md` disagree, **the memo wins**, and the deviation
goes in the Phase 6 report.

If the memo has fewer than two existing entries, or mixes two marker styles, **stop and
`AskUserQuestion`**, showing the evidence you read. Do not guess — Phase 5 writes into
the user's own file.

## Preflight (hard-fail by default)

Run these before Step 0; abort on any failure. Print the findings as one labelled block
**before** any question is asked, so the user sees the evidence the auto-detection is
based on.

1. **Working directory readable** — `pwd && ls -la` via Bash. If cwd has no files →
   HARD FAIL: "No files found in cwd. Please cd to the project directory containing the
   memo + transcripts."
2. **Working directory writable** — probe with `mktemp` inside the cwd and remove it via
   `trap`; never leave a named artifact behind. If the probe fails → HARD FAIL: "CWD not
   writable; this skill edits an existing memo file in place and needs write access."

## Step 0 — Inputs

### 0.1 Auto-detect the memo

Expand the language-neutral candidates plus the profile's:

```bash
find . -maxdepth 1 -type f \( -name '*memo*.md' -o -name '*interview*.md' \) -exec ls -la {} +
# plus the memo globs in references/profile-zh.md §9
```

Use `find`, not a bare `ls` with globs. Under zsh — the default shell on macOS — an
unmatched glob is a **hard error that aborts the whole command line**, and `2>/dev/null`
does not help because the failure happens during expansion, before `ls` ever runs. A bare
`ls *memo*.md *interview*.md` therefore detects **nothing** in any directory where one of
the patterns has no match, which is the normal case.

Pick the **largest** matching file as the default. If none match, ask the user for the path.

### 0.2 Auto-detect transcripts

Expand the date-prefixed and language-neutral candidates plus the profile's:

```bash
find . -maxdepth 1 -type f \( -name '20[0-9][0-9][01][0-9][0-3][0-9]-*.md' \
     -o -name '*interview*.md' \) -exec ls -la {} +
# plus the transcript globs in references/profile-zh.md §9
```

Then, in this order:

1. **Exclude the selected `MEMO_PATH` from the transcript set.** `*interview*.md` is used
   by both 0.1 and 0.2, so a memo named `xxx-interview.md` will match its own transcript
   glob and the skill would diff the memo against itself.
2. **Reject duplicate paths** — the same file reached through two globs is one candidate.
3. **Print every surviving candidate with its size** before asking anything. A 2 KB
   "transcript" next to a 90 KB one is usually a detection error, and the user can only
   see that if the sizes are on screen.

### 0.3 Confirm

One `AskUserQuestion`, two options: **use the auto-detected paths** (shown above with
sizes), or **override with explicit paths**. Nothing more — no pros/cons scaffold.

Collect:

- `MEMO_PATH` — full path to the consolidated memo file
- `TRANSCRIPT_GLOB` — glob for the transcript files

### 0.4 Scope

`$ARGUMENTS`, in full, is **exactly one interviewee name**. It is not split on spaces and
carries no flags — English names contain spaces, and a list syntax would be ambiguous with
them.

- `$ARGUMENTS` non-empty → scope every later phase to that person.
- `$ARGUMENTS` empty → enumerate the memo's existing interviewee sections and offer them
  as `AskUserQuestion` options. Never batch.
- The name matches more than one section → `AskUserQuestion` with the matches as options.

To process a second person, invoke the skill again.

## Workflow

Follow these phases in order. Each phase has a tight deliverable — do not skip ahead.

### Phase 1 — Scope

1. Confirm which interviewee to update (from `$ARGUMENTS` or the Step 0.4 question).
2. Resolve the transcript by Glob: search `TRANSCRIPT_GLOB` for files whose name contains
   the interviewee's name, an alternate romanization of it, or a role keyword. The
   Chinese-specific keys are in `references/profile-zh.md`.
3. Locate the target section in the memo by `Grep`-ing for the memo's own interview
   heading pattern (`references/profile-zh.md` §3 for Chinese memos) — **be liberal**,
   heading conventions vary.
4. If multiple transcript files match the same interviewee, ask the user which to use.
5. If no transcript file matches, hard-fail with the list of unmatched interviewee names
   and the glob that was searched.

### Phase 2 — Read

1. Read the full transcript for the scoped person. Transcripts are long and
   conversational; read in chunks if needed, but **cover the whole file** before editing
   — questions and key answers are scattered throughout.
2. Read the current memo section end-to-end: from its interview heading to the **next
   same-level heading or horizontal rule**, whichever comes first.
3. **Take the snapshot now** — see § Non-destruction guarantee. Phase 5 must not start
   without it.

### Phase 3 — Extract candidate Q&A from the transcript

Transcripts are raw speaker dialogue, not pre-formatted Q&A.

- **Q candidates** — lines from the **interviewer** side that are explicit questions. What
  counts as an explicit question is a per-language matter; for Chinese memos the
  punctuation and the opener list are in `references/profile-zh.md` §7.
- **A candidates** — the interviewee's response immediately following, possibly
  **spanning several turns** until the topic changes.
- Merge multi-turn answers on the **same topic into one** answer block, preserving
  wording. The block's marker glyph comes from the memo's own entries.
- Discard **chit-chat, scheduling**, AV setup, and off-topic asides.

Produce a working list of `(question_theme, transcript_quote)` pairs in your response
context. **Do not write to the memo file yet.**

### Phase 4 — Diff against the memo

For each candidate:

1. `Grep` the current memo section for the same theme (**by keyword, not exact string**).
   If present with equivalent content → **skip**.
2. If the memo's answer is **thinner**/incomplete and the transcript has concrete detail
   (numbers, names, timelines) → queue as an addition under the same Q, or as a
   **follow-up Q**.
3. If the theme is absent → queue as a new Q&A under the most relevant existing
   sub-section (shape per the memo; Chinese default in `references/profile-zh.md` §2).

Then write the **candidate ledger** (see § Candidate ledger) before touching the file.

### Phase 5 — Apply edits

1. Use `Edit` with **enough surrounding context** (the preceding Q&A block) to uniquely
   locate the insertion point. Insert new Q&A where it logically belongs — **not** dumped
   at the end of the section.
2. Keep wording close to the transcript. Light clean-up of filler, speech repetitions and
   obvious speech-to-text artifacts is allowed (Chinese filler list in
   `references/profile-zh.md` §8). **Do not rephrase into** a high-level summary.
3. **Never delete or rewrite** existing lines unless the user explicitly asks to correct a
   factual mismatch.
4. Do not renumber existing sub-sections or interview headings. If the memo skips a
   number, **preserve the gap**.

### Phase 6 — Verify & report

See § Non-destruction guarantee for the verification, then report:

- Which interviewee section was updated
- How many Q&A items were added
- One-line summaries of each addition, each naming the source transcript filename
- Any style deviations from the memo's existing convention (rare; flag if found)
- The snapshot path, so the user can roll back by hand

Keep the report brief; the diff is the source of truth.

## Non-destruction guarantee

`git diff` is not a safety net here. An untracked memo, or a memo outside the worktree,
yields an **empty diff** — which reads as "✓ nothing was deleted" precisely when there is
no version control to recover from. The guarantee below does not depend on git.

1. **Snapshot.** Immediately after reading the memo in Phase 2, before any edit:

   ```bash
   SNAP=$(mktemp -t interview-notes-snap)
   cp "$MEMO_PATH" "$SNAP"
   ```

   If the snapshot fails, hard-fail. Phase 5 **must not start** without it.

2. **Insertion-only check.** After Phase 5, verify the new file is a **supersequence** of
   the snapshot — every snapshot line still present, in the same order:

   ```bash
   diff "$SNAP" "$MEMO_PATH"
   ```

   The output must contain **only `>` lines**. Any `<` line or `c` hunk means something
   was deleted or altered. **Any edit that modifies an existing line is destructive** by
   this definition, even one that only appends to the end of it — every addition must be a
   whole new line.

3. **Auto-restore.** On any `<` or `c`:

   ```bash
   cp "$SNAP" "$MEMO_PATH"
   ```

   then report the offending lines and stop. **Do not ask** the user first and do not keep
   part of the edit — additive-only is a hard constraint, not a preference.

4. **git is supplementary.** Run `git diff -- "$MEMO_PATH"` for display **only** when the
   memo is inside a worktree *and* `git ls-files --error-unmatch "$MEMO_PATH"` succeeds.
   Otherwise say so in the report: the memo is **not tracked by git**, and the snapshot
   check is what verified it. git is **never the only evidence**.

5. **Keep the snapshot** for the rest of the session and print the **snapshot path** in
   the report, so a rollback is one `cp` away.

## Candidate ledger

Keyword `Grep` alone misses a near-duplicate that shares no keyword with the existing
entry — so a second run appends it again, and the memo degrades with every run. The
ledger makes that failure visible before it reaches the file.

At the end of Phase 4, **before any edit**, print one row per candidate:

| field | meaning |
|---|---|
| `source` | transcript filename + line range |
| `theme` | the normalized theme — filler and modifiers stripped |
| `target` | the sub-section it would land in |
| `decision` | `new` \| `thinner` \| `equivalent` |
| `evidence` | for `equivalent` / `thinner`: the existing memo entry it was compared against |

Then act **strictly by the ledger** — no edit without a row, no row without an edit:

- `equivalent` → **skip**. Write nothing.
- `thinner` → append only the **concrete information** the existing entry lacks (numbers,
  dates, names), **as a new line under the same Q — never by editing an existing line.**
  Extending an existing line would rewrite it, which the non-destruction check treats as
  destruction and auto-restores; a `thinner` addition written that way can never land.
- `new` → place it per Phase 4.3.

**Deciding `equivalent`.** Three conditions, all required: the two sit in the **same
sub-section**, they carry the **same theme**, and the candidate adds no concrete
information the existing entry lacks. If any one fails, it is `thinner` or `new`. If you
are not sure, **ask the user** — never default to writing.

**Running it twice on the same inputs must change nothing.** The second run's ledger
should be entirely `equivalent`, and the memo's checksum identical. If it is not, the
skill is corrupting the memo one run at a time.

## Hard constraints

- **Additive only** by default. Removals require explicit user instruction.
- **One section at a time.** Do not batch-edit multiple interviewees in a single turn
  unless the user explicitly asks.
- **Wording fidelity.** Prefer the transcript's phrasing over polished prose. If the
  transcript is ambiguous, mark it with the memo's own hedge phrase rather than asserting
  (Chinese hedges in `references/profile-zh.md` §4).
- **Style match.** Detect the memo's existing Q/A marker style and match it exactly. The
  profile supplies a default only where the memo shows you nothing.
- **Traceability.** Every new Q&A must be backed by specific transcript text. If nothing
  in the transcript supports it, do not add it.
- **No fabrication.** Do not infer numbers, dates, or names that are not in the transcript.

## Common pitfalls

- Mixing **two marker styles** within the same memo — match whichever the existing entries
  use.
- Appending all new Q&A at the **bottom of the section** instead of placing them in the
  relevant sub-section.
- Summarizing a **5-minute answer** into one sentence — losing the concrete details the
  user wants preserved.
- Treating **interjections** as questions (Chinese list in `references/profile-zh.md` §7).
- Rewriting existing Q&A wording as a side effect of an `Edit` — always scope `old_string`
  to the insertion anchor only.
- Renumbering around an **intentionally-skipped** section number.
- Assuming the memo **is in a git repo**. It usually is not; that is why the snapshot
  exists.

## Completion criteria

- Scoped interviewee section is updated in place.
- All added content is traceable to specific transcript text — state **which transcript
  filename** each addition came from.
- All pre-existing content is preserved **byte-for-byte**, verified by the snapshot check.
- Final response states: interviewee name, **sub-sections touched**, a short bullet list of
  added Q&A themes, and the snapshot path.

## Output

This skill **edits the user's memo file in place** at `MEMO_PATH`. It creates no new file.
The memo file is the **user's, not a plugin artifact**.

If the user wants the original preserved beyond this session, ask them to **commit it
first or save a backup** copy outside the skill.
