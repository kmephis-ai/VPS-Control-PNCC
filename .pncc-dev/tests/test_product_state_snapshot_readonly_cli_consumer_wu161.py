import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "cli" / "Get-PnccStateSnapshot.ps1"
CONTRACT = ROOT / ".pncc-dev" / "contracts" / "product-state-snapshot-readonly-cli-consumer-wu161.json"
FOUNDATION = ROOT / "src" / "foundations" / "windows-v7" / "V7-StateSnapshot.ps1"


def test_wu161_cli_contract_is_bounded_read_only_and_ps51_compatible():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    script = SCRIPT.read_text(encoding="utf-8-sig")

    assert contract["schema_version"] == 1
    assert contract["role"] == "PRODUCT_STATE_SNAPSHOT_READONLY_CLI_CONSUMER"
    assert contract["work_unit_id"] == "PIPE-WU-161"
    assert contract["runtime_required"] is False
    assert contract["foundation"]["contract"] == "PNCC_STATE_SNAPSHOT"
    assert contract["cli"]["powershell_minimum"] == "5.1"
    assert contract["cli"]["input_transport"] == "LOCAL_JSON_FILE"
    assert contract["cli"]["output_transport"] == "STDOUT_JSON"
    assert all(value is False for value in contract["authority"].values())

    assert SCRIPT.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "#requires -Version 5.1" in script
    assert "Set-StrictMode -Version 2.0" in script
    assert "src\\foundations\\windows-v7\\V7-StateSnapshot.ps1" in script
    assert "New-V7StateSnapshotContract" in script
    assert "ConvertFrom-Json" in script
    assert "ConvertTo-Json" in script
    assert "-Compress" in script

    forbidden = (
        "Set-Content",
        "Add-Content",
        "Out-File",
        "Remove-Item",
        "Move-Item",
        "Copy-Item",
        "Start-Process",
        "Stop-Process",
        "Restart-Service",
        "Stop-Service",
        "Start-Service",
        "Invoke-WebRequest",
        "Invoke-RestMethod",
        "New-NetRoute",
        "Remove-NetRoute",
        "Set-NetRoute",
        "-pw ",
    )
    for token in forbidden:
        assert token not in script


def test_wu161_preserves_exact_tunnel_safety_invariants():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = FOUNDATION.read_text(encoding="utf-8-sig")
    tunnels = contract["fixed_tunnel_invariants"]

    assert tunnels["primary_auto"] == {
        "host": "127.0.0.1",
        "port": 1081,
        "lifecycle": "AUTO",
        "automation_may_manage_lifecycle": True,
    }
    assert tunnels["reserve_manual"] == {
        "host": "127.0.0.1",
        "port": 1080,
        "lifecycle": "MANUAL_ONLY",
        "automation_may_manage_lifecycle": False,
    }
    assert "Port = 1081" in source
    assert "Port = 1080" in source
    assert "Lifecycle = 'MANUAL_ONLY'" in source
    assert "AutomationMayManageLifecycle = $false" in source


def test_wu161_cli_normalizes_module_collection_shapes_without_mutation():
    script = SCRIPT.read_text(encoding="utf-8-sig")
    assert "$moduleNames = @($moduleNamesRaw" in script
    assert "Where-Object { -not [string]::IsNullOrWhiteSpace($_) }" in script
    assert "ModuleNames" in script
    assert "Get-Content" in script
    assert "Resolve-Path" in script
