# Security Policy

## Public repository boundary

This repository contains product/engineering source only. It must not contain owner-specific runtime secrets, private topology, DPAPI blobs, password files, private keys, unsanitized logs, support bundles, or live node credentials.

Never commit or post in Issues/PRs:
- VPS/router passwords or tokens;
- private SSH keys / PPK files;
- DPAPI-encrypted owner data;
- PuTTY password files;
- unsanitized runtime logs/evidence;
- personal node configuration that is not required for the generic product.

Use documentation/example ranges and placeholders for public examples, such as `203.0.113.10`, `192.0.2.0/24`, `example.invalid`, `<VPS_HOST>`.

## Fixed PNCC safety properties

- `127.0.0.1:1081` is `PRIMARY_AUTO`.
- `127.0.0.1:1080` is `RESERVE_MANUAL / MANUAL_ONLY`.
- PNCC automation must never start, stop, restart, or recover port 1080.
- V6.3.1 is an immutable rollback baseline. Expected SHA-256: `385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e`.
- New PNCC product runtime must use DPAPI at rest and PuTTY `-pwfile`; plaintext `-pw` is forbidden.
- Host-key verification is fail-closed and must not be bypassed.
- CI verification is not physical runtime verification.
- Stable/DONE requires fresh trusted Windows runtime evidence.

## Public CI security

Public-repository CI uses GitHub-hosted runners only. Do not attach a home/LAN self-hosted runner to this public repository. Workflows for pull requests must not receive production secrets or arbitrary access to owner infrastructure.

Do not combine `pull_request_target` with checkout/execution of untrusted pull-request code.

## Reporting a vulnerability

Until a private security-reporting channel is configured, do not publish live credentials or exploit material in a public Issue. Contact the repository owner privately through an established trusted channel and provide only the minimum necessary information.
