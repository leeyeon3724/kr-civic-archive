$ErrorActionPreference = "Stop"

$gitDir = (git rev-parse --git-dir).Trim()
if (-not $gitDir) {
    throw "Failed to resolve .git directory."
}

$hooksDir = Join-Path $gitDir "hooks"
New-Item -ItemType Directory -Force -Path $hooksDir | Out-Null

$hookPath = Join-Path $hooksDir "commit-msg"
$hookScript = @"
#!/usr/bin/env bash
python scripts/check_commit_messages.py --message-file "\$1"
"@

Set-Content -Path $hookPath -Value $hookScript -Encoding UTF8NoBOM
Write-Output "Installed commit-msg hook: $hookPath"
