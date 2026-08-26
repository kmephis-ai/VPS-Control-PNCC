# RC14.38 Public Sanitation Record

This directory is a **sanitized public migration snapshot derived from** the private exact
`VPS-Control-v7.0.0-rc14.38.zip` candidate.

It is **not** the exact runtime-qualified RC14.38 artifact and must not be presented as such.

Private candidate identity retained outside this directory:
- version: `v7.0.0-rc14.38`
- original ZIP SHA-256: `6d81137519a363ebf3d8503f33a344d8fdc75848d517cf732cb6d6d02394d727`
- status at migration: NOT Stable/DONE; runtime investigation continues independently.

Sanitation classes applied before public Git history:
- owner VPS exit address -> documentation/example TEST-NET value;
- owner router address -> documentation/example TEST-NET value;
- owner PuTTY saved-session name -> generic example session;
- owner-specific cloud-drive example path -> generic example path;
- original per-file package checksum list removed because sanitation changes bytes.

No credentials, DPAPI blobs, private keys, password files, runtime logs/evidence, process state,
portable PuTTY data, or local Git history are included.

The sanitized snapshot is a migration/provenance input. Runtime claims must refer to an exact
approved artifact and fresh trusted Windows evidence, not to this sanitized snapshot.
- publication-only EOF whitespace normalization applied to `modules/V7-Runtime.ps1` so `git diff --check` passes; no executable semantics changed.
