#Requires -Version 5.1
<#
================================================================================
  SmartKassa - do'kon serveriga BIR TUGMALI o'rnatuvchi
================================================================================
  Bu bitta fayl hamma ishni qiladi:
    1. Kerakli dasturlarni o'rnatadi  (Git, Python, Node.js, Caddy) - winget orqali
    2. Loyihani GitHub'dan yuklaydi   (C:\SmartKassa)
    3. Sozlaydi                       (kutubxonalar, frontend build, backend\.env)
    4. LAN rejimiga moslaydi          (APP_ENV=production, ALLOW_SELF_UPDATE=true)
    5. Ishga tushiradi + kompyuter yonganda avtomat ishlashini o'rnatadi

  ISHLATISH (do'kon serveri bo'ladigan kompyuterda):
    1. Bu faylni saqlang (masalan, Ish stoli).
    2. Ustiga o'ng tugma bosib "Run with PowerShell" ni tanlang.
       (yoki PowerShell'da:
        powershell -NoProfile -ExecutionPolicy Bypass -File "<shu fayl yo'li>")
    3. UAC oynasi chiqsa "Ha" - skript administrator huquqini so'raydi.

  QAYTA ISHLATISH xavfsiz: bor narsani buzmaydi, faqat yangilaydi.
================================================================================
#>

[CmdletBinding()]
param(
    [string]$InstallDir = "C:\SmartKassa",
    [string]$RepoUrl    = "https://github.com/mirazizGG/Kassa.git",
    [switch]$NoStart,
    [switch]$NoAutostart
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$SelfUrl = "https://raw.githubusercontent.com/mirazizGG/Kassa/main/deploy/install-smartkassa.ps1"

function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !   $m" -ForegroundColor Yellow }
function Fail($m) {
    Write-Host "`n  X   $m" -ForegroundColor Red
    Write-Host ""
    Read-Host "Yopish uchun Enter bosing"
    exit 1
}

# --- Administrator huquqi (kerak bo'lsa oynani qayta ochamiz) ---
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Warn "Administrator huquqi kerak - oyna qayta ochilmoqda..."
    $file = $PSCommandPath
    if (-not $file -or -not (Test-Path $file)) {
        $file = Join-Path $env:TEMP "install-smartkassa.ps1"
        try { Invoke-WebRequest -Uri $SelfUrl -OutFile $file -UseBasicParsing } catch { Fail "Skriptni yuklab bo'lmadi: $_" }
    }
    $argList = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$file`"",
        "-InstallDir", "`"$InstallDir`"", "-RepoUrl", "`"$RepoUrl`""
    )
    if ($NoStart)     { $argList += "-NoStart" }
    if ($NoAutostart) { $argList += "-NoAutostart" }
    try { Start-Process powershell.exe -Verb RunAs -ArgumentList $argList }
    catch { Fail "Administrator oynasi ochilmadi. PowerShell'ni o'zingiz 'Administrator sifatida' oching va qaytadan urinib ko'ring." }
    exit
}

Write-Host ""
Write-Host "  ============================================" -ForegroundColor White
Write-Host "   SmartKassa o'rnatuvchi" -ForegroundColor White
Write-Host "   Papka: $InstallDir" -ForegroundColor DarkGray
Write-Host "  ============================================" -ForegroundColor White

# --- winget bormi ---
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Fail "winget topilmadi. Microsoft Store'dan 'App Installer' ni o'rnating (yoki Windows'ni yangilang), keyin qaytadan."
}

function Sync-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ";"
}

function Ensure-Tool($cmd, $id, $label) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { Ok "$label - bor"; return }
    Step "$label o'rnatilmoqda ($id)..."
    winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
    Sync-Path
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { Ok "$label o'rnatildi" }
    else { Warn "$label o'rnatildi, lekin hozircha PATH'da ko'rinmayapti (kompyuterni qayta yoqish kerak bo'lishi mumkin)." }
}

Step "1/5 - Kerakli dasturlar"
Ensure-Tool "git"    "Git.Git"            "Git"
Ensure-Tool "python" "Python.Python.3.12" "Python"
Ensure-Tool "node"   "OpenJS.NodeJS.LTS"  "Node.js"
Ensure-Tool "caddy"  "CaddyServer.Caddy"  "Caddy"

$required = [ordered]@{ git = "Git"; python = "Python"; node = "Node.js" }
$missing = @()
foreach ($item in $required.GetEnumerator()) {
    if (-not (Get-Command $item.Key -ErrorAction SilentlyContinue)) { $missing += $item.Value }
}
if ($missing.Count -gt 0) {
    Fail ("Bu dasturlar hali tayyor emas: {0}.`n  Kompyuterni QAYTA YOQING va shu faylni qaytadan ishga tushiring." -f ($missing -join ", "))
}

# --- Loyiha ---
Step "2/5 - Loyihani GitHub'dan olish"
if (Test-Path (Join-Path $InstallDir ".git")) {
    Ok "Loyiha allaqachon bor - yangilanmoqda"
    Push-Location $InstallDir
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { Warn "git pull o'tmadi (serverda qo'lda o'zgarish bo'lishi mumkin) - davom etamiz." }
    Pop-Location
}
elseif (Test-Path $InstallDir) {
    Fail "$InstallDir papkasi bor, lekin git loyihasi emas. Uni o'chiring yoki boshqa joy tanlang:  -InstallDir C:\Boshqa\Yol"
}
else {
    git clone $RepoUrl $InstallDir
    if (-not (Test-Path (Join-Path $InstallDir ".git"))) { Fail "git clone ishlamadi. Internet aloqasini tekshiring." }
    Ok "Yuklab olindi"
}

$scripts = Join-Path $InstallDir "deploy\scripts"
$envFile = Join-Path $InstallDir "backend\.env"

function Invoke-Child($scriptName, $mustSucceed) {
    $path = Join-Path $scripts $scriptName
    if (-not (Test-Path $path)) { Fail "$scriptName topilmadi: $path" }
    $p = Start-Process powershell.exe -PassThru -Wait -NoNewWindow -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$path`""
    )
    if ($mustSucceed -and $p.ExitCode -ne 0) {
        Fail "$scriptName xato bilan tugadi (kod $($p.ExitCode)). Yuqoridagi xabarlarga qarang."
    }
    return $p.ExitCode
}

# --- Sozlash ---
Step "3/5 - Sozlash: kutubxonalar + frontend build (bir necha daqiqa vaqt oladi)"
Invoke-Child "first-time-setup.ps1" $true | Out-Null
if (-not (Test-Path $envFile)) { Fail "backend\.env yaratilmadi." }

# --- LAN rejimi uchun .env ---
Step "4/5 - LAN rejimi sozlamalari"
function Set-EnvLine($key, $value) {
    $esc = [regex]::Escape($key)
    $lines = @(Get-Content -LiteralPath $envFile)
    if ($lines | Where-Object { $_ -match "^\s*$esc\s*=" }) {
        $lines = $lines | ForEach-Object { if ($_ -match "^\s*$esc\s*=") { "$key=$value" } else { $_ } }
    }
    else { $lines += "$key=$value" }
    Set-Content -LiteralPath $envFile -Value $lines -Encoding utf8
}
Set-EnvLine "APP_ENV" "production"
Set-EnvLine "ALLOW_SELF_UPDATE" "true"
# ALLOWED_ORIGINS: LAN + Caddy = bitta origin, CORS kerak emas. Qatorni izohga olamiz.
$lines = @(Get-Content -LiteralPath $envFile) | ForEach-Object {
    if ($_ -match "^\s*ALLOWED_ORIGINS\s*=" ) { "# $_    # LAN rejimi: kerak emas (bo'sh = hamma origin)" } else { $_ }
}
Set-Content -LiteralPath $envFile -Value $lines -Encoding utf8
Ok "APP_ENV=production, ALLOW_SELF_UPDATE=true, ALLOWED_ORIGINS izohga olindi"

# --- Ishga tushirish ---
if ($NoStart) {
    Warn "Ishga tushirilmadi (-NoStart). Keyin qo'lda:  cd `"$scripts`" ; .\start-all.ps1"
}
else {
    Step "5/5 - Xizmatlarni ishga tushirish"
    Invoke-Child "start-all.ps1" $false | Out-Null

    if ($NoAutostart) {
        Warn "Avtomatik ishga tushirish o'rnatilmadi (-NoAutostart). Keyin:  .\install-autostart.ps1"
    }
    else {
        Step "Kompyuter yonganda avtomat ishlashini o'rnatish"
        Invoke-Child "install-autostart.ps1" $false | Out-Null
    }
}

# --- Xulosa ---
$ip = $null
try {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp, Manual -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "169.*" -and $_.IPAddress -ne "127.0.0.1" } |
        Select-Object -First 1).IPAddress
}
catch {}

Write-Host ""
Write-Host "  ======================================================" -ForegroundColor Green
Write-Host "   TAYYOR - SmartKassa ishga tushdi" -ForegroundColor Green
Write-Host "  ======================================================" -ForegroundColor Green
if ($ip) {
    Write-Host "   Do'kon ichidagi kompyuterlardan:  http://$($ip):8080" -ForegroundColor White
    Write-Host "   Shu kompyuterda:                  http://localhost:8080" -ForegroundColor White
}
else {
    Write-Host "   Manzil:  http://localhost:8080   (IP'ni  .\status.ps1  ko'rsatadi)" -ForegroundColor White
}
Write-Host ""
Write-Host "   Login:   admin  /  123     <---  DARHOL parolni o'zgartiring!" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Kundalik buyruqlar:   cd `"$scripts`"" -ForegroundColor DarkGray
Write-Host "     .\status.ps1     - holat" -ForegroundColor DarkGray
Write-Host "     .\start-all.ps1  - yoqish" -ForegroundColor DarkGray
Write-Host "     .\stop-all.ps1   - o'chirish" -ForegroundColor DarkGray
Write-Host "     .\update.ps1     - GitHub'dan qo'lda yangilash" -ForegroundColor DarkGray
Write-Host ""
Write-Host "   O'zgarish kiritish: uyda 'git push' -> do'konda ekrandagi 'Yangilash' tugmasi." -ForegroundColor DarkGray
Write-Host ""
Read-Host "Yopish uchun Enter bosing"
