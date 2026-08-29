# VPS Control Center / PNCC

Public engineering repository for **Personal Network Control Center (PNCC)**, evolved from VPS Control Center.

## Repository status

**Stable v7.0.0 released / post-Stable development active.**

The first governed Stable release completed the full source → deterministic artifact → physical Runtime Qualification → Runtime Authority → Owner-authorized promotion lifecycle.

Stable release identity:

- tag: `v7.0.0`;
- release: `VPS Control PNCC v7.0.0`;
- artifact: `VPS-Control-v7.0.0.zip`;
- SHA-256: `1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599`;
- size: `700897` bytes;
- fresh Stable nine-scope Runtime Qualification: `PASS`;
- Runtime Authority: `true`;
- release asset independently re-downloaded and SHA/size verified.

Machine-readable completion authority is recorded in `.pncc-dev/attestations/stable-v7.0.0-completion.json`.

Stable rollback baseline remains:

- V6.3.1;
- SHA-256 `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e`;
- immutable unless a separately governed decision explicitly replaces that rollback contract.

## Three truths

- **Public GitHub** — Product / Engineering Truth.
- **Local PNCC Data** — private Instance Configuration Truth.
- **Real Windows / Keenetic / VPS nodes** — Runtime Truth.

GitHub-hosted CI verifies engineering properties. It does **not** manufacture physical Runtime Truth. Runtime claims require trusted physical evidence and exact candidate/artifact identity.

## Fixed tunnel contract

- `127.0.0.1:1081` — `PRIMARY_AUTO`.
- `127.0.0.1:1080` — `RESERVE_MANUAL / MANUAL_ONLY`.
- PNCC automation must never start, stop, restart, recover or otherwise mutate the lifecycle of 1080.

## Development model

Current governed flow:

`Issue / ADWF Work Unit → exact base/branch → implementation → tests → PR → exact-head GitHub-hosted CI → deterministic artifact identity → trusted local Runtime Qualification → sanitized evidence → authority/promotion boundary`

No public self-hosted Actions runner is attached to the home network.

The first Stable lifecycle established **L4 — Artifact + Runtime Truth**. The next development frontier is Wave 5: bounded **ADWF Autonomous Execution**, while security/runtime/promotion boundaries continue to fail closed and require explicit authority where defined.

See:

- [`AGENTS.md`](AGENTS.md)
- [`SECURITY.md`](SECURITY.md)
- [`docs/roadmap/PNCC_PIPELINE_ROADMAP.md`](docs/roadmap/PNCC_PIPELINE_ROADMAP.md)
- [`docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md`](docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md)
- [`docs/adr/0001-public-github-runtime-boundary.md`](docs/adr/0001-public-github-runtime-boundary.md)
- [`docs/migration/PUBLIC_MIGRATION_SAFETY_GATE.md`](docs/migration/PUBLIC_MIGRATION_SAFETY_GATE.md)

## License

A project-wide open-source license is intentionally **not selected yet**. Legacy-code provenance and third-party dependency/license boundaries remain under review in `LICENSE_DECISION_REQUIRED.md`. Public visibility does not, by itself, grant a license to reuse the code.
