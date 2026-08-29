#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import Any

SHA40=re.compile(r'^[0-9a-f]{40}$'); SHA256=re.compile(r'^[0-9a-f]{64}$')
REQ_KEYS={'schema_version','contract_id','request_id','origin_work_unit_id','candidate','required_scopes','expected_invariants','state','runtime_authority','promotion_eligible'}
CAND_KEYS={'candidate_id','source_sha','artifact_filename','artifact_sha256','artifact_size_bytes','provider_artifact_id','provider_artifact_digest','provider_build_run_id'}
INV_KEYS={'primary_auto_port','reserve_manual_port','reserve_manual_lifecycle','v6_3_1_sha256','putty_password_argument','plaintext_pw_allowed','hostkey_verification_disable_allowed'}
RES_KEYS={'schema_version','contract_id','request_id','candidate','producer','environment','checks','evidence_bundle','qualification_state','failure_classification','runtime_authority','promotion_eligible'}
PROD_KEYS={'source_plane','agent_id','runtime_agent_version','validation_lab_version'}
ENV_KEYS={'windows_version','powershell_version'}
CHECK_KEYS={'scope','result','exit_code','failure_class','evidence_refs'}
EVID_KEYS={'sha256','private_location_ref','sanitation_state'}

class ContractError(RuntimeError): pass

def load(path: Path)->dict[str,Any]:
    v=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(v,dict): raise ContractError(f'{path}: object required')
    return v

def exact(v:Any, keys:set[str], label:str):
    if not isinstance(v,dict): raise ContractError(f'{label}: object required')
    a=set(v); miss=sorted(keys-a); unk=sorted(a-keys)
    if miss or unk: raise ContractError(f'{label}: schema mismatch missing={miss} unknown={unk}')

def valid_candidate(c:Any,label:str):
    exact(c,CAND_KEYS,label)
    if not isinstance(c['candidate_id'],str) or not c['candidate_id']: raise ContractError(f'{label}: candidate_id')
    if not isinstance(c['source_sha'],str) or not SHA40.fullmatch(c['source_sha']): raise ContractError(f'{label}: source_sha')
    for k in ('artifact_sha256','provider_artifact_digest'):
        if not isinstance(c[k],str) or not SHA256.fullmatch(c[k]): raise ContractError(f'{label}: {k}')
    for k in ('artifact_size_bytes','provider_artifact_id','provider_build_run_id'):
        if not isinstance(c[k],int) or isinstance(c[k],bool) or c[k]<=0: raise ContractError(f'{label}: {k}')
    if not isinstance(c['artifact_filename'],str) or '/' in c['artifact_filename'] or '\\' in c['artifact_filename']: raise ContractError(f'{label}: artifact_filename')

def governed_candidates(policy:dict[str,Any])->list[dict[str,Any]]:
    values=policy.get('governed_candidates')
    if values is None:
        values=[policy.get('current_candidate')]
    if not isinstance(values,list) or not values: raise ContractError('policy governed_candidates')
    out=[]; ids=set()
    for i,c in enumerate(values):
        valid_candidate(c,f'policy.governed_candidates[{i}]')
        cid=c['candidate_id']
        if cid in ids: raise ContractError('duplicate governed candidate id')
        ids.add(cid); out.append(c)
    current=policy.get('current_candidate')
    valid_candidate(current,'policy.current_candidate')
    active_id=policy.get('active_candidate_id',current['candidate_id'])
    if active_id!=current['candidate_id']: raise ContractError('policy active/current candidate mismatch')
    if not any(c==current for c in out): raise ContractError('current candidate must be governed')
    return out

def validate_request(req:dict[str,Any], policy:dict[str,Any])->None:
    exact(req,REQ_KEYS,'request'); valid_candidate(req['candidate'],'request.candidate')
    if req['schema_version']!=1 or req['contract_id']!=policy['request_contract_id']: raise ContractError('request contract identity')
    governed=governed_candidates(policy)
    if sum(1 for c in governed if c==req['candidate'])!=1: raise ContractError('request candidate is not an exact governed candidate')
    scopes=req['required_scopes']; expected=policy['required_scopes']
    if not isinstance(scopes,list) or len(scopes)!=len(set(scopes)) or scopes!=expected: raise ContractError('request required_scopes must equal ordered policy scopes')
    exact(req['expected_invariants'],INV_KEYS,'request.expected_invariants')
    if req['expected_invariants']!=policy['fixed_invariants']: raise ContractError('request invariants mismatch policy')
    if req['state']!='RUNTIME_PENDING' or req['runtime_authority'] is not False or req['promotion_eligible'] is not False: raise ContractError('request authority/state invalid')

def validate_result(req:dict[str,Any], result:dict[str,Any], policy:dict[str,Any])->str:
    validate_request(req,policy)
    exact(result,RES_KEYS,'result'); valid_candidate(result['candidate'],'result.candidate')
    if result['schema_version']!=1 or result['contract_id']!=policy['result_contract_id']: raise ContractError('result contract identity')
    if result['request_id']!=req['request_id'] or result['candidate']!=req['candidate']: raise ContractError('result request/candidate substitution')
    exact(result['producer'],PROD_KEYS,'result.producer')
    if result['producer'].get('source_plane')!=policy['trusted_result_source_plane']: raise ContractError('result source plane must be PRIVATE_RUNTIME')
    for k in ('agent_id','runtime_agent_version','validation_lab_version'):
        if not isinstance(result['producer'].get(k),str) or not result['producer'][k].strip(): raise ContractError(f'result.producer.{k}')
    exact(result['environment'],ENV_KEYS,'result.environment')
    for k in ENV_KEYS:
        if not isinstance(result['environment'].get(k),str) or not result['environment'][k].strip(): raise ContractError(f'result.environment.{k}')
    checks=result['checks']
    if not isinstance(checks,list): raise ContractError('result.checks array')
    by={}; allowed_classes=set(policy['failure_classes'])
    for i,ch in enumerate(checks):
        exact(ch,CHECK_KEYS,f'result.checks[{i}]')
        scope=ch['scope']
        if scope in by: raise ContractError('duplicate result scope')
        if scope not in policy['required_scopes']: raise ContractError('unknown result scope')
        if ch['result'] not in {'PASS','FAIL','BLOCKED'}: raise ContractError('invalid check result')
        if not isinstance(ch['exit_code'],int) or isinstance(ch['exit_code'],bool): raise ContractError('exit_code integer required')
        refs=ch['evidence_refs']
        if not isinstance(refs,list) or not refs or len(refs)!=len(set(refs)) or not all(isinstance(x,str) and x for x in refs): raise ContractError('nonempty unique evidence_refs required')
        fc=ch['failure_class']
        if ch['result']=='PASS':
            if fc is not None or ch['exit_code']!=0: raise ContractError('PASS requires exit_code=0 and null failure_class')
        else:
            if fc not in allowed_classes or ch['exit_code']==0: raise ContractError('non-PASS requires failure_class and nonzero exit')
        by[scope]=ch
    if set(by)!=set(policy['required_scopes']): raise ContractError('result must contain every required scope exactly once')
    exact(result['evidence_bundle'],EVID_KEYS,'result.evidence_bundle')
    eb=result['evidence_bundle']
    if not isinstance(eb['sha256'],str) or not SHA256.fullmatch(eb['sha256']): raise ContractError('evidence bundle sha256')
    if not isinstance(eb['private_location_ref'],str) or not eb['private_location_ref'].strip(): raise ContractError('private location ref')
    if eb['sanitation_state']!='PRIVATE': raise ContractError('raw runtime evidence must remain PRIVATE')
    states={c['result'] for c in checks}; q=result['qualification_state']; top=result['failure_classification']
    if 'FAIL' in states: expected='FAILED'
    elif 'BLOCKED' in states: expected='BLOCKED'
    else: expected='RUNTIME_VERIFIED'
    if q!=expected: raise ContractError(f'qualification_state mismatch expected={expected}')
    if expected=='RUNTIME_VERIFIED':
        if top is not None or result['runtime_authority'] is not True: raise ContractError('RUNTIME_VERIFIED requires runtime_authority=true and null failure classification')
    else:
        classes={c['failure_class'] for c in checks if c['result']!='PASS'}
        if top not in allowed_classes or top not in classes: raise ContractError('blocked/failed top failure classification must match a non-PASS check')
        if result['runtime_authority'] is not False: raise ContractError('non-verified result cannot grant runtime authority')
    if result['promotion_eligible'] is not False: raise ContractError('runtime result cannot grant promotion eligibility')
    return expected

def evaluate(root:Path, request_path:Path, result_path:Path|None=None)->dict[str,Any]:
    policy=load(root/'.pncc-dev/contracts/runtime-qualification-policy.json'); request=load(request_path); validate_request(request,policy)
    if result_path is None:
        return {'state':'WAITING_RUNTIME_EVIDENCE','runtime_authority':False,'promotion_eligible':False,'request_id':request['request_id'],'candidate':request['candidate']}
    result=load(result_path); state=validate_result(request,result,policy)
    return {'state':state,'runtime_authority':result['runtime_authority'],'promotion_eligible':False,'request_id':request['request_id'],'candidate':request['candidate'],'failure_classification':result['failure_classification']}

def main(argv=None)->int:
    p=argparse.ArgumentParser(); p.add_argument('--repository-root',type=Path,default=Path('.')); p.add_argument('--request',type=Path,required=True); p.add_argument('--result',type=Path); p.add_argument('--require-runtime-verified',action='store_true'); a=p.parse_args(argv)
    try: out=evaluate(a.repository_root.resolve(),a.request.resolve(),a.result.resolve() if a.result else None)
    except Exception as e:
        print(f'RUNTIME_QUALIFICATION_CONTRACT=FAIL ERROR={e}',file=sys.stderr); return 2
    print(f"RUNTIME_QUALIFICATION_STATE={out['state']} REQUEST_ID={out['request_id']} CANDIDATE_ID={out['candidate']['candidate_id']} ARTIFACT_SHA256={out['candidate']['artifact_sha256']} RUNTIME_AUTHORITY={str(out['runtime_authority']).lower()} PROMOTION_ELIGIBLE=false")
    if a.require_runtime_verified and out['state']!='RUNTIME_VERIFIED':
        print('RUNTIME_QUALIFICATION_NOT_VERIFIED',file=sys.stderr); return 3
    return 0
if __name__=='__main__': raise SystemExit(main())
