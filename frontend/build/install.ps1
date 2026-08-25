# SmartKassa o'rnatuvchisi (installer o'rnini bosuvchi skript).
#
# Electron .exe o'rniga ishlatiladi: hech narsa o'rnatmaydi, faqat
# kompyuterda allaqachon mavjud brauzerni (Chrome/Edge) app-mode'da
# ochadigan Desktop yorlig'ini yaratadi. Shuning uchun istalgan Windows
# versiyasida (7/8/8.1/10/11) ishlaydi.
#
# Ishlatish: bu faylni SmartKassa-ornatish.bat orqali ishga tushiring
# (ikki marta bosish kifoya), yoki to'g'ridan-to'g'ri:
#   powershell -ExecutionPolicy Bypass -File install.ps1 -ServerUrl "http://192.168.5.16:4173"

param(
    [string]$ServerUrl = "http://192.168.5.16:4173",
    [string]$ShortcutName = "SmartKassa"
)

$ErrorActionPreference = "Stop"

function Write-Step($text) {
    Write-Host ""
    Write-Host "== $text ==" -ForegroundColor Cyan
}

function Find-Browser {
    $candidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Test-ServerReachable([string]$url) {
    try {
        $uri = [Uri]$url
        $port = $uri.Port
        if ($port -lt 0) { $port = 80 }
        $client = New-Object System.Net.Sockets.TcpClient
        $result = $client.BeginConnect($uri.Host, $port, $null, $null)
        $ok = $result.AsyncWaitHandle.WaitOne(3000, $false)
        $client.Close()
        return $ok
    } catch {
        return $false
    }
}

Write-Host "SmartKassa sozlanmoqda..." -ForegroundColor Cyan

# 1. Brauzer mavjudligini tekshirish
Write-Step "1/3 Brauzer tekshirilmoqda"
$browserPath = Find-Browser
if (-not $browserPath) {
    Write-Host "Chrome yoki Edge topilmadi." -ForegroundColor Red
    Write-Host "Iltimos, birortasini qo'lda o'rnating (masalan, boshqa kompyuterdan" -ForegroundColor Yellow
    Write-Host "yuklab olingan Chrome/Edge o'rnatuvchisi orqali), so'ng bu skriptni" -ForegroundColor Yellow
    Write-Host "qayta ishga tushiring." -ForegroundColor Yellow
    exit 1
}
Write-Host "Topildi: $browserPath" -ForegroundColor Green

# 2. Serverga ulanishni tekshirish
Write-Step "2/3 Server bilan bog'lanish tekshirilmoqda ($ServerUrl)"
if (Test-ServerReachable $ServerUrl) {
    Write-Host "Server bilan bog'lanish OK." -ForegroundColor Green
} else {
    Write-Host "OGOHLANTIRISH: Serverga hozircha ulanib bo'lmadi." -ForegroundColor Yellow
    Write-Host "Tekshiring: server kompyuter yoqilganmi, frontend/backend ishlab" -ForegroundColor Yellow
    Write-Host "turibdimi, va bu kompyuter bilan bir tarmoqdami. Yorliq baribir" -ForegroundColor Yellow
    Write-Host "yaratiladi -- server ishga tushgach yorliq o'zi ishlay boshlaydi." -ForegroundColor Yellow
}

# 3. Desktop yorlig'ini yaratish
Write-Step "3/3 Desktop yorlig'i yaratilmoqda"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "$ShortcutName.lnk"
$iconPath = "$PSScriptRoot\icon.ico"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $browserPath
$shortcut.Arguments = "--app=$ServerUrl"
$shortcut.WorkingDirectory = Split-Path $browserPath
$shortcut.Description = "SmartKassa"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
}
$shortcut.Save()

Write-Host ""
Write-Host "Tayyor! Desktop'da '$ShortcutName' yorlig'i yaratildi." -ForegroundColor Green
Write-Host "Manzil: $ServerUrl"
