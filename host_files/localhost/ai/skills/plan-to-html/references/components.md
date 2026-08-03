# Plan body components

You author the plan **body** as an HTML fragment, then `build_plan.py` wraps it in the
template and builds the table of contents. This file is the catalog of components the
template's CSS supports. Copy the markup, fill in real content, drop what you don't need.

## Ground rules

- The body is everything *between* the header and footer — do **not** write `<html>`, `<head>`,
  `<style>`, the top bar, the title, or the meta row. The script adds all of that.
- Wrap every top-level section as `<section class="sec" id="kebab-id"><h2>Title</h2> ... </section>`.
  The TOC and the section numbers come from these automatically — one TOC entry per `<section class="sec" id>`.
  Optional: add `data-toc="Short label"` to a section to show shorter text in the TOC than the heading.
- Use real content only. Omit any section or component you have nothing concrete for — an honest
  short plan beats a padded one. Don't invent file paths, risks, or estimates.
- Keep prose tight. Lead with what's skimmable; push deep detail into `<details class="more">` so the
  document stays digestible but still complete.

---

## At a glance (put this first)

A row of stat cards giving the 30-second version. Great for goal / scope / risk / effort.

```html
<section class="sec" id="at-a-glance" data-toc="At a glance">
  <h2>At a glance</h2>
  <div class="glance">
    <div class="stat"><div class="k">Goal</div><div class="v">Cut deploy time to under 5 min</div></div>
    <div class="stat"><div class="k">Scope</div><div class="v">CI workflows only</div></div>
    <div class="stat"><div class="k">Risk</div><div class="v"><span class="pill pill--warn">Medium</span></div></div>
    <div class="stat"><div class="k">Effort</div><div class="v serif">~1.5 days</div></div>
  </div>
</section>
```

## Overview / context

Plain prose. Set up the problem and the chosen approach. A `callout--note` is good for the
one-line thesis. Keep it to a few short paragraphs.

```html
<section class="sec" id="overview"><h2>Overview</h2>
  <p>Two or three sentences on the problem and why now.</p>
  <div class="callout callout--note">
    <span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-5M12 8h.01"/></svg></span>
    <div class="body"><b>Approach</b>The single most important sentence describing the strategy.</div>
  </div>
</section>
```

## Phases / steps

The backbone of an implementation plan. One `.phase` card per phase; number them yourself in
`phase-num`. Steps are an `<ol class="steps">` (auto-numbered). Add a `phase-meta` line for an
estimate or dependency. Nest a file-change list or callout inside a phase when it helps.

```html
<section class="sec" id="plan"><h2>Implementation</h2>
  <div class="phase">
    <div class="phase-head">
      <div class="phase-num">1</div>
      <div>
        <p class="phase-title">Add the path filter</p>
        <div class="phase-meta">~3h &middot; no dependencies</div>
      </div>
    </div>
    <ol class="steps">
      <li>First concrete action, in the imperative.</li>
      <li>Second action, referencing <code>paths/to/files</code>.</li>
    </ol>
  </div>

  <div class="phase">
    <div class="phase-head">
      <div class="phase-num">2</div>
      <div><p class="phase-title">Wire up the guarded fallback</p></div>
    </div>
    <ol class="steps">
      <li>...</li>
    </ol>
  </div>
</section>
```

## File changes

A precise list of what gets touched. `op--new` / `op--edit` / `op--del` / `op--move`.

```html
<ul class="files">
  <li><span class="op op--new">new</span><code>.github/workflows/deploy.yml</code><span class="desc">— path-filtered deploy job</span></li>
  <li><span class="op op--edit">edit</span><code>salt/top.sls</code><span class="desc">— add runner group</span></li>
  <li><span class="op op--del">del</span><code>scripts/legacy-deploy.sh</code></li>
  <li><span class="op op--move">move</span><code>a.py → b.py</code></li>
</ul>
```

## Callouts

Five variants. Structure is identical; only the modifier class and icon change. The first `<b>` in
`.body` renders as a heading line. Icons are inline SVG (no external deps) — reuse these.

```html
<!-- note (accent) --> <div class="callout callout--note"><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-5M12 8h.01"/></svg></span><div class="body"><b>Note</b>Body text.</div></div>

<!-- decision (accent) --> <div class="callout callout--decision"><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2z"/></svg></span><div class="body"><b>Decision</b>What was chosen and the one-line why.</div></div>

<!-- ok / good --> <div class="callout callout--ok"><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg></span><div class="body"><b>Why this is safe</b>Body text.</div></div>

<!-- warn --> <div class="callout callout--warn"><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg></span><div class="body"><b>Watch out</b>Body text.</div></div>

<!-- risk --> <div class="callout callout--risk"><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg></span><div class="body"><b>Risk</b>What could go wrong, and the mitigation.</div></div>
```

## Tables (options, decisions, tradeoffs)

Always wrap in `.table-wrap` so wide tables scroll instead of breaking the layout.

```html
<div class="table-wrap">
  <table class="tbl">
    <thead><tr><th>Option</th><th>Pros</th><th>Cons</th><th>Verdict</th></tr></thead>
    <tbody>
      <tr><td>Path-filtered workflow</td><td>Fast, targeted</td><td>More YAML</td><td><span class="pill pill--ok">Chosen</span></td></tr>
      <tr><td>Deploy everything</td><td>Simple</td><td>Slow, risky</td><td><span class="pill">Rejected</span></td></tr>
    </tbody>
  </table>
</div>
```

## Checklist (testing / verification / acceptance)

Add class `done` to a `<li>` to render it ticked.

```html
<ul class="checklist">
  <li class="done">Workflow lints clean (<code>actionlint</code>)</li>
  <li>Dry-run deploy on staging passes</li>
  <li>Rollback path verified</li>
</ul>
```

## Pills / status badges

`pill` (neutral) plus `pill--ok`, `pill--info`, `pill--warn`, `pill--danger`. Inline anywhere.

```html
<span class="pill pill--ok">Low risk</span>
<span class="pill pill--warn">Needs review</span>
<span class="pill pill--danger">Blocker</span>
```

## Progressive disclosure (keep it digestible)

Put long detail — full config, edge cases, derivations — inside a collapsible block so the main
flow stays skimmable. This is the key to "digestible but still complete".

```html
<details class="more">
  <summary>Full workflow YAML</summary>
  <div class="more-body">
    <pre><code>name: deploy
on:
  push:
    paths: [ "salt/**" ]
...</code></pre>
  </div>
</details>
```

## Code, quotes, prose

- Inline: `<code>like this</code>`. Block: `<pre><code>...</code></pre>` (escape `<`, `>`, `&`).
- `<blockquote>` renders as an editorial pull-quote (serif italic) — use sparingly for a key principle.
- `<h3>` / `<h4>` for sub-headings inside a section. Regular `<p>`, `<ul>`, `<ol>` work as expected.

---

## Suggested section order for an implementation plan

Adapt freely — include only what has real content:

1. **At a glance** — stat cards
2. **Overview / context** — problem + chosen approach
3. **Approach / design** — how it works (optional; fold into overview if small)
4. **Implementation** — phase cards with steps + file-change lists
5. **Risks & mitigations** — risk callouts or a table
6. **Testing & verification** — checklist
7. **Rollout / sequencing** — order, flags, backout (optional)
8. **Open questions** — what still needs a decision (optional)
