<#
Install department skills on Windows for agent tools that read SKILL.md folders.

Usage: .\install.ps1 <target> [department ...]
  target:      claude | copilot | gemini | codex | agents | all
  department:  hr finance supply-chain legal sales marketing it customer-service (default: all)

Examples:
  .\install.ps1 claude hr legal
  .\install.ps1 copilot
  $env:SKILLS_DIR = ".\.github\skills"; .\install.ps1 custom finance

If scripts are blocked, run once in this window: Set-ExecutionPolicy -Scope Process Bypass
#>
param(
  [Parameter(Mandatory = $true, Position = 0)][string]$Target,
  [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Departments
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-SkillDir([string]$t) {
  switch ($t) {
    "claude"  { return Join-Path $HOME ".claude\skills" }
    "copilot" { return Join-Path $HOME ".copilot\skills" }
    "gemini"  { return Join-Path $HOME ".gemini\skills" }
    "codex"   { return Join-Path $HOME ".agents\skills" }
    "agents"  { return Join-Path $HOME ".agents\skills" }
    "custom"  { if (-not $env:SKILLS_DIR) { throw "Set `$env:SKILLS_DIR for the custom target" }; return $env:SKILLS_DIR }
    default   { throw "Unknown target: $t (use claude, copilot, gemini, codex, agents, custom or all)" }
  }
}

if (-not $Departments -or $Departments.Count -eq 0) {
  $Departments = Get-ChildItem -Directory (Join-Path $Root "departments") | ForEach-Object { $_.Name }
}
foreach ($d in $Departments) {
  if (-not (Test-Path (Join-Path $Root "departments\$d\skills"))) { throw "Unknown department: $d" }
}

$targets = if ($Target -eq "all") { @("claude", "copilot", "gemini", "codex") } else { @($Target) }

foreach ($t in $targets) {
  $dest = Get-SkillDir $t
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  $count = 0
  foreach ($d in $Departments) {
    Get-ChildItem -Directory (Join-Path $Root "departments\$d\skills") | ForEach-Object {
      $out = Join-Path $dest $_.Name
      if (Test-Path $out) { Remove-Item -Recurse -Force $out }
      Copy-Item -Recurse $_.FullName $out
      $count++
    }
  }
  Write-Host "Installed $count skills into $dest"
}
Write-Host "Restart your agent (or start a new session) so it picks up the new skills."
