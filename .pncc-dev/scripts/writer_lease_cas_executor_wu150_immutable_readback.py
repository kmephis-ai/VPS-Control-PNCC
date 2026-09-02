#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / ".pncc-dev/scripts/writer_lease_cas_executor_wu149.py"


def load_core() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pncc_wu149_cas_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("CORE_IMPORT_FAILED")
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    return core


def install_immutable_registry_reads(core: ModuleType) -> ModuleType:
    original_gh: Callable[..., Any] = core.gh
    mutable_path = f"/contents/{core.REGISTRY_PATH}?ref={urllib.parse.quote(core.STATE_BRANCH, safe='')}"

    def pinned_gh(method: str, path: str, token: str, body: Any = None) -> Any:
        if method == "GET" and path == mutable_path:
            observed_head = original_gh(
                "GET", f"/git/ref/heads/{core.STATE_BRANCH}", token
            )["object"]["sha"]
            immutable_path = (
                f"/contents/{core.REGISTRY_PATH}?ref="
                f"{urllib.parse.quote(observed_head, safe='')}"
            )
            return original_gh(method, immutable_path, token, body)
        return original_gh(method, path, token, body)

    core.gh = pinned_gh
    return core


def main() -> int:
    core = install_immutable_registry_reads(load_core())
    try:
        return core.main()
    except core.ExecutorError as exc:
        print("WRITER_LEASE_CAS_EXECUTOR=BLOCKED")
        print("ERROR=" + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
