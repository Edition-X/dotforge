---
description: Reproduce a failure, prove root cause, apply the smallest fix, and verify without repeating unchanged attempts.
agent: orchestrator
---
Debug failure or observed defect: `$ARGUMENTS`.

Capture exact failing command, environment, expected behavior, observed behavior, and previous attempts. Delegate reproduction to `test-runner` when deterministic and root-cause analysis to `debugger`. Require evidence separating observations, hypotheses, experiments, root cause, fix, and verification. Apply smallest justified fix through `implementer` only after root cause is demonstrated; use `architect` when boundaries or production safety are involved.

Allow one focused correction to same approach. If it fails again, escalate instead of repeating. Inspect actual diff, rerun focused and relevant broader checks, and report failures honestly. Do not change unrelated files or perform remote/destructive actions.
