# Public Migration Safety Gate

This gate must PASS before PNCC product source is imported into public Git history.

## Current migration baseline

- Target repository: `kmephis-ai/VPS-Control-PNCC`.
- Public bootstrap branch: `migration/public-bootstrap-a1`.
- Current exact candidate under investigation: `v7.0.0-rc14.38`.
- Candidate SHA-256: `6d81137519a363ebf3d8503f33a344d8fdc75848d517cf732cb6d6d02394d727`.
- V6.3.1 immutable SHA-256: `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e`.

Repository migration does not make RC14.38 stable and must not mutate it.

## Gate A — source inventory

Before import, classify every candidate item as one of:
- PRODUCT_SOURCE;
- PRODUCT_TEST;
- PRODUCT_DOC;
- SANITIZED_EXAMPLE;
- GENERATED_BUILD_ARTIFACT;
- PRIVATE_INSTANCE_CONFIG;
- SECRET_OR_CREDENTIAL;
- RUNTIME_STATE;
- RUNTIME_LOG_OR_EVIDENCE;
- THIRD_PARTY_BINARY_OR_SOURCE;
- LEGACY_IMMUTABLE_BASELINE.

Unknown classification is BLOCKED, not PASS.

## Gate B — prohibited public material

The import tree must contain no:
- real passwords/tokens/private keys;
- `.ppk`, `.pem`, `.pfx`, owner DPAPI data or password files;
- unsanitized runtime logs/evidence/support bundles;
- active node profiles with private values;
- owner-specific topology where a generic placeholder is sufficient;
- local process state, PID files, heartbeat/state files;
- private PuTTY session/host material unless explicitly proven non-sensitive and required;
- archives containing any prohibited content.

## Gate C — source scanning

Scan the complete staged tree before commit for:
- known secret formats;
- credential keywords with assigned values;
- plaintext PuTTY `-pw` usage in new PNCC product runtime;
- private-key headers;
- absolute owner-specific paths;
- real instance IP/host values that should be examples;
- ignored/prohibited extensions/directories;
- nested archives.

False positives must be classified and documented; they must not simply be suppressed globally.

## Gate D — legacy provenance

Before publishing legacy source:
- prove source is owned/licensable for publication;
- identify bundled third-party binaries/source and their licenses;
- do not publish a license for the whole repository until provenance review supports that choice;
- preserve V6.3.1 as immutable rollback evidence without exposing private instance state.

## Gate E — CI/bootstrap

Before first product-source PR:
- public-safety workflow exists on `main`;
- workflow permissions are read-only by default;
- no public self-hosted runner is used;
- repository-integrity and secret-boundary checks run on GitHub-hosted runners;
- CI result is explicitly labeled engineering verification, not runtime verification.

## Gate F — runtime separation

The public repository must not directly execute arbitrary PR code on the home network. Real runtime qualification is performed by a separate typed local execution mechanism that consumes an approved exact SHA/artifact and returns sanitized machine-verifiable evidence.

## Exit condition

Only after Gates A–F are PASS may the sanitized PNCC source baseline be committed to a migration branch and reviewed for merge.
