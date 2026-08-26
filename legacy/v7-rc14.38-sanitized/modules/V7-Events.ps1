#requires -Version 5.1
# VPS Control Center RC14 unified event envelope. Reader remains backward-compatible with RC11/RC12/RC13 JSONL records.

function Normalize-V7EventSeverity([string]$Severity) {
    switch(($Severity+'').ToUpperInvariant()) {
        'ERROR' { return 'ERROR' }
        'WARN' { return 'WARN' }
        'WARNING' { return 'WARN' }
        'DEBUG' { return 'DEBUG' }
        default { return 'INFO' }
    }
}

function Write-V7EventRecord {
    param([Parameter(Mandatory=$true)][string]$Path,[string]$Type='SYSTEM',[string]$Source='V7',[string]$Severity='INFO',[string]$Module='',[Parameter(Mandatory=$true)][string]$Summary,[string]$Detail='')
    try{
        $dir=Split-Path -Parent $Path;if(-not(Test-Path -LiteralPath $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
        $obj=[ordered]@{SchemaVersion=2;EventId=([guid]::NewGuid().ToString('N'));Timestamp=(Get-Date).ToString('o');Type=$Type;Source=$Source;Severity=(Normalize-V7EventSeverity $Severity);Module=$Module;Summary=$Summary;Detail=$Detail}
        $line=([pscustomobject]$obj|ConvertTo-Json -Compress -Depth 5)
        $utf8=New-Object Text.UTF8Encoding($false)
        $sw=New-Object IO.StreamWriter($Path,$true,$utf8)
        try{$sw.WriteLine($line)}finally{$sw.Dispose()}
    }catch{}
}

function ConvertTo-V7EventEnvelope($Record) {
    if(-not $Record){return $null}
    $schema=1;try{if($Record.SchemaVersion){$schema=[int]$Record.SchemaVersion}}catch{}
    $eventId='';try{$eventId=[string]$Record.EventId}catch{}
    return [pscustomobject]@{
        SchemaVersion=$schema;EventId=$eventId;Timestamp=[string]$Record.Timestamp;Type=[string]$Record.Type;Source=[string]$Record.Source;
        Severity=(Normalize-V7EventSeverity ([string]$Record.Severity));Module=[string]$Record.Module;Summary=[string]$Record.Summary;Detail=[string]$Record.Detail
    }
}

function Read-V7EventRecords {
    param([Parameter(Mandatory=$true)][string]$Path,[int]$Tail=500)
    $list=New-Object Collections.ArrayList
    if(-not(Test-Path -LiteralPath $Path)){return $list}
    try{
        foreach($line in Get-Content -LiteralPath $Path -Encoding UTF8 -Tail $Tail){
            if(-not $line){continue}
            try{$raw=$line|ConvertFrom-Json;$normalized=ConvertTo-V7EventEnvelope $raw;if($normalized){[void]$list.Add($normalized)}}catch{}
        }
    }catch{}
    return $list
}
