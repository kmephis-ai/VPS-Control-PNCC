# VPS Control Center / PNCC

Public engineering repository for **Personal Network Control Center (PNCC)**, evolved from VPS Control Center.

## Repository status

**Stable v7.0.0 released / immutable / known startup UI defect; patch remediation active.**

The first governed Stable release completed the full source → deterministic artifact → physical Runtime Qualification → Runtime Authority → Owner-authorized promotion lifecycle. A later exact-release startup probe found a startup-blocking false positive in the product's `FUNCTIONAL_CONSISTENCY` self-gate. The published v7.0.0 ZIP/tag remain immutable historical evidence and are not being overwritten.

Stable release identity:

- tag: `v7.0.0`;
- release: `VPS Control PNCC v7.0.0`;
- artifact: `VPS-Control-v7.0.0.zip`;
- SHA-256: `1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599`;
- size: `700897` bytes;
- fresh Stable nine-scope Runtime Qualification: `PASS`;
- Runtime Authority: `true` for the qualified runtime evidence boundary;
- release asset independently re-downloaded and SHA/size verified;
- functional UI startup acceptance: `KNOWN_DEFECT / FAIL` for the released v7.0.0 artifact.

Machine-readable completion history remains in `.pncc-dev/attestations/stable-v7.0.0-completion.json`. The later startup-defect truth is recorded separately in `.pncc-dev/attestations/stable-v7.0.0-startup-defect.json`; it does not rewrite historical Runtime Qualification, but it prevents the released v7.0.0 UI from being treated as currently accepted for normal startup.

Stable rollback baseline remains:

- V6.3.1;
- SHA-256 `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e`;
- immutable unless a separately governed decision explicitly replaces that rollback contract.

## Three truths

- **Public GitHub** — Product / Engineering Truth.
- **Local PNCC Data** — private Instance Configuration Truth.
- **Real Windows / Keenetic / VPS nodes** — Runtime Truth.

GitHub-hosted CI verifies engineering properties. It does **not** manufacture physical Runtime Truth or physical WinForms startup acceptance. Runtime/startup claims require trusted physical evidence and exact candidate/artifact identity.

## Fixed tunnel contract

- `127.0.0.1:1081` — `PRIMARY_AUTO`.
- `127.0.0.1:1080` — `RESERVE_MANUAL / MANUAL_ONLY`.
- PNCC automation must never start, stop, restart, recover or otherwise mutate the lifecycle of 1080.

## Development model

Current governed flow:

`Issue / ADWF Work Unit → exact base/branch → implementation → tests → PR → exact-head GitHub-hosted CI → deterministic artifact identity → trusted local Runtime Qualification / startup acceptance → sanitized evidence → authority/promotion boundary`

No public self-hosted Actions runner is attached to the home network.

The first Stable lifecycle established **L4 — Artifact + Runtime Truth**. Wave 5 bounded **ADWF Autonomous Execution** remains the strategic frontier, but writer-authority expansion is temporarily paused for the governed v7.0.0 startup-defect remediation. The corrected patch line must pass the mandatory physical startup contract: exact governed artifact → fresh extract → Windows PowerShell 5.1 preflight → package manifest PASS → Demo startup → `FUNCTIONAL_CONSISTENCY` PASS → WinForms UI observed → clean exit. The expected patch lineage is v7.0.1; no new promotion occurs before that exact-artifact evidence exists.

See:

- [`AGENTS.md`](AGENTS.md)
- [`SECURITY.md`](SECURITY.md)
- [`docs/roadmap/PNCC_PIPELINE_ROADMAP.md`](docs/roadmap/PNCC_PIPELINE_ROADMAP.md)
- [`docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md`](docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md)
- [`docs/adr/0001-public-github-runtime-boundary.md`](docs/adr/0001-public-github-runtime-boundary.md)
- [`docs/migration/PUBLIC_MIGRATION_SAFETY_GATE.md`](docs/migration/PUBLIC_MIGRATION_SAFETY_GATE.md)

## License

A project-wide open-source license is intentionally **not selected yet**. Legacy-code provenance and third-party dependency/license boundaries remain under review in `LICENSE_DECISION_REQUIRED.md`. Public visibility does not, by itself, grant a license to reuse the code.
