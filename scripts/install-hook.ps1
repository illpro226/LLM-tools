# Install the optional guard hook: a PreToolUse/PostToolUse hook that nudges
# (and for a few raw git/grep/cat shapes, denies) Claude Code toward the
# suite's tools instead of built-ins, and logs a savings_record.md in this
# checkout. Entirely optional -- the tools work standalone without it.
#
# Usage: powershell -File scripts/install-hook.ps1

$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Src = Join-Path $RepoDir "hooks\llm-tools-guard.py"
$DestDir = Join-Path $HOME ".claude\hooks"
$Dest = Join-Path $DestDir "llm-tools-guard.py"
$Settings = Join-Path $HOME ".claude\settings.json"

if (-not (Test-Path $Src)) {
    Write-Error "install-hook: $Src not found"
    exit 1
}

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
if (Test-Path $Dest) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item $Dest "$Dest.bak-$stamp"
    Write-Host "install-hook: backed up existing $Dest"
}
Copy-Item $Src $Dest -Force
Write-Host "install-hook: copied hook to $Dest"

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Register the hook in $Settings (create if absent):"
$snippet = @"
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell|Read|Grep",
        "hooks": [
          { "type": "command",
            "command": "python \"$($Dest -replace '\\','/')\"",
            "timeout": 10 }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Read|Bash|PowerShell",
        "hooks": [
          { "type": "command",
            "command": "python \"$($Dest -replace '\\','/')\"",
            "timeout": 10 }
        ]
      }
    ]
  }
}
"@
Write-Host $snippet
Write-Host "   (merge with any existing `"hooks`" key rather than overwriting the file)"
Write-Host ""
Write-Host "2. Savings tracking (the per-tool $RepoDir\savings_record.md table)"
Write-Host "   auto-detects this checkout only if its path matches a hard-coded"
Write-Host "   entry in KNOWN_SAVINGS_ROOTS inside the hook. On a fresh clone it"
Write-Host "   usually won't, so set this instead (persist via System Properties"
Write-Host "   -> Environment Variables, or `$env:` for the current session):"
Write-Host ""
Write-Host "   `$env:LLM_TOOLS_SAVINGS_ROOT = `"$RepoDir`""
Write-Host ""
Write-Host "   Without it the hook still enforces tool preference; it just skips"
Write-Host "   savings logging rather than guessing a path (fail-open by design)."
