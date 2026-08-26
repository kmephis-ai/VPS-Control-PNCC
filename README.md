# VPS Control Center / PNCC

Public engineering repository for the migration of VPS Control Center into **Personal Network Control Center (PNCC)**.

## Repository status

**Public bootstrap / migration in progress.**

This repository is intentionally not yet a copy of the owner's local VPS-Control working directory. Product source will be imported only after the Public Migration Safety Gate proves that the staged tree contains no private instance state, secrets, sensitive runtime evidence, or unreviewed third-party material.

Current migration candidate tracked outside GitHub source import:

- `v7.0.0-rc14.38`
- SHA-256 `6d81137519a363ebf3d8503f33a344d8fdc75848d517cf732cb6d6d02394d727`
- **not Stable/DONE** without fresh Windows runtime evidence.

Stable rollback baseline:

- V6.3.1
- SHA-256 `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e`
- immutable during the migration.

## Three truths

- **Public GitHub** — Product / Engineering Truth.
- **Local PNCC Data** — private Instance Configuration Truth.
- **Real Windows / Keenetic / VPS nodes** — Runtime Truth.

CI verifies engineering properties. It does **not** prove physical network behavior.

## Fixed tunnel contract

- `127.0.0.1:1081` — `PRIMARY_AUTO`.
- `127.0.0.1:1080` — `RESERVE_MANUAL / MANUAL_ONLY`.
- PNCC automation never start/stops/restarts/recovers 1080.

## Development model

Target flow:

`Issue / ADWF Work Unit → branch → implementation → tests → PR → GitHub-hosted CI → exact SHA/artifact → trusted local runtime qualification → sanitized evidence → classification/promotion`

No public self-hosted Actions runner is attached to the home network.

See:

- [`AGENTS.md`](AGENTS.md)
- [`SECURITY.md`](SECURITY.md)
- [`docs/adr/0001-public-github-runtime-boundary.md`](docs/adr/0001-public-github-runtime-boundary.md)
- [`docs/migration/PUBLIC_MIGRATION_SAFETY_GATE.md`](docs/migration/PUBLIC_MIGRATION_SAFETY_GATE.md)

## License

License selection is intentionally deferred until legacy-code provenance and bundled third-party components are reviewed. Public visibility does not, by itself, grant a license to reuse the code.
