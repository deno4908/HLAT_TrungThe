$ErrorActionPreference = 'Stop'
$bundleRoot = $PSScriptRoot
$qgisInstall = Get-ChildItem -LiteralPath 'C:\Program Files' -Directory | Where-Object { $_.Name -like 'QGIS 3.*' } | Sort-Object { [version]($_.Name -replace '^QGIS ', '') } -Descending | Select-Object -First 1
if (-not $qgisInstall) { throw 'Khong tim thay QGIS 3.x trong Program Files. Hay cai ZIP plugin bang QGIS.' }
$qgisExe = Join-Path $qgisInstall.FullName 'bin\qgis-ltr-bin.exe'
if (-not (Test-Path -LiteralPath $qgisExe)) { $qgisExe = Join-Path $qgisInstall.FullName 'bin\qgis-bin.exe' }
if (-not (Test-Path -LiteralPath $qgisExe)) { throw 'Khong tim thay tep chay QGIS.' }
$profilesRoot = Join-Path $env:LOCALAPPDATA 'HLAT34'
$profileRoot = Join-Path $profilesRoot 'profiles\chude34'
$pluginRoot = Join-Path $profileRoot 'python\plugins'
$settingsRoot = Join-Path $profileRoot 'QGIS'
New-Item -ItemType Directory -Path $pluginRoot, $settingsRoot -Force | Out-Null
Expand-Archive -LiteralPath (Join-Path $bundleRoot 'hlat_trungthe_34.zip') -DestinationPath $pluginRoot -Force
$settingsFile = Join-Path $settingsRoot 'QGIS3.ini'
if (-not (Test-Path -LiteralPath $settingsFile)) {
    Set-Content -LiteralPath $settingsFile -Encoding UTF8 -Value "[PythonPlugins]`nhlat_trungthe_34=true`nprocessing=true`n[Qgis]`ncheckVersion=false`n"
}
$projectFile = Join-Path $bundleRoot 'demo\ChuDe34_BacNinh.qgz'
$launchArgs = @('--profiles-path', ('"' + $profilesRoot + '"'), '--profile', 'chude34', '--project', ('"' + $projectFile + '"'))
Start-Process -FilePath $qgisExe -ArgumentList $launchArgs
