#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / '.pncc-dev/contracts/wave6-wu184-installer-acquisition-receipt-policy.json'
WU184_VALIDATOR_PATH = ROOT / '.pncc-dev/scripts/validate_wave6_wu184_installer_acquisition_receipt.py'


def load_wu184_validator():
    spec = importlib.util.spec_from_file_location('pncc_wu184_receipt_validator', WU184_VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise ValueError('WU184_VALIDATOR_LOAD')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, 'validate', None)):
        raise ValueError('WU184_VALIDATOR_API')
    return module


def decision(decision_value, reason_codes):
    return {
        'schema_version': 1,
        'work_unit': 'PIPE-WU-185',
        'decision': decision_value,
        'reason_codes': list(reason_codes),
        'authority': 'RECEIPT_CONSUMER_ADMISSION_ONLY'
    }


def evaluate(receipt, policy=None, validator=None):
    try:
        if not isinstance(receipt, dict):
            raise ValueError('RECEIPT_NOT_OBJECT')
        if policy is None:
            policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
        if not isinstance(policy, dict) or policy.get('work_unit_id') != 'PIPE-WU-184':
            raise ValueError('WU184_POLICY_IDENTITY')
        if validator is None:
            validator = load_wu184_validator()
        result = validator.validate(receipt, policy)
        if result is not True:
            raise ValueError('WU184_VALIDATOR_NOT_TRUE')
        return decision('ADMITTED', ['WU184_RECEIPT_VERIFIED'])
    except Exception as exc:
        code = str(exc).strip() or exc.__class__.__name__
        return decision('BLOCKED', [code])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(json.dumps(decision('BLOCKED', ['USAGE']), sort_keys=True, separators=(',', ':')))
        return 2
    try:
        receipt = json.loads(pathlib.Path(argv[0]).read_text(encoding='utf-8'))
    except Exception as exc:
        code = str(exc).strip() or exc.__class__.__name__
        print(json.dumps(decision('BLOCKED', ['INPUT_READ_OR_JSON:' + code]), sort_keys=True, separators=(',', ':')))
        return 1
    result = evaluate(receipt)
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0 if result['decision'] == 'ADMITTED' else 1


if __name__ == '__main__':
    sys.exit(main())
