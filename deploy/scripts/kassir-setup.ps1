# SmartKassa - KASSIR kompyuteriga sozlash.
#
# Kassir kompyuteriga HECH NARSA o'rnatilmaydi (Python/Git kerak emas).
# Bu skript faqat ish stoliga "SmartKassa" yorlig'ini yaratadi - u brauzerni
# (Chrome/Edge) "app rejimida" ochib, do'kon serveriga ulanadi.
#
# Windows 7 / 8 / 8.1 / 10 / 11 da ishlaydi.
#
# Ishlatish:
#   powershell -ExecutionPolicy Bypass -File kassir-setup.ps1
#   powershell -ExecutionPolicy Bypass -File kassir-setup.ps1 -ServerIp 192.168.100.17

param(
    [string]$ServerIp = "",
    [int]$Port = 8000,
    [string]$Name = "SmartKassa"
)

$ErrorActionPreference = "Stop"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

function Info($m) { Write-Host "  $m" -ForegroundColor Gray }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !   $m" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  ======================================================" -ForegroundColor White
Write-Host "   SmartKassa - kassir kompyuteriga yorliq" -ForegroundColor White
Write-Host "  ======================================================" -ForegroundColor White
Write-Host ""

# --- Server IP ---
if (-not $ServerIp) {
    Write-Host "  Do'kon SERVER kompyuterining IP manzilini kiriting." -ForegroundColor Cyan
    Write-Host "  (Serverda  status.ps1  buni ko'rsatadi, masalan: 192.168.100.17)" -ForegroundColor DarkGray
    $ServerIp = (Read-Host "  Server IP").Trim()
}
if (-not $ServerIp) { Write-Host "  IP kiritilmadi. Bekor qilindi." -ForegroundColor Red; exit 1 }

$url = "http://${ServerIp}:${Port}"
Info "Manzil: $url"

# --- Serverga ulanishni tekshirish (majburiy emas) ---
try {
    $client = New-Object System.Net.Sockets.TcpClient
    $async = $client.BeginConnect($ServerIp, $Port, $null, $null)
    if ($async.AsyncWaitHandle.WaitOne(3000, $false) -and $client.Connected) {
        Ok "Server bilan bog'lanish bor"
    } else {
        Warn "Serverga hozir ulanib bo'lmadi - yorliq baribir yaratiladi"
        Warn "(server yoqilgach ishlaydi; bir tarmoqda ekaningizni tekshiring)"
    }
    $client.Close()
} catch {
    Warn "Serverga hozir ulanib bo'lmadi - yorliq baribir yaratiladi"
}

# --- Brauzerni topish ---
$browser = $null
foreach ($p in @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)) { if (Test-Path $p) { $browser = $p; break } }

# --- Ikonka (majburiy emas) ---
$iconPath = $null
try {
    $appDir = Join-Path $env:LOCALAPPDATA "SmartKassa"
    New-Item -ItemType Directory -Path $appDir -Force | Out-Null
    $iconPath = Join-Path $appDir "icon.ico"
    if (-not (Test-Path $iconPath)) {
        Invoke-WebRequest "https://raw.githubusercontent.com/mirazizGG/Kassa/main/frontend/build/icon.ico" `
            -OutFile $iconPath -UseBasicParsing
    }
} catch { $iconPath = $null }

# --- Yorliq ---
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell

if ($browser) {
    $lnk = Join-Path $desktop "$Name.lnk"
    if (Test-Path $lnk) { Remove-Item $lnk -Force -ErrorAction SilentlyContinue }
    $sc = $shell.CreateShortcut($lnk)
    $sc.TargetPath = $browser
    $sc.Arguments = "--app=$url --new-window"
    $sc.WorkingDirectory = Split-Path $browser
    $sc.Description = "SmartKassa - kassa dasturi"
    if ($iconPath -and (Test-Path $iconPath)) { $sc.IconLocation = $iconPath }
    $sc.Save()
    Ok "Ish stolida '$Name' yorlig'i yaratildi (brauzer: $(Split-Path $browser -Leaf))"
} else {
    $urlFile = Join-Path $desktop "$Name.url"
    $lines = @("[InternetShortcut]", "URL=$url", "IconIndex=0")
    if ($iconPath -and (Test-Path $iconPath)) { $lines += "IconFile=$iconPath" }
    Set-Content -LiteralPath $urlFile -Value $lines -Encoding ASCII
    Warn "Chrome/Edge topilmadi - oddiy internet yorlig'i yaratildi"
    Info "To'liq dastur oynasi uchun Chrome yoki Edge o'rnating va bu skriptni qaytadan ishlating."
}

Write-Host ""
Ok "Tayyor. Ish stolidagi '$Name' yorlig'ini ikki marta bosib kiring."
Write-Host ""
