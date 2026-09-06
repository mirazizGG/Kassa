# SmartKassa - do'kon server kompyuterida ish stoli (Desktop) yorlig'ini yaratadi.
#
# Yorliqni ikki marta bosganda brauzer (Chrome/Edge) "app rejimida" - manzil
# satrisiz, alohida dastur oynasi kabi - http://localhost:8000 ni ochadi.
# Chrome/Edge topilmasa, oddiy internet yorlig'i (.url) yaratiladi.
#
# Windows 8.1 / 10 / 11 (PowerShell 4.0+) da ishlaydi. Qayta ishlatish xavfsiz.
#
# Ishlatish:
#   powershell -ExecutionPolicy Bypass -File create-desktop-shortcut.ps1
#   powershell -ExecutionPolicy Bypass -File create-desktop-shortcut.ps1 -Url "http://localhost:8000" -Name "SmartKassa"

param(
    [string]$Url  = "http://localhost:8000",
    [string]$Name = "SmartKassa"
)

$ErrorActionPreference = "Stop"

function Info($m) { Write-Host "  $m" -ForegroundColor Gray }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !   $m" -ForegroundColor Yellow }

# Loyiha ildizi (bu skript deploy\scripts\ ichida)
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$iconPath = Join-Path $repoRoot "frontend\build\icon.ico"

$desktop = [Environment]::GetFolderPath("Desktop")

function Find-Browser {
    $candidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
    return $null
}

$browser = Find-Browser
$shell = New-Object -ComObject WScript.Shell

if ($browser) {
    $lnk = Join-Path $desktop "$Name.lnk"
    if (Test-Path $lnk) { Remove-Item $lnk -Force -ErrorAction SilentlyContinue }
    $sc = $shell.CreateShortcut($lnk)
    $sc.TargetPath = $browser
    $sc.Arguments = "--app=$Url --new-window"
    $sc.WorkingDirectory = Split-Path $browser
    $sc.Description = "SmartKassa - kassa dasturi"
    if (Test-Path $iconPath) { $sc.IconLocation = $iconPath }
    $sc.Save()
    Ok "Ish stolida '$Name' yorlig'i yaratildi (brauzer: $(Split-Path $browser -Leaf))"
}
else {
    # Chrome/Edge yo'q - oddiy internet yorlig'i (standart brauzerda ochiladi)
    $urlFile = Join-Path $desktop "$Name.url"
    $content = @(
        "[InternetShortcut]",
        "URL=$Url",
        "IconIndex=0"
    )
    if (Test-Path $iconPath) { $content += "IconFile=$iconPath" }
    Set-Content -LiteralPath $urlFile -Value $content -Encoding ASCII
    Warn "Chrome/Edge topilmadi - oddiy internet yorlig'i yaratildi: '$Name.url'"
    Info "To'liq dastur oynasi uchun Chrome yoki Edge o'rnatib, bu skriptni qayta ishga tushiring."
}

Info "Manzil: $Url"
