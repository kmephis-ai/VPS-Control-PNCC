#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Iterable

V631_SHA256 = "385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e"

REQUIRED_MARKERS = {
    "WINDOWS10_INTENT": re.compile(r"(?i)windows\s*10"),
    "POWERSHELL51_INTENT": re.compile(r"(?i)powershell\s*5\.1"),
    "RESERVE_1080_MANUAL_ONLY": re.compile(r"(?i)1080.*(?:manual[_ -]?only|reserve[_ -]?manual)|(?:manual[_ -]?only|reserve[_ -]?manual).*1080"),
    "PRIMARY_1081": re.compile(r"(?i)1081.*primary[_ -]?auto|primary[_ -]?auto.*1081"),
    "V631_IMMUTABLE": re.compile(re.escape(V631_SHA256), re.I),
    "HOSTKEY_FAIL_CLOSED": re.compile(r"(?i)host[- ]?key.*(?:fail[- ]?closed|verify|verification)"),
}

FORBIDDEN = {
    "PLAINTEXT_PUTTY_PASSWORD": re.compile(r"(?i)(?:plink|putty|pscp|psftp)?[^\n]{0,120}(?:^|\s)-pw(?:\s|=)"),
    "EMBEDDED_PASSWORD": re.compile(r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\";]{3,}"),
    "HOSTKEY_BYPASS": re.compile(r"(?i)(?:no[-_ ]?host[-_ ]?key|skip[-_ ]?host[-_ ]?key|disable[^\n]{0,40}host[-_ ]?key|host[-_ ]?key[^\n]{0,40}(?:false|off|ignore|bypass))"),
    "AUTO_1080_LIFECYCLE": re.compile(r"(?i)(?:start|stop|restart|recover|monitor|watchdog|auto(?:matic)?)[^\n]{0,80}1080|1080[^\n]{0,80}(?:start|stop|restart|recover|monitor|watchdog|auto(?:matic)?)"),
    "V631_MUTATION": re.compile(r"(?i)(?:replace|overwrite|patch|modify|mutate|delete|remove)[^\n]{0,100}(?:v?6\.3\.1|385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e)"),
    "INSTALLER_NETWORK_EXEC": re.compile(r"(?i)(?:curl|wget|invoke-webrequest|start-bitstransfer|downloadstring|downloadfile|https?://)"),
    "COMPILER_EXEC": re.compile(r"(?i)\b(?:iscc(?:\.exe)?|innosetup|innosetupcompiler)\b"),
    "SECURITY_WEAKENING": re.compile(r"(?i)(?:disable|weaken|bypass|ignore)[^\n]{0,60}(?:security|ruleset|protection|verification|signature|tls|certificate)"),
}

@dataclass(frozen=True)
class Decision:
    classification: str
    reasons: tuple[str, ...]

    @property
    def admitted(self) -> bool:
        return self.classification == "ADMITTED"

    def to_dict(self) -> dict:
        return {"classification": self.classification, "reasons": list(self.reasons)}


def validate_text(text: str) -> Decision:
    reasons: list[str] = []
    if not isinstance(text, str) or not text.strip():
        return Decision("BLOCKED", ("EMPTY_PROPOSAL_TEXT",))

    for code, rx in REQUIRED_MARKERS.items():
        if not rx.search(text):
            reasons.append(f"MISSING_{code}")

    for code, rx in FORBIDDEN.items():
        if rx.search(text):
            reasons.append(code)

    # Fail closed when text tries to redefine either fixed port contract ambiguously.
    if re.search(r"(?i)1080[^\n]{0,80}primary[_ -]?auto|primary[_ -]?auto[^\n]{0,80}1080", text):
        reasons.append("PORT_ROLE_CONTRADICTION_1080")
    if re.search(r"(?i)1081[^\n]{0,80}(?:manual[_ -]?only|reserve[_ -]?manual)", text):
        reasons.append("PORT_ROLE_CONTRADICTION_1081")

    reasons = sorted(set(reasons))
    return Decision("ADMITTED" if not reasons else "BLOCKED", tuple(reasons))


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="WU188 pure in-memory installer-definition proposal validator")
    p.add_argument("--text", required=True, help="Proposal text supplied directly; no filesystem input is accepted")
    args = p.parse_args(list(argv) if argv is not None else None)
    decision = validate_text(args.text)
    print(json.dumps(decision.to_dict(), sort_keys=True))
    return 0 if decision.admitted else 2


if __name__ == "__main__":
    sys.exit(main())
