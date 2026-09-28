#Requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InputPath,
    [Parameter(Mandatory)][ValidateSet('original','personal','company')][string]$Mode
)
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath 'E:\PCConfig\registries\host_python.json' -Raw -Encoding utf8 | ConvertFrom-Json
$python = [string]$config.executable
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'registered_host_python_missing' }
$exporter = Join-Path $PSScriptRoot 'export_pdf.py'
& $python -B -X utf8 $exporter --input $InputPath --mode $Mode
exit $LASTEXITCODE
