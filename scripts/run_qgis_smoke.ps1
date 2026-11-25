$ErrorActionPreference = 'Stop'
$bundleRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $bundleRoot
$profilesRoot = Join-Path $workspaceRoot '.qgis_test'
$argsList = @('--nologo','--profiles-path',('"' + $profilesRoot + '"'),'--profile','chude34','--project',('"' + (Join-Path $bundleRoot 'demo\ChuDe34_BacNinh.qgz') + '"'),'--code',('"' + (Join-Path $bundleRoot 'tests\qgis_smoke.py') + '"'))
$proc = Start-Process -FilePath 'C:\Program Files\QGIS 3.44.13\bin\qgis-ltr-bin.exe' -ArgumentList $argsList -WindowStyle Hidden -PassThru
if (-not $proc.WaitForExit(60000)) { throw ('QGIS test did not exit in 60 seconds. Process ID: ' + $proc.Id) }
$proc.Refresh()
$reportPath = Join-Path $bundleRoot 'kiem_thu\qgis_desktop.json'
$report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
$report | Add-Member -NotePropertyName 'process_exit_code' -NotePropertyValue $proc.ExitCode -Force
$report.passed = ($proc.ExitCode -eq 0 -and $report.phase -eq 'ui_checks_passed_waiting_for_clean_exit')
if ($report.passed) { $report.phase = 'completed_with_clean_exit' }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
if (-not $report.passed) { throw ('QGIS test failed; exit code ' + $proc.ExitCode) }
Write-Output 'QGIS_NATIVE_ZIP_AND_CLEAN_EXIT_OK'
