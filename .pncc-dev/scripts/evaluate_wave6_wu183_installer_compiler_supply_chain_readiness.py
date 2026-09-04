#!/usr/bin/env python3
import json
import pathlib
import sys

CONTRACT = pathlib.Path('.pncc-dev/contracts/wave6-wu183-installer-compiler-supply-chain-readiness.json')


def require(condition, code):
    if not condition:
        raise ValueError(code)


def evaluate(data):
    require(data.get('schema_version') == 1, 'SCHEMA_VERSION')
    require(data.get('work_unit_id') == 'PIPE-WU-183', 'WORK_UNIT_ID')
    require(data.get('role') == 'INSTALLER_COMPILER_SUPPLY_CHAIN_READINESS', 'ROLE')
    require(data.get('runtime_required') is False, 'RUNTIME_REQUIRED')

    dep = data.get('depends_on', {})
    require(dep.get('work_unit_id') == 'PIPE-WU-181', 'WU181_DEPENDENCY')
    require(dep.get('issue') == 412 and dep.get('pull_request') == 413, 'WU181_PROVIDER_IDENTITY')
    require(dep.get('qualified_head_sha') == 'a904a7e191fa11801955336851b18180f9f06e97', 'WU181_HEAD')
    require(dep.get('installer_implementation_authority') is False, 'WU181_IMPLEMENTATION_BOUNDARY')
    require(dep.get('binary_build_authority') is False, 'WU181_BUILD_BOUNDARY')

    tool = data.get('toolchain', {})
    exact = {
        'family': 'Inno Setup',
        'version': '7.1.0',
        'edition': 'x64',
        'release_date': '2026-08-12',
        'expected_asset_filename': 'innosetup-7.1.0-x64.exe',
        'upstream_repository': 'jrsoftware/issrc',
        'immutable_release_tag': 'is-7_1_0',
        'official_site_host': 'jrsoftware.org',
        'authenticode_publisher': 'Pyrsys B.V.',
    }
    for key, expected in exact.items():
        require(tool.get(key) == expected, 'TOOLCHAIN_' + key.upper())

    verify = data.get('verification', {})
    for key in (
        'https_required', 'exact_versioned_asset_required',
        'github_release_attestation_required', 'authenticode_publisher_match_required'
    ):
        require(verify.get(key) is True, 'VERIFY_' + key.upper())
    require(verify.get('release_attestation_repository') == 'jrsoftware/issrc', 'ATTESTATION_REPOSITORY')
    require(verify.get('release_attestation_command_template') == 'gh release verify-asset {asset} --repo jrsoftware/issrc', 'ATTESTATION_COMMAND')
    for key in (
        'mutable_latest_url_allowed', 'mirror_as_trust_anchor_allowed',
        'package_manager_as_sole_trust_source_allowed', 'fallback_on_attestation_failure_allowed'
    ):
        require(verify.get(key) is False, 'VERIFY_' + key.upper())
    require(verify.get('verification_failure_semantics') == 'FAIL_CLOSED', 'FAILURE_SEMANTICS')

    boundary = data.get('execution_boundary', {})
    require(boundary.get('github_hosted_runner_only') is True, 'HOSTED_RUNNER_BOUNDARY')
    for key in (
        'download_compiler_in_this_work_unit', 'execute_compiler_in_this_work_unit',
        'create_pncc_installer_binary', 'install_compiler', 'upload_release_asset',
        'default_branch_direct_write'
    ):
        require(boundary.get(key) is False, 'EXECUTION_' + key.upper())

    authority = data.get('authority', {})
    forbidden = (
        'installer_implementation', 'binary_build', 'product_runtime_mutation',
        'runtime_execution', 'release', 'tag', 'promotion', 'stable_transition',
        'ruleset_or_security_weakening', 'self_hosted_runner',
        'reserve_1080_lifecycle_mutation', 'primary_1081_lifecycle_mutation',
        'v631_mutation', 'secret_collection'
    )
    for key in forbidden:
        require(authority.get(key) is False, 'AUTHORITY_' + key.upper())

    require(data.get('allowed_repository_mutation_prefixes') == [
        '.pncc-dev/contracts/wave6-wu183-',
        '.pncc-dev/scripts/evaluate_wave6_wu183_',
        '.pncc-dev/tests/test_wu183_',
        '.github/workflows/wave6-wu183-'
    ], 'MUTATION_PREFIXES')
    require(data.get('classification') == 'READINESS_ONLY_NOT_RUNTIME_VERIFIED', 'CLASSIFICATION')
    return True


def main():
    try:
        data = json.loads(CONTRACT.read_text(encoding='utf-8'))
        evaluate(data)
    except Exception as exc:
        print('WU183_READINESS=BLOCKED')
        print('ERROR=' + str(exc))
        return 1
    print('WU183_READINESS=READY')
    print('TOOLCHAIN=Inno Setup 7.1.0 x64')
    print('AUTHORITY=READINESS_ONLY')
    return 0


if __name__ == '__main__':
    sys.exit(main())
