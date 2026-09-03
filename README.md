# VPS Control Center / PNCC

Public engineering repository for **Personal Network Control Center (PNCC)**, evolved from VPS Control Center.

## Repository status

**Stable v7.0.1 released / physically qualified / current Stable.**

The v7.0.1 patch line completed the governed source → deterministic artifact → physical startup acceptance → fresh Runtime Qualification → Runtime Authority → explicit Owner-authorized Release/Tag/Stable promotion lifecycle. The previously published v7.0.0 release remains immutable historical evidence with a separately recorded startup defect; it was not overwritten or retargeted.

Current Stable release identity:

- tag: `v7.0.1`;
- release: `VPS Control PNCC v7.0.1`;
- artifact: `VPS-Control-v7.0.1.zip`;
- SHA-256: `22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72`;
- size: `701893` bytes;
- physical startup acceptance: `PASS`;
- fresh nine-scope Runtime Qualification: `PASS`;
- Runtime Authority: `true`;
- release asset server digest verified: `true`;
- independent release re-download SHA/size verified: `true`;
- Stable declaration: `true`.

Machine-readable current completion truth is `.pncc-dev/attestations/stable-v7.0.1-completion.json`. Publication proof is `.pncc-dev/attestations/stable-release-tag-publication-v7.0.1.json`. Historical v7.0.0 completion and startup-defect attestations remain preserved separately and are not current Stable authority.

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

## State Snapshot CLI

Для безопасного read-only просмотра детерминированного `PNCC_STATE_SNAPSHOT` есть Windows PowerShell 5.1 CLI и checked-in synthetic example. Перед выводом можно отдельно проверить вход:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Test-PnccStateSnapshotInput.ps1 -InputPath .\tools\cli\examples\state-input.example.json
```

Затем вывести русский статус:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Show-PnccStateSnapshot.ps1 -InputPath .\tools\cli\examples\state-input.example.json
```

Для machine-readable результата validator или snapshot добавьте `-Json` к соответствующей команде. Пример является синтетическим и не доказывает текущее состояние Windows/VPS/Keenetic/туннелей: `CI VERIFIED != RUNTIME VERIFIED`.

Подробности: [`tools/cli/README.md`](tools/cli/README.md).

## Development model

Current governed flow:

`Issue / ADWF Work Unit → exact base/branch → implementation → tests → PR → exact-head GitHub-hosted CI → deterministic artifact identity → trusted local Runtime Qualification / startup acceptance → sanitized evidence → authority/promotion boundary`

No public self-hosted Actions runner is attached to the home network.

The project has achieved **L4 — Artifact + Runtime Truth**. With v7.0.1 now current Stable, **Wave 5 — ADWF Autonomous Execution is the current development frontier**. The next focus is durable autonomous Work Unit selection/execution, writer-lease enforcement, exact-head CI recovery, WAITING_RUNTIME semantics, and session handoff/resume—while retaining explicit Owner authority at runtime, security and release/promotion boundaries.

See:

- [`AGENTS.md`](AGENTS.md)
- [`SECURITY.md`](SECURITY.md)
- [`docs/roadmap/PNCC_PIPELINE_ROADMAP.md`](docs/roadmap/PNCC_PIPELINE_ROADMAP.md)
- [`docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md`](docs/architecture/PNCC_TARGET_DEVELOPMENT_PIPELINE.md)
- [`docs/adr/0001-public-github-runtime-boundary.md`](docs/adr/0001-public-github-runtime-boundary.md)
- [`docs/migration/PUBLIC_MIGRATION_SAFETY_GATE.md`](docs/migration/PUBLIC_MIGRATION_SAFETY_GATE.md)

## License

A project-wide open-source license is intentionally **not selected yet**. Legacy-code provenance and third-party dependency/license boundaries remain under review in `LICENSE_DECISION_REQUIRED.md`. Public visibility does not, by itself, grant a license to reuse the code.
