---
description: Run a bounded evidence-based load-test and optimization loop in a safe non-production environment through one worker per iteration.
agent: orchestrator
---
Load-test target and safe environment: `$ARGUMENTS`.

First confirm the target is not production unless the user explicitly approved production
testing. If target, environment, credentials, or stop budget is unclear, stop and report
the blocker. Establish performance acceptance criteria, maximum iterations, maximum
duration, and resource budget. Delegate each bounded iteration — harness changes,
execution, collection, and bottleneck analysis — as one whole ticket to `worker`.

For every iteration record source revision, environment, workload profile, concurrency or
arrival rate, duration, latency percentiles, throughput, error rate, resource usage,
suspected bottleneck, one evidence-based change, and comparison with the prior run. Keep
conditions comparable. Never run unbounded tests, production tests without explicit
approval, or multiple competing changes in one iteration. Dispatch a fresh `verifier` to
confirm a completed run's evidence before treating an iteration as accepted. Stop when
criteria pass, the budget/iteration limit is reached, or an external blocker is proven.

Return the run ledger, metrics, bottleneck evidence, changes, verifier findings, stop
reason, and remaining uncertainty.
