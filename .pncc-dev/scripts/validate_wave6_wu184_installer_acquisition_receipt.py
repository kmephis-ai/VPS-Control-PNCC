#!/usr/bin/env python3
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / '.pncc-dev/contracts/wave6-wu184-installer-acquisition-receipt-policy.json'

TOP_KEYS = {'schema_version','receipt_type','policy_source','toolchain','artifact','source','github_release_attestation','authenticode','acquisition','verification'}
TOOL_KEYS = {'family','version','edition','upstream_repository','immutable_release_tag','release_id','asset_id','asset_filename'}
ARTIFACT_KEYS = {'sha256','byte_count'}
SOURCE_KEYS = {'url','mutable_latest','mirror_trust_anchor','package_manager_sole_trust'}
ATTEST_KEYS = {'verified','repository','verifier'}
AUTH_KEYS = {'verified','publisher'}
ACQ_KEYS = {'runner_provider','runner_os','runner_image','acquired_at_utc'}
VERIFY_KEYS = {'status','fail_closed'}
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
UTC_RE = re.compile(r'^20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$')


def require(condition, code):
    if not condition:
        raise ValueError(code)


def exact_keys(obj, keys, code):
    require(isinstance(obj, dict) and set(obj) == keys, code)


def validate(receipt, policy):
    exact_keys(receipt, TOP_KEYS, 'TOP_LEVEL_KEYS')
    require(receipt['schema_version'] == 1, 'SCHEMA_VERSION')
    required = policy['required_receipt']
    require(receipt['receipt_type'] == required['receipt_type'], 'RECEIPT_TYPE')
    require(receipt['policy_source'] == required['policy_source'], 'POLICY_SOURCE')

    tool = receipt['toolchain']; exact_keys(tool, TOOL_KEYS, 'TOOLCHAIN_KEYS')
    pinned = policy['toolchain']
    for key in TOOL_KEYS:
        expected_key = 'asset_filename' if key == 'asset_filename' else key
        require(tool[key] == pinned[expected_key], 'TOOLCHAIN_' + key.upper())

    artifact = receipt['artifact']; exact_keys(artifact, ARTIFACT_KEYS, 'ARTIFACT_KEYS')
    require(isinstance(artifact['sha256'], str) and SHA256_RE.fullmatch(artifact['sha256']) is not None, 'ARTIFACT_SHA256_FORMAT')
    require(artifact['sha256'] == pinned['asset_sha256'], 'ARTIFACT_SHA256')
    require(type(artifact['byte_count']) is int and artifact['byte_count'] > 0, 'ARTIFACT_BYTE_COUNT_FORMAT')
    require(artifact['byte_count'] == pinned['asset_byte_count'], 'ARTIFACT_BYTE_COUNT')

    source = receipt['source']; exact_keys(source, SOURCE_KEYS, 'SOURCE_KEYS')
    require(source['url'] == pinned['asset_url'], 'SOURCE_URL')
    require(source['url'].startswith('https://'), 'SOURCE_HTTPS')
    require('/latest/' not in source['url'].lower(), 'SOURCE_MUTABLE_LATEST_URL')
    require(source['mutable_latest'] is required['mutable_latest'], 'SOURCE_MUTABLE_LATEST')
    require(source['mirror_trust_anchor'] is required['mirror_trust_anchor'], 'SOURCE_MIRROR_TRUST')
    require(source['package_manager_sole_trust'] is required['package_manager_sole_trust'], 'SOURCE_PACKAGE_MANAGER_TRUST')

    att = receipt['github_release_attestation']; exact_keys(att, ATTEST_KEYS, 'ATTESTATION_KEYS')
    require(att['verified'] is required['github_release_attestation_verified'], 'ATTESTATION_VERIFIED')
    require(att['repository'] == required['github_release_attestation_repository'], 'ATTESTATION_REPOSITORY')
    require(att['verifier'] == required['github_release_attestation_verifier'], 'ATTESTATION_VERIFIER')

    auth = receipt['authenticode']; exact_keys(auth, AUTH_KEYS, 'AUTHENTICODE_KEYS')
    require(auth['verified'] is required['authenticode_verified'], 'AUTHENTICODE_VERIFIED')
    require(auth['publisher'] == pinned['authenticode_publisher'], 'AUTHENTICODE_PUBLISHER')

    acq = receipt['acquisition']; exact_keys(acq, ACQ_KEYS, 'ACQUISITION_KEYS')
    require(acq['runner_provider'] == required['runner_provider'], 'RUNNER_PROVIDER')
    require(acq['runner_os'] == required['runner_os'], 'RUNNER_OS')
    require(isinstance(acq['runner_image'], str) and acq['runner_image'].strip(), 'RUNNER_IMAGE')
    ts = acq['acquired_at_utc']
    require(isinstance(ts, str) and UTC_RE.fullmatch(ts) is not None, 'ACQUIRED_AT_FORMAT')
    try:
        dt.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as exc:
        raise ValueError('ACQUIRED_AT_VALUE') from exc

    verification = receipt['verification']; exact_keys(verification, VERIFY_KEYS, 'VERIFICATION_KEYS')
    require(verification['status'] == required['verification_status'], 'VERIFICATION_STATUS')
    require(verification['fail_closed'] is required['fail_closed'], 'VERIFICATION_FAIL_CLOSED')
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('WU184_RECEIPT=BLOCKED')
        print('ERROR=USAGE')
        return 2
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
        receipt = json.loads(pathlib.Path(argv[0]).read_text(encoding='utf-8'))
        validate(receipt, policy)
    except Exception as exc:
        print('WU184_RECEIPT=BLOCKED')
        print('ERROR=' + str(exc))
        return 1
    print('WU184_RECEIPT=VERIFIED')
    print('POLICY=PIPE-WU-184')
    return 0


if __name__ == '__main__':
    sys.exit(main())
