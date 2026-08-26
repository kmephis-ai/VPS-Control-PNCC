# ADR-0002: Durable AI-managed development pipeline

- Status: Accepted
- Date: 2026-08-26
- Tracking: #6 (`PIPE-001 — PNCC Autonomous Development Pipeline`)

## Context

PNCC already has a governed public repository, fixed security/runtime invariants, GitHub-hosted CI and an explicit separation between Product / Engineering Truth, private Instance Configuration Truth and physical Runtime Truth.

The remaining development risk is continuity and execution quality. Important state can otherwise remain trapped in one chat session, CI currently proves mostly static/public-safety properties, and runtime qualification is not yet cryptographically tied to a durable candidate/evidence lifecycle.

Long AI sessions are not a reliable continuity mechanism. The project therefore needs durable, machine-readable development state that any authorized agent/session can reconcile against provider truth and resume without reconstructing history from conversation text.

## Decision

PNCC will evolve toward a durable AI-managed engineering pipeline with these architectural properties:

1. Development progresses through one **AI-sized Work Unit** at a time.
2. Session continuity depends on durable machine-readable state, not chat history.
3. Every Work Unit records exact base/head identity, scope, forbidden scope, exit criteria and evidence requirements.
4. Overlapping mutation domains use a single writer lease; read-only discovery may run in parallel.
5. Failure classification is executable governance. `VALIDATOR_DEFECT`, `HARNESS_DEFECT` and `ENVIRONMENT_OR_BASELINE_BLOCKER` do not authorize product mutation. Only a proven `PRODUCT_DEFECT` may authorize a product candidate change.
6. CI is layered into fast engineering checks, deeper behavioral/security checks, deterministic candidate construction and a separate trusted runtime qualification plane.
7. Candidate artifacts are bound to exact source revisions through hashes/manifests/provenance. Runtime evidence must identify the exact candidate it qualifies.
8. GitHub CI success never promotes a candidate to `RUNTIME VERIFIED` or `Stable/DONE` without fresh trusted Windows/runtime evidence.
9. ADWF remains the upstream provider of generic orchestration/policy via a version-pinned Consumer Project Pack. PNCC remains an independent consumer repository.
10. The long-term operating model is **Human-by-Exception**: automation may continue within explicit policy/scope; owner involvement is required only at defined risk/authority boundaries.

## Authority model

Mandatory invariants remain in `AGENTS.md` and `SECURITY.md`.

The target end state is defined in `docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md`.

Incremental delivery is defined in `docs/roadmap/PNCC_PIPELINE_ROADMAP.md`.

Actual GitHub provider state, CI results and trusted runtime evidence override stale planning/checkpoint state, but may not override mandatory security/runtime invariants.

## Consequences

- PNCC will optimize for **session independence**, not maximum duration of one chat.
- Roadmap items are not all expanded into Issues in advance; only the nearest executable Work Unit is materialized.
- A green static CI result is necessary but insufficient for runtime promotion.
- Runtime evidence becomes an indexed engineering artifact rather than an informal transcript.
- Auto-merge/merge-queue capabilities are deferred until durable state, tests, artifact truth and qualification gates are mature enough to make unattended progression safe.
- Product features should not displace pipeline stabilization work when the development system itself is the limiting factor.

## Initial maturity

Current pipeline maturity is classified approximately as **L1 — Governed GitHub**.

Accepted target is **L6 — Human-by-Exception**.
