---
name: research
description: Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the user wants a topic researched, docs or API facts gathered, or reading legwork delegated to a background agent.
---

For broad repository discovery, use or delegate to optional native `scout` when available
and worth its overhead. Keep small known reads direct. Scout is read-only and returns a compact
factual handoff; parent owns notes and decisions. If unavailable, continue direct.

Its job:

1. Investigate the question against **primary sources** — official docs, source code, specs, first-party APIs — not a secondary write-up of them. Follow every claim back to the source that owns it.
2. Return findings, evidence, coverage, and unknowns with paths and line ranges. Keep
   output near 500 words and omit secrets.
3. Parent writes findings to a single Markdown file, citing each claim's source. Save it
   where repo already keeps such notes; match existing convention, and if none, put it
   somewhere sensible and say where.
