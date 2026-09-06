---
description: Reproduce a failure, prove root cause, apply the smallest fix through a worker, and verify without repeating unchanged attempts.
agent: orchestrator
---
Debug failure or observed defect: `$ARGUMENTS`.

Capture the exact failing command, environment, expected behavior, observed behavior, and
any previous attempts. Delegate reproduction, root-cause evidence, and the smallest
justified fix as one whole ticket to `worker`: require it to separate observations,
hypotheses, experiments, demonstrated root cause, fix, and verification. Apply the fix only
after root cause is demonstrated, not before.

Allow one focused correction to the same worker if the first attempt fails. A second
materially similar failure (same failure_fingerprint) goes to a fresh `rescue` dispatch
instead of a third attempt on the same approach. Inspect the actual diff yourself, rerun
focused and relevant broader checks, and report failures honestly. Do not change unrelated
files or perform remote/destructive actions.
