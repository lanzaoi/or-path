# OR-Path L2 installer (Windows)
# Usage:
#   irm https://github.com/lanzaoi/or-path/releases/download/v0.3.0/install.ps1 | iex
#   powershell -File install.ps1 -LocalZip .\dist\orpath-0.3.0-win-x64.zip
#   powershell -File install.ps1 -Version 0.3.0

param(
  [string]$Version = "latest",
  [string]$InstallDir = "",
  [string]$Repo = "lanzaoi/or-path",
  [string]$LocalZip = "",
  [switch]$SkipSetup,
  [switch]$NoPath
)

$ErrorActionPreference = "Stop"

function Get-DefaultInstallDir {
  if ($env:LOCALAPPDATA) {
    return (Join-Path $env:LOCALAPPDATA "Programs\orpath")
  }
  return (Join-Path $HOME "orpath")
}

function Resolve-LatestVersion {
  param([string]$Repository)
  $page = Invoke-WebRequest -Uri "https://github.com/$Repository/releases/latest" -UseBasicParsing
  $m = [regex]::Match($page.Content, 'releases/tag/v([0-9][^"''<>\s]*)')
  if (-not $m.Success) { throw "Failed to resolve latest release for $Repository" }
  return $m.Groups[1].Value
}

function Get-FileSha256 {
  param([string]$Path)
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if (-not $InstallDir) { $InstallDir = Get-DefaultInstallDir }

$resolvedVersion = $Version
if ($Version -eq "latest" -or $Version -eq "stable") {
  if ($LocalZip) {
    $resolvedVersion = "local"
  } else {
    $resolvedVersion = Resolve-LatestVersion -Repository $Repo
  }
} else {
  $resolvedVersion = $Version.TrimStart("v")
}

$assetName = "orpath-$resolvedVersion-win-x64.zip"
if ($LocalZip) {
  $assetName = [System.IO.Path]::GetFileName($LocalZip)
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("orpath-install-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
  $zipPath = Join-Path $tmp $assetName
  if ($LocalZip) {
    Write-Host "==> Using local zip $LocalZip"
    Copy-Item -LiteralPath $LocalZip -Destination $zipPath -Force
  } else {
    $base = "https://github.com/$Repo/releases/download/v$resolvedVersion"
    $url = "$base/$assetName"
    Write-Host "==> Downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing

    $sumsUrl = "$base/SHA256SUMS"
    $sumsPath = Join-Path $tmp "SHA256SUMS"
    try {
      Invoke-WebRequest -Uri $sumsUrl -OutFile $sumsPath -UseBasicParsing
      $esc = [regex]::Escape($assetName)
      $hit = Select-String -LiteralPath $sumsPath -Pattern "^([0-9a-fA-F]{64})\s+\*?$esc$" | Select-Object -First 1
      if (-not $hit) { throw "SHA256SUMS missing entry for $assetName" }
      $expect = $hit.Matches[0].Groups[1].Value.ToLowerInvariant()
      $actual = Get-FileSha256 -Path $zipPath
      if ($expect -ne $actual) { throw "SHA-256 mismatch: expected $expect got $actual" }
      Write-Host "==> Checksum OK"
    } catch {
      Write-Host "[WARN] checksum verify skipped/failed: $_"
    }
  }

  $extract = Join-Path $tmp "extract"
  New-Item -ItemType Directory -Path $extract | Out-Null
  Write-Host "==> Extracting (long-path aware)"
  $py = $null
  if (Get-Command python -ErrorAction SilentlyContinue) { $py = (Get-Command python).Source }
  elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
  # Prefer extracting with Python helper once placed beside zip... use embedded minimal extractor
  $extractOk = $false
  if ($py) {
    $helper = Join-Path $tmp "extract_zip_longpath.py"
    @'
import os, shutil, sys, zipfile
from pathlib import Path

def win_long(path: Path) -> str:
    s = os.path.abspath(str(path))
    if os.name != "nt":
        return s
    if s.startswith("\\\\?\\"):
        return s
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s[2:]
    return "\\\\?\\" + s

zp, dest = Path(sys.argv[1]), Path(sys.argv[2])
dest.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zp, "r") as zf:
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        target = dest / name
        if name.endswith("/"):
            os.makedirs(win_long(target), exist_ok=True)
            continue
        os.makedirs(win_long(target.parent), exist_ok=True)
        with zf.open(info) as src, open(win_long(target), "wb") as out:
            shutil.copyfileobj(src, out, length=1024 * 1024)
print("ok")
'@ | Set-Content -LiteralPath $helper -Encoding UTF8
    & $py $helper $zipPath $extract
    if ($LASTEXITCODE -eq 0) { $extractOk = $true }
  }
  if (-not $extractOk) {
    Write-Host "==> fallback Expand-Archive (may fail on long paths)"
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extract -Force
  }

  $bundle = Get-ChildItem -LiteralPath $extract -Directory | Select-Object -First 1
  if (-not $bundle) { throw "zip contained no top-level directory" }
  $bat = Join-Path $bundle.FullName "orpath.bat"
  if (-not (Test-Path -LiteralPath $bat)) { throw "orpath.bat missing in bundle" }

  Write-Host "==> Installing to $InstallDir"
  if (Test-Path -LiteralPath $InstallDir) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force
  }
  New-Item -ItemType Directory -Path (Split-Path -Parent $InstallDir) -Force | Out-Null
  Move-Item -LiteralPath $bundle.FullName -Destination $InstallDir

  if (-not $NoPath) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -and ($userPath.Split(";") -notcontains $InstallDir)) {
      [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(";") + ";" + $InstallDir), "User")
      Write-Host "==> Added to user PATH (new terminals): $InstallDir"
    }
  }

  if (-not $SkipSetup) {
    Write-Host "==> Running orpath setup"
    $setup = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "orpath.bat", "setup") -WorkingDirectory $InstallDir -Wait -PassThru -NoNewWindow
    if ($setup.ExitCode -ne 0) {
      Write-Host "[WARN] setup exit $($setup.ExitCode) — run manually: cd `"$InstallDir`" && orpath.bat setup"
    }
  }

  Write-Host ""
  Write-Host "PASS: OR-Path installed at $InstallDir"
  Write-Host "  cd `"$InstallDir`""
  Write-Host "  orpath.bat doctor"
  Write-Host "  START-WATCH.bat"
  Write-Host "  orpath.bat demo-m0 --slug m0"
  Write-Host "Edit .env for DEEPSEEK_API_KEY if you need LIVE multi-agent."
} finally {
  if (Test-Path -LiteralPath $tmp) {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
  }
}
