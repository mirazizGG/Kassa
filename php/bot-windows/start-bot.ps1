# Kassa botini ishlatib turadi: yiqilsa yoki internet uzilsa 15 soniyadan keyin qayta ko'taradi.
# Buni "Kassa bot" vazifasi chaqiradi (install.ps1 yaratadi). Qo'lda chaqirish shart emas.
# Fayl ataylab faqat ASCII.

$Root = $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "app\bootstrap.php"))) {
    $Root = Split-Path $PSScriptRoot -Parent
}
$Php = Join-Path $Root "runtime\php\php.exe"
if (-not (Test-Path $Php)) { $Php = "php.exe" }
$Log = Join-Path $Root "logs\bot-console.log"
New-Item -ItemType Directory -Force (Join-Path $Root "logs") | Out-Null
Set-Location $Root

while ($true) {
    # Jurnal cheksiz o'smasin
    if ((Test-Path $Log) -and ((Get-Item $Log).Length -gt 5MB)) {
        Move-Item $Log "$Log.old" -Force
    }
    Add-Content $Log ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] start-bot: bot ishga tushirilmoqda")
    # cmd orqali: PowerShell 5.1 ning *>> operatori UTF-16 yozib, jurnalni buzadi
    cmd /c "`"$Php`" bin\bot.php >> `"$Log`" 2>&1"
    Add-Content $Log ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] start-bot: bot to'xtadi (kod $LASTEXITCODE), 15 soniyadan keyin qayta")
    Start-Sleep -Seconds 15
}
