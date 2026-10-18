# Neural Nexus: run unit tests + optional end-to-end Oracle/OCI smoke tests.
# Usage (from backend-tests): powershell -ExecutionPolicy Bypass -File .\scripts\run_archive_qa.ps1
param(
    [string]$BaseUrl = "http://127.0.0.1:8002",
    [switch]$SkipLive
)
$ErrorActionPreference = "Stop"
$here = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $here
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportDir = Join-Path $here "test-reports\$stamp"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$items = New-Object System.Collections.Generic.List[object]
function Add-Check([string]$Name,[bool]$Ok,[string]$Detail) {
    $items.Add([pscustomobject]@{ Test=$Name; Result=$(if($Ok){"PASS"}else{"FAIL"}); Detail=$Detail })
    Write-Host "$(if($Ok){'[PASS]'}else{'[FAIL]'}) $Name - $Detail"
}
function Api([string]$Path,$Body=$null) {
    $args = @{ Uri = "$BaseUrl/archive$Path"; TimeoutSec=40 }
    if ($null -ne $Body) {
        $args.Method="Post"
        $args.ContentType="application/json"
        $args.Body=($Body | ConvertTo-Json -Compress -Depth 8)
    }
    return Invoke-RestMethod @args
}
Write-Host "=== The Last Archive automated QA ==="
$unitFile=Join-Path $reportDir "unit-tests.txt"
& python -m pytest tests/test_archive_scenarios.py -v *> $unitFile
$code=$LASTEXITCODE
Add-Check "Python unit tests" ($code -eq 0) "exit=$code; log: $unitFile"
if (-not $SkipLive) {
    try {
        $health=Api "/health"
        Add-Check "Oracle health" ($health.ok -eq $true -and $health.store -eq "oracle") ("ok="+$health.ok)
        if (-not $health.ok) { throw "Health endpoint reports Oracle unavailable" }
        foreach($scenario in @("boston_tea_party_1773","storming_bastille_1789")) {
            $visit=Api "/start" @{ nickname="Automated QA"; scenario_id=$scenario }
            $sid=$visit.session_id
            if (-not $sid) { throw "No session_id returned for $scenario" }
            Add-Check "$scenario - start" $true $sid
            $input=if($scenario -like "boston*") {"Why is Parliament taxing the colonies without representation?"} else {"Why are people running toward the Bastille for gunpowder?"}
            $action=Api "/action" @{ session_id=$sid; text=$input }
            Add-Check "$scenario - NPC reply" ([bool]$action.reply) ("score="+$action.total_score)
            $state=Api ("/state/"+$sid)
            Add-Check "$scenario - score persisted" ($state.score -eq $action.total_score) ("score="+$state.score)
            $null=Api "/extract" @{session_id=$sid}
            $court=Api "/court" @{session_id=$sid; testimony="I investigated the historical dispute and its causes."}
            Add-Check "$scenario - Archivist question" ([bool]$court.archivist_question) $court.source
            $verdict=Api "/verdict" @{session_id=$sid; response="The events reflected political tensions, disputes about government authority, and public protests."}
            Add-Check "$scenario - verdict /100" ($verdict.score -ge 0 -and $verdict.score -le 100 -and [bool]$verdict.decision) ("score="+$verdict.score+" decision="+$verdict.decision)
            $saved=Api ("/saves/"+$sid)
            Add-Check "$scenario - Saved Visits" ($saved.session_id -eq $sid -and [bool]$saved.verdict) ("history entries="+@($saved.transcript).Count)
        }
    } catch {
        Add-Check "Live API suite" $false $_.Exception.Message
    }
}
$passed=@($items | Where-Object Result -eq "PASS").Count
$failed=@($items | Where-Object Result -eq "FAIL").Count
$summary=@(
    "# The Last Archive - QA report",
    "",
    "Generated: $(Get-Date -Format o)",
    "Total: $($items.Count) | Passed: $passed | Failed: $failed",
    "",
    "| Test | Result | Detail |",
    "|---|---|---|"
)
foreach($item in $items) {
    $detail=($item.Detail -replace "\|","/" -replace "\r?\n"," ")
    $summary+="| $($item.Test) | $($item.Result) | $detail |"
}
$summary+=""
$summary+="Unit test output: unit-tests.txt"
$summary | Set-Content -Path (Join-Path $reportDir "QA_REPORT.md") -Encoding UTF8
$items | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $reportDir "QA_REPORT.json") -Encoding UTF8
Write-Host "Report: $reportDir\QA_REPORT.md"
if ($failed -gt 0) { exit 1 }
exit 0
