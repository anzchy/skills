---
name: jack-html-preview
description: Turn ONE input — a project/source folder, a single Markdown file, a local repo, or a GitHub repo URL — into ONE self-contained interactive HTML file that explains the input end-to-end (structure, architecture, and the data-and-control flow from entry point to output). Produces a single .html with all CSS/JS inlined, styled to the Claude/Anthropic design language, that opens by double-click and is shareable as one file. Use whenever someone wants to visualize, explain, walk through, document, or "make an interactive page" for a codebase, repo, folder, or Markdown doc. Invoke manually as "/jack-html-preview <path-or-url>".
version: 0.1.0
---

# jack-html-preview

Reading a codebase or a long doc top-to-bottom is slow, and a static README can't show how the pieces connect. This skill produces ONE self-contained interactive HTML file that explains an input end-to-end — its structure, its architecture, and the underlying mechanism (how data and control flow from the entry point to the output). The file inlines all CSS and JS, fetches nothing at runtime, and opens by double-click, so it's shareable as a single attachment.

The input to explain: $ARGUMENTS

## What the output must be

A single `.html` file that:

- **Is fully self-contained** — all CSS and JS inlined, no build step, no `<link>`/`<script src>`, no web fonts or data fetched over the network. It must open offline by double-click and survive being emailed as one file. Fonts fall back to the system stack (the design language is preserved via the CSS variables, not by loading Anthropic's fonts).
- **Follows `reference/claude-design-spec.md`** — paper background (`#FAF9F5`), charcoal text, serif display headings, the leaf-shaped (asymmetric) border radius, restrained orange accent, generous line-height. Read that file before rendering; don't invent a different look.
- **Leads with a one-paragraph "what this does" summary**, then a "how it works" walkthrough that traces entry point → core → output in plain language.
- **Includes at least these three interactive features:**
  1. an interactive **collapsible file/module tree** (for Markdown: the heading hierarchy);
  2. **clickable nodes** that reveal a plain-language explanation of each part;
  3. a **diagram of the end-to-end flow** (entry point → core modules → output).

## Workflow

### 1. Detect the input type

Classify `$ARGUMENTS` into exactly one of four types and prepare its source:

| Input | How to detect | How to prepare |
| --- | --- | --- |
| **GitHub repo URL** | starts with `https://github.com/` or `git@github.com:` | shallow-clone into a temp dir: `git clone --depth 1 <url> "$(mktemp -d)/repo"` (or `gh repo clone`). Before cloning, **stop and ask** if the repo is likely over ~200 MB. |
| **Local repo** | a directory containing `.git/` | use in place, read-only. Don't modify the working tree. |
| **Project/source folder** | a directory without `.git/` | use in place, read-only. |
| **Single Markdown file** | a path ending in `.md`/`.markdown` | read the file directly. |

If the input is ambiguous (e.g. a bare name), ask one clarifying question rather than guessing.

### 2. Map the structure

The HTML is only as good as this mapping — spend the effort here, not on chrome.

**For code (folder / local repo / GitHub repo):**
- Find the **entry point(s)** — `main()`, a `bin`/CLI entry, a server bootstrap, `index.*`, a framework root. This anchors the flow diagram's "ENTRY".
- Identify the **key modules/files** and what each is responsible for, in plain language. Skip noise (`node_modules`, `.git`, build artifacts, lockfiles, vendored deps).
- Trace the **end-to-end path**: how a request/command/input travels from the entry point, through the core modules, to the output. This becomes the "how it works" walkthrough and the flow diagram.
- Note key **dependencies** and how they're wired in.
- Build a tree of the meaningful directories and files (collapse deep/irrelevant branches).

**For a single Markdown file:**
- Map the **heading hierarchy** (H1→H2→H3) — that hierarchy *is* the tree.
- The "flow" is the document's logical progression (intro → body sections → conclusion).
- Each node's explanation is a plain-language summary of that section.

Use Explore/Glob/Grep/Read for big inputs rather than reading every file — you need an accurate map, not a full transcript. For a large repo, sample entry points and representative modules.

### 3. Render the single self-contained HTML

1. Read `reference/claude-design-spec.md` for the exact colors, type scale, spacing, and the leaf-radius motif.
2. Start from `reference/html-template.html` — it already encodes the design language and the three interactive features (collapsible tree, click-to-explain panel, CSS flow diagram). **Copy it and fill it in**; it's a starting point, not a fixed form — add or drop tree nodes, flow steps, and panels to match the real input. A 3-file CLI and a 200-file monorepo must not look identical.
3. Populate from the step-2 mapping: the one-paragraph summary, the walkthrough, the flow steps (entry → core → output), the tree nodes, and the `NODE_DATA` explanations keyed by node id.
4. Keep everything inline. Before writing, sanity-check there is no `<link>`, no `src=`/`href=` pointing at a network resource, and no runtime fetch — the file must work with the network off.

### 4. Write the file and report

- Default output path: `./<name>-preview.html` (derive `<name>` from the repo/folder/file). Honor an explicit path if the user gave one.
- Write the file, then report the absolute path and a one-line summary of what it covers.
- **Do not auto-open it.** Offer to open it (e.g. `open <path>`) and wait for the user to say yes.
- If you shallow-cloned a repo into a temp dir, the HTML is self-contained, so you can leave the clone or clean it up — mention which.

## Stop and ask before

- Cloning any repo likely over ~200 MB.
- Adding any dependency (this skill needs only `git`/`gh`, already present) or any build step.
- Deleting or overwriting an existing file at the output path.

## Reference files (read on demand, don't preload)

- `reference/claude-design-spec.md` — the Claude/Anthropic design system (colors, type, spacing, leaf radius, components). Read in step 3 before rendering.
- `reference/html-template.html` — the self-contained HTML scaffold with the three interactive features wired up. Copy and fill it in.
