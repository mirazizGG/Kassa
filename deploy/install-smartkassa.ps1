<#
================================================================================
  SmartKassa - do'kon serveriga BIR FAYLLI o'rnatuvchi  (Windows 8.1 / 10 / 11)
================================================================================
  winget, Node.js, Caddy KERAK EMAS. Faqat Python + Git o'rnatiladi
  (ular internetdan to'g'ridan-to'g'ri yuklab olinadi).

  Bu fayl:
    1. Python va Git ni o'rnatadi (yo'q bo'lsa)
    2. Loyiha kodini tayyorlaydi:
         - agar shu skript loyiha ichidan (klon qilingan papkadan) ishga
           tushirilsa -> o'sha papkani ishlatadi, git pull qiladi
         - aks holda GitHub'dan C:\SmartKassa ga klon qiladi
    3. Kutubxonalarni o'rnatadi, backend\.env yaratadi (tasodifiy SECRET_KEY)
    4. LAN rejimiga moslaydi (APP_ENV=production, ALLOW_SELF_UPDATE=true)
    5. Ishga tushiradi + kompyuter yonganda avtomat ishlashini o'rnatadi

  Frontend serverda BUILD QILINMAYDI - u repodagi tayyor `frontend/dist` dan
  olinadi va backend'ning o'zi beradi (bitta port: 8000).

  ISHLATISH (do'kon serveri kompyuterida) - ikki yo'l, ikkalasi ham bir xil:

    A) Loyihani GitHub'dan yuklab oling (ZIP yoki `git clone`), keyin:
         PowerShell'da  ->  .\deploy\install-smartkassa.ps1
       (loyiha o'sha joyda sozlanadi)

    B) Hech narsa yuklamasdan, bitta buyruq bilan (C:\SmartKassa ga o'rnatadi):
         irm https://raw.githubusercontent.com/mirazizGG/Kassa/main/deploy/install-smartkassa.ps1 | iex

  Oddiy PowerShell oynasi yetarli - skript o'zi Administrator so'raydi.
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
$ProgressPreference = "SilentlyContinue"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
# Windows 8.1 uchun: TLS 1.2 ni majburan yoqamiz (aks holda github/python.org ochilmaydi)
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$SelfUrl = "https://raw.githubusercontent.com/mirazizGG/Kassa/main/deploy/install-smartkassa.ps1"
$PyWin10 = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
$PyWin81 = "https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe"

# Agar shu skript loyiha ichidan ishga tushirilgan bo'lsa (deploy\ papkasi
# haqiqiy klon ichida) - o'sha joyni ishlatamiz, C:\SmartKassa ga klon qilmaymiz.
if (-not $PSBoundParameters.ContainsKey('InstallDir') -and $PSScriptRoot) {
    $repoRoot = Split-Path $PSScriptRoot -Parent
    if ((Test-Path (Join-Path $repoRoot ".git")) -and (Test-Path (Join-Path $repoRoot "backend\main.py"))) {
        $InstallDir = $repoRoot
    }
}

function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !   $m" -ForegroundColor Yellow }
function Fail($m) {
    Write-Host "`n  X   $m" -ForegroundColor Red
    Write-Host ""
    Read-Host "Yopish uchun Enter bosing"
    exit 1
}

# --- Administrator ---
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Warn "Administrator huquqi kerak - oyna qayta ochilmoqda..."
    $file = $PSCommandPath
    if (-not $file -or -not (Test-Path $file)) {
        $file = Join-Path $env:TEMP "install-smartkassa.ps1"
        try { Invoke-WebRequest -Uri $SelfUrl -OutFile $file -UseBasicParsing } catch { Fail "Skriptni yuklab bo'lmadi: $_" }
    }
    $a = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$file`"", "-InstallDir", "`"$InstallDir`"", "-RepoUrl", "`"$RepoUrl`"")
    if ($NoStart)     { $a += "-NoStart" }
    if ($NoAutostart) { $a += "-NoAutostart" }
    try { Start-Process powershell.exe -Verb RunAs -ArgumentList $a }
    catch { Fail "Administrator oynasi ochilmadi. PowerShell'ni 'Administrator sifatida' oching va qaytadan." }
    exit
}

$osVer = [Version](Get-CimInstance Win32_OperatingSystem).Version
$isWin10Plus = $osVer.Major -ge 10
Write-Host ""
Write-Host "  ============================================" -ForegroundColor White
Write-Host "   SmartKassa o'rnatuvchi" -ForegroundColor White
Write-Host "   Windows $($osVer)  |  Papka: $InstallDir" -ForegroundColor DarkGray
Write-Host "  ============================================" -ForegroundColor White

function Sync-Path {
    $m = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $u = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($m, $u) | Where-Object { $_ }) -join ";"
}

function Download($url, $outFile) {
    Write-Host "      yuklanmoqda: $url" -ForegroundColor DarkGray
    Invoke-WebRequest -Uri $url -OutFile $outFile -UseBasicParsing
}

# ---------- Python ----------
Step "1/5 - Python"
$pyOk = $false
if (Get-Command python -ErrorAction SilentlyContinue) {
    try { $pyOk = [bool](python --version 2>$null) } catch { $pyOk = $false }
}
if ($pyOk) {
    Ok "Python bor: $(python --version)"
}
else {
    $url = if ($isWin10Plus) { $PyWin10 } else { $PyWin81 }
    $exe = Join-Path $env:TEMP "python-setup.exe"
    Step "Python o'rnatilmoqda ($([IO.Path]::GetFileName($url)))..."
    Download $url $exe
    Start-Process $exe -Wait -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_launcher=1"
    Remove-Item $exe -ErrorAction SilentlyContinue
    Sync-Path
    if (Get-Command python -ErrorAction SilentlyContinue) { Ok "Python o'rnatildi: $(python --version)" }
    else { Warn "Python o'rnatildi, lekin PATH'da ko'rinmayapti - pastda aytilgani bo'yicha kompyuterni qayta yoqing." }
}

# ---------- Git ----------
Step "2/5 - Git"
if (Get-Command git -ErrorAction SilentlyContinue) {
    Ok "Git bor: $(git --version)"
}
else {
    Step "Git yuklanmoqda (GitHub'dan eng oxirgi versiya)..."
    try {
        $rel = Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest" -UseBasicParsing
        $asset = $rel.assets | Where-Object { $_.name -match "64-bit\.exe$" -and $_.name -notmatch "rc" } | Select-Object -First 1
        if (-not $asset) { throw "64-bit .exe topilmadi" }
        $exe = Join-Path $env:TEMP "git-setup.exe"
        Download $asset.browser_download_url $exe
        Start-Process $exe -Wait -ArgumentList "/VERYSILENT /NORESTART /SP- /NOCANCEL"
        Remove-Item $exe -ErrorAction SilentlyContinue
        Sync-Path
    }
    catch { Fail "Git o'rnatib bo'lmadi: $_`n  Qo'lda o'rnating: https://git-scm.com/download/win" }
    if (Get-Command git -ErrorAction SilentlyContinue) { Ok "Git o'rnatildi: $(git --version)" }
    else { Warn "Git o'rnatildi, lekin PATH'da ko'rinmayapti - kompyuterni qayta yoqing." }
}

# PATH'da hali yo'q bo'lsa - to'xtaymiz (qayta yoqish kerak)
$stillMissing = @()
foreach ($c in "python", "git") { if (-not (Get-Command $c -ErrorAction SilentlyContinue)) { $stillMissing += $c } }
if ($stillMissing.Count -gt 0) {
    Fail ("{0} hali tayyor emas. Kompyuterni QAYTA YOQING va shu faylni qaytadan ishga tushiring." -f ($stillMissing -join ", "))
}

# ---------- Loyiha ----------
Step "3/5 - Loyihani GitHub'dan olish"
if (Test-Path (Join-Path $InstallDir ".git")) {
    Ok "Loyiha bor - yangilanmoqda"
    Push-Location $InstallDir
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { Warn "git pull o'tmadi - davom etamiz." }
    Pop-Location
}
elseif (Test-Path $InstallDir) {
    Fail "$InstallDir bor, lekin git loyihasi emas. O'chiring yoki boshqa joy tanlang:  -InstallDir C:\Boshqa"
}
else {
    git clone $RepoUrl $InstallDir
    if (-not (Test-Path (Join-Path $InstallDir ".git"))) { Fail "git clone ishlamadi. Internetni tekshiring." }
    Ok "Yuklab olindi"
}

$scripts = Join-Path $InstallDir "deploy\scripts"
$envFile = Join-Path $InstallDir "backend\.env"

function Invoke-Child($name, $mustSucceed) {
    $path = Join-Path $scripts $name
    if (-not (Test-Path $path)) { Fail "$name topilmadi." }
    $p = Start-Process powershell.exe -PassThru -Wait -NoNewWindow -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$path`""
    )
    if ($mustSucceed -and $p.ExitCode -ne 0) { Fail "$name xato bilan tugadi (kod $($p.ExitCode))." }
}

# ---------- Sozlash ----------
Step "4/5 - Sozlash (pip install; frontend repodagi dist'dan)"
Invoke-Child "first-time-setup.ps1" $true
if (-not (Test-Path $envFile)) { Fail "backend\.env yaratilmadi." }

# LAN rejimi
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
$lines = @(Get-Content -LiteralPath $envFile) | ForEach-Object {
    if ($_ -match "^\s*ALLOWED_ORIGINS\s*=" ) { "# $_    # LAN: kerak emas (bir origin)" } else { $_ }
}
Set-Content -LiteralPath $envFile -Value $lines -Encoding utf8
Ok "APP_ENV=production, ALLOW_SELF_UPDATE=true"

# ---------- Ishga tushirish ----------
if ($NoStart) {
    Warn "Ishga tushirilmadi (-NoStart). Keyin:  cd `"$scripts`" ; .\start-all.ps1"
}
else {
    Step "5/5 - Ishga tushirish"
    Invoke-Child "start-all.ps1" $false
    if (-not $NoAutostart) {
        Step "Kompyuter yonganda avtomat ishlashini o'rnatish"
        Invoke-Child "install-autostart.ps1" $false
    }
}

# ---------- Xulosa ----------
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
    Write-Host "   Kassir kompyuterlardan:  http://$($ip):8000" -ForegroundColor White
    Write-Host "   Shu kompyuterda:         http://localhost:8000" -ForegroundColor White
}
else {
    Write-Host "   Manzil:  http://localhost:8000   (IP'ni  .\status.ps1  ko'rsatadi)" -ForegroundColor White
}
Write-Host ""
Write-Host "   Login:  miraziz  /  8038434     <---  DARHOL parolni o'zgartiring!" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Kundalik:  cd `"$scripts`"" -ForegroundColor DarkGray
Write-Host "     .\status.ps1   .\start-all.ps1   .\stop-all.ps1   .\update.ps1" -ForegroundColor DarkGray
Write-Host ""
Write-Host "   Yangilash: uyda  deploy\publish.ps1  ->  do'konda ekrandagi 'Yangilash' tugmasi." -ForegroundColor DarkGray
Write-Host ""
Read-Host "Yopish uchun Enter bosing"
