# PNCC Owner Physical Preflight

This is the first physical-node execution boundary after WU-017/WU-018. It is read-only with respect to PNCC, Proxifier, watchdog and tunnels.

The orchestrator checks out exact repository SHA `d1c2b9001dfd5db9ca81ff60ec3857671f19a56e`, acquires the governed RC14.39 provider artifact through the existing bootstrap, verifies candidate identity, searches the two governed local roots for the immutable V6.3.1 rollback artifact by SHA-256, runs the live preflight collector and emits a persistent transcript plus a return ZIP.

It does not start, stop, restart or recover 1080, 1081, PNCC, Proxifier or watchdog. `CI VERIFIED != RUNTIME VERIFIED`.
