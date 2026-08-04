---
description: Run a bounded evidence-based load-test and optimization loop in a safe non-production environment.
agent: orchestrator
---
Load-test target and safe environment: `$ARGUMENTS`.

First confirm target is not production unless user explicitly approved production testing. If target, environment, credentials, or stop budget is unclear, stop and report blocker. Establish performance acceptance criteria, maximum iterations, maximum duration, and resource budget. Delegate workload modelling to `architect` or `implementer`, harness changes to `implementer`, execution and collection to `test-runner`, bottleneck analysis to `debugger`, and review to `reviewer`.

For every bounded iteration record source revision, environment, workload profile, concurrency or arrival rate, duration, latency percentiles, throughput, error rate, resource usage, suspected bottleneck, one evidence-based change, and comparison with prior run. Keep conditions comparable. Never run unbounded tests, production tests without explicit approval, or multiple competing changes in one iteration. Stop when criteria pass, budget/iteration limit is reached, or external blocker is proven.

Return run ledger, metrics, bottleneck evidence, changes, reviewer verdicts, stop reason, and remaining uncertainty.
