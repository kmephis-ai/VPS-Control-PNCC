#!/usr/bin/env python3
from __future__ import annotations
import argparse,re,subprocess,sys
from pathlib import Path
TOKEN = r"(?<!['\"])(['\"])-pw\1(?!['\"])"
ARRAY_ASSIGN = re.compile(r"(?i)\$[A-Za-z_][A-Za-z0-9_]*\s*\+?=\s*@\([^\r\n]*?" + TOKEN)
DIRECT_INVOKE = re.compile(r"(?i)(?:Start-Process|&\s*\$?[A-Za-z_][A-Za-z0-9_]*)[^\r\n]{0,400}?" + TOKEN)
SAMPLES={"bad_append":("$a+=@('-pw',$pw)",True),"bad_array":("$a=@('-batch','-ssh','-pw',$pw,'host')",True),"good_pwfile":("$a+=@('-pwfile',$pwfile)",False),"redaction":("if($v -in @('-pw','-pwfile')){$redactNext=$true}",False),"self_check":("$engineText.Contains('$arguments+=@(''-pw'',$password)')",False)}
def executable_plaintext_pw(line:str)->bool:return bool(ARRAY_ASSIGN.search(line) or DIRECT_INVOKE.search(line))
def self_test()->None:
    failed=[]
    for name,(sample,expected) in SAMPLES.items():
        actual=executable_plaintext_pw(sample)
        if actual!=expected:failed.append(f"{name}: expected={expected} actual={actual}")
    if failed:raise SystemExit("scanner self-test failed:\n"+"\n".join(failed))
    print("PUTTY_PASSWORD_TRANSPORT_SCANNER_SELF_TEST=PASS")
def tracked_files(root:Path)->list[str]:
    cp=subprocess.run(["git","-C",str(root),"ls-files","*.ps1","*.psm1"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if cp.returncode!=0:raise SystemExit("git ls-files failed: "+cp.stderr.strip())
    return [x for x in cp.stdout.splitlines() if x]
def scan(root:Path)->None:
    bad=[]
    for raw in tracked_files(root):
        p=Path(raw)
        if "legacy" in p.parts:continue
        full=root/p
        try:text=full.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:continue
        for line_no,line in enumerate(text.splitlines(),1):
            if executable_plaintext_pw(line):bad.append(f"{raw}:{line_no}")
    if bad:raise SystemExit("Executable plaintext PuTTY/Plink -pw argv is forbidden:\n"+"\n".join(bad))
    print("PUTTY_PASSWORD_TRANSPORT=PASS EXECUTABLE_PLAINTEXT_PW=0")
def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--repository-root",default=".");ap.add_argument("--self-test",action="store_true");args=ap.parse_args();self_test()
    if not args.self_test:scan(Path(args.repository_root).resolve())
    return 0
if __name__=="__main__":raise SystemExit(main())
