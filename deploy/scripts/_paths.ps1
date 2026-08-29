# Umumiy yo'llar va sozlamalar. Boshqa skriptlar buni "dot-source" qiladi.
# Ishlatilishi:  . "$PSScriptRoot\_paths.ps1"

$ErrorActionPreference = "Stop"

$ScriptsDir  = $PSScriptRoot
$DeployDir   = Split-Path $ScriptsDir -Parent
$RepoRoot    = Split-Path $DeployDir -Parent

$BackendDir  = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$DistDir     = Join-Path $FrontendDir "dist"
$RunDir      = Join-Path $DeployDir "run"

$CaddyfilePath = Join-Path $DeployDir "Caddyfile"

# Portlar
$BackendPort = 8000
$CaddyPort   = 8080

# PID fayllari
$BackendPid    = Join-Path $RunDir "backend.pid"
$CaddyPid      = Join-Path $RunDir "caddy.pid"
$CloudflaredPid = Join-Path $RunDir "cloudflared.pid"

if (-not (Test-Path $RunDir)) {
	New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
}

function Write-Step($msg)  { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "  !   $msg" -ForegroundColor Yellow }
function Write-Err2($msg)  { Write-Host "  X   $msg" -ForegroundColor Red }

function Test-Port($port) {
	try {
		$c = New-Object System.Net.Sockets.TcpClient
		$c.Connect("127.0.0.1", $port)
		$c.Close()
		return $true
	} catch {
		return $false
	}
}

function Get-PidFromFile($file) {
	if (-not (Test-Path $file)) { return $null }
	$id = (Get-Content $file -Raw).Trim()
	if (-not $id) { return $null }
	$proc = Get-Process -Id $id -ErrorAction SilentlyContinue
	if ($proc) { return [int]$id }
	return $null
}

function Stop-ByPidFile($file, $name) {
	$id = Get-PidFromFile $file
	if ($id) {
		try {
			Stop-Process -Id $id -Force -ErrorAction Stop
			Write-Ok "$name to'xtatildi (PID $id)"
		} catch {
			Write-Warn2 "$name to'xtatilmadi: $_"
		}
	} else {
		Write-Warn2 "$name ishlamayapti"
	}
	if (Test-Path $file) { Remove-Item $file -Force -ErrorAction SilentlyContinue }
}
