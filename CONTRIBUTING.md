# Contributing to PNCC

PNCC is currently in public-bootstrap/migration phase. Contributions are welcome only within the repository's safety and evidence contracts.

## Before proposing a change

- Read `AGENTS.md`, `SECURITY.md` and the migration safety gate.
- Never include real credentials, private topology, DPAPI data, password files, private keys, unsanitized logs or owner-specific runtime state.
- Use generic/sanitized fixtures and documentation addresses.

## Change model

- Work through a branch and pull request.
- Keep one writer for overlapping conflict domains.
- Add or update tests for deterministic defects.
- Do not weaken CI, security boundaries, tunnel lifecycle policy, host-key verification, or immutable-baseline checks merely to make a change pass.

## Runtime claims

GitHub-hosted CI may establish `CI VERIFIED`. It cannot establish `RUNTIME VERIFIED` for Proxifier, the owner's VPS, router, or local Windows environment.

A change that affects real routing is promoted only after an approved exact SHA/artifact is exercised by the trusted local runtime mechanism and returns sanitized machine-verifiable evidence.

## Failure classification

Do not mutate product code for validator/harness/environment failures. A product change/new candidate requires a proven product defect.

## License/provenance

Until the repository license/provenance review is complete, do not import third-party code or binaries without explicit provenance and license documentation.
