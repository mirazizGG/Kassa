# Kassa bot - do'kon kompyuteriga o'rnatish
#
# Ishlatish: papkadagi "ORNATISH.bat" ni ikki marta bosing
# (yoki: powershell -ExecutionPolicy Bypass -File install.ps1)
#
# Nima qiladi:
#   1. PHP bo'lmasa - yuklab oladi (runtime\php) va sozlaydi
#   2. .env ni tekshiradi: server API va Telegram bilan aloqa (bin\bot-check.php)
#   3. "Kassa bot" vazifasini yaratadi - kompyuter yoqilganda o'zi ishga tushadi
#   4. Botni hozir ishga tushiradi
#
# Fayl ataylab faqat ASCII: Windows PowerShell 5.1 BOM'siz UTF-8 ni buzadi.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Paket ildizi: app\ va bin\ turgan papka (paketda - shu papka, repoda - bitta yuqori)
$Root = $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "app\bootstrap.php"))) {
    $Root = Split-Path $PSScriptRoot -Parent
}
if (-not (Test-Path (Join-Path $Root "bin\bot.php"))) {
    Write-Host "XATO: bin\bot.php topilmadi. Skriptni kassa-bot papkasi ichidan ishga tushiring." -ForegroundColor Red
    exit 1
}
$Php = Join-Path $Root "runtime\php\php.exe"
$TaskName = "Kassa bot"

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    $text" -ForegroundColor Green }
function Fail($text) { Write-Host "    XATO: $text" -ForegroundColor Red; Read-Host "Chiqish uchun Enter"; exit 1 }

$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Host "Kassa bot - o'rnatish" -ForegroundColor Yellow
Write-Host "Papka: $Root"

# ---------------------------------------------------------------------------
Step "1/4 PHP"
# ---------------------------------------------------------------------------
if (-not (Test-Path $Php)) {
    Write-Host "    PHP yuklab olinmoqda (windows.php.net)..."
    $list = (Invoke-WebRequest -UseBasicParsing "https://windows.php.net/downloads/releases/").Content
    $zipName = [regex]::Matches($list, "php-8\.4\.\d+-nts-Win32-vs17-x64\.zip") |
        ForEach-Object { $_.Value } | Sort-Object -Unique |
        Sort-Object { [version]($_ -replace "^php-([\d.]+)-.*$", '$1') } | Select-Object -Last 1
    if (-not $zipName) { Fail "PHP arxivi topilmadi. Internetni tekshiring." }
    $zip = Join-Path $env:TEMP $zipName
    Invoke-WebRequest -UseBasicParsing "https://windows.php.net/downloads/releases/$zipName" -OutFile $zip
    $dest = Join-Path $Root "runtime\php"
    New-Item -ItemType Directory -Force $dest | Out-Null
    Expand-Archive -Path $zip -DestinationPath $dest -Force
    Remove-Item $zip -Force
    Ok "$zipName o'rnatildi"
}

$ini = Join-Path $Root "runtime\php\php.ini"
if (-not (Test-Path $ini)) {
    $text = Get-Content (Join-Path $Root "runtime\php\php.ini-production") -Raw
    $text = $text -replace ';extension_dir = "ext"', 'extension_dir = "ext"'
    foreach ($ext in "curl", "openssl", "mbstring", "pdo_mysql", "pdo_sqlite", "sqlite3", "zip", "fileinfo") {
        $text = $text -replace ";extension=$ext\b", "extension=$ext"
    }
    Set-Content -Path $ini -Value $text -Encoding ascii
    Ok "php.ini sozlandi"
}

# PHP Visual C++ 2015-2022 kutubxonasiga muhtoj - yo'q bo'lsa o'rnatamiz
& $Php -v *> $null
if ($LASTEXITCODE -ne 0) {
    if (-not $IsAdmin) { Fail "Visual C++ Redistributable kerak. ORNATISH.bat ni 'Administrator sifatida' ishga tushiring." }
    Write-Host "    Visual C++ Redistributable o'rnatilmoqda..."
    $vc = Join-Path $env:TEMP "vc_redist.x64.exe"
    Invoke-WebRequest -UseBasicParsing "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $vc
    Start-Process $vc -ArgumentList "/install", "/quiet", "/norestart" -Wait
    & $Php -v *> $null
    if ($LASTEXITCODE -ne 0) { Fail "PHP ishga tushmadi." }
}
Ok ((& $Php -r "echo 'PHP ', PHP_VERSION;"))

# ---------------------------------------------------------------------------
Step "2/4 Sozlamalar (.env) va aloqa"
# ---------------------------------------------------------------------------
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) { Fail ".env fayli yo'q ($envFile)" }
$envText = Get-Content $envFile -Raw
if (($envText -notmatch "(?m)^KASSA_API_URL=\S") -and ($envText -match "DATABASE_URL=mysql://FOYDALANUVCHI")) {
    Fail ".env da KASSA_API_URL (sayt manzili) yoki DATABASE_URL to'ldirilmagan."
}
New-Item -ItemType Directory -Force (Join-Path $Root "logs") | Out-Null
Push-Location $Root
& $Php bin\bot-check.php
$checkOk = ($LASTEXITCODE -eq 0)
Pop-Location
if (-not $checkOk) { Fail "Tekshiruv o'tmadi - yuqoridagi xabarlarni o'qing." }

# ---------------------------------------------------------------------------
Step "3/4 Avtomatik ishga tushish"
# ---------------------------------------------------------------------------
# Eski alohida zahira vazifasi endi kerak emas: zahirani bot o'zi oladi.
# Ikkalasi qolsa, har kecha ikki marta nusxa keladi.
foreach ($old in "Kassa zahira nusxa", $TaskName) {
    if (Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $old -Confirm:$false
    }
}
Get-CimInstance Win32_Process -Filter "Name='php.exe'" |
    Where-Object { $_.CommandLine -like "*bot.php*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$starter = Join-Path $Root "start-bot.ps1"
if (-not (Test-Path $starter)) { $starter = Join-Path $PSScriptRoot "start-bot.ps1" }
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$starter`"" `
    -WorkingDirectory $Root
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

if ($IsAdmin) {
    # Kompyuter yoqilishi bilan, hech kim tizimga kirmasa ham ishlaydi
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Ok "Kompyuter yoqilganda ishga tushadi (hisobga kirmasdan ham)"
} else {
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
    Ok "Siz Windows'ga kirganingizda ishga tushadi"
    Write-Host "    (Kompyuter yoqilishi bilan ishlashi uchun ORNATISH.bat ni Administrator sifatida oching)"
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description "Kassa Telegram boti: hisobot, zahira, qarz eslatmasi, ogohlantirishlar" | Out-Null

# ---------------------------------------------------------------------------
Step "4/4 Ishga tushirish"
# ---------------------------------------------------------------------------
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 8
$log = Join-Path $Root "logs\bot.log"
if (Test-Path $log) { Get-Content $log -Tail 3 | ForEach-Object { Write-Host "    $_" } }
$running = Get-CimInstance Win32_Process -Filter "Name='php.exe'" | Where-Object { $_.CommandLine -like "*bot.php*" }
if ($running) { Ok "Bot ishlayapti. Telegramda botga /start yozib tekshiring." }
else { Write-Host "    Bot hali ko'rinmadi - logs\bot.log ni tekshiring." -ForegroundColor Yellow }

Write-Host ""
Write-Host "Tayyor." -ForegroundColor Green
Read-Host "Chiqish uchun Enter"
