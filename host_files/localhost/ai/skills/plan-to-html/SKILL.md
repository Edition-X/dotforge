---
name: plan-to-html
description: >-
  Render an implementation or technical plan as a single, self-contained, high-end HTML
  document (light editorial design, sticky table of contents, light/dark toggle,
  print-to-PDF), saved to /Users/dkelly/Projects/html and opened in the browser. Use this
  skill whenever Dan asks you to write up, create, draft, or save a plan — especially as
  HTML or as a "nice", "visual", "readable", or "shareable" document — and also right after
  you've worked out an implementation plan (including coming out of plan mode), when handing
  it over as a polished HTML doc would help him digest it. Triggers on phrases like "make me
  a plan", "turn this into a plan doc", "plan for X as HTML", "save this as a plan", "give me
  a nice writeup of the plan", "document this plan". Strongly prefer this over dumping a long
  plan into the chat whenever the result is something Dan would want to read, keep, or share.
---

# Plan → HTML

Turn a plan into one self-contained, premium-looking HTML file Dan can read, keep, or share.
Output: a single `.html` (all CSS/JS inline, no external dependencies, works offline) saved to
`/Users/dkelly/Projects/html/` and opened in the browser.

## When to use

- Dan asks for a plan as an HTML doc, or a "nice"/"visual"/"readable"/"shareable" writeup.
- You've just figured out an implementation plan (or finished plan mode) and a polished
  document would land better than a wall of chat text.

When in doubt and the plan has real substance, offer it: "Want this as an HTML doc?"

## When *not* to use

- A quick two-line answer or a tiny change — just say it in chat.
- The user explicitly wants the plan inline, in a PR description, or in a ticket.

## How it works

The design lives in `assets/template.html`. A wrapper script injects your content and builds
the table of contents, so every plan looks consistent and you only have to write the body.

1. **Have a real plan first.** If the task isn't fully understood, do the thinking before the
   document — read the relevant code, confirm file paths, identify genuine risks. The doc is
   only as good as the plan. Never invent paths, phases, risks, or estimates to fill a section.

2. **Read the component catalog** once per session: `references/components.md`. It has
   copy-paste markup (phase cards, file-change lists, callouts, tables, checklists, pills,
   collapsible detail blocks) matched to the template's CSS.

3. **Author the body** as an HTML fragment and write it to a temp file (e.g.
   `/tmp/plan-body.html`). Structure for an implementation plan — include only sections with
   real content:
   *At a glance → Overview → Approach → Implementation (phases + file changes) → Risks →
   Testing → Rollout → Open questions.*
   Every top-level section is `<section class="sec" id="kebab-id"><h2>Title</h2>…</section>` —
   the TOC and section numbers are generated from these.
   Write only the body: no `<html>`, `<head>`, `<style>`, title, or meta row.

4. **Build it** with the script (adjust flags to the plan):

   ```bash
   python3 ~/.claude/skills/plan-to-html/scripts/build_plan.py \
     --title "Targeted deploy pipeline" \
     --summary "Path-filtered deploys with a guarded deploy-all fallback." \
     --status Proposed \
     --effort "~1.5 days" \
     --owner "Dan Kelly" \
     --repo monitoring-config \
     --body /tmp/plan-body.html
   ```

   It writes `~/Projects/html/<slug>-<date>.html` (de-duplicating the name if it exists) and
   opens it. Flags: `--title` and `--body` are required; `--summary`, `--kicker`
   (default "Implementation Plan"), `--status`, `--effort`, `--owner`, `--repo`, `--date`,
   `--slug`, `--out-dir`, `--no-open`, `--print-path-only` are optional.

5. **Report back** in chat: give the file path and a 2–3 line summary. Don't re-paste the whole
   plan — the document is the deliverable.

## Authoring principles

- **Digestible but complete.** Lead with the at-a-glance cards and a tight overview so the doc
  is skimmable in 30 seconds; move deep detail (full configs, edge cases, derivations) into
  `<details class="more">` blocks so it's all there without burying the reader.
- **Show structure, not just prose.** Prefer phase cards, file-change lists, and callouts over
  long paragraphs — they're what make the plan scannable.
- **Be honest about uncertainty.** Use risk callouts and an "Open questions" section rather than
  pretending the plan is more settled than it is.
- **Keep status truthful.** Default `--status Draft`; only mark Proposed/Approved when that's real.

## Customizing the look

All design is in `assets/template.html`, with the palette and fonts as CSS variables at the top
(and a `[data-theme="dark"]` block). To restyle every future plan, edit those variables — don't
hand-edit generated files in `~/Projects/html/`.
