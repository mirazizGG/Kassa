# Kassa botini ishlatib turadi: yiqilsa yoki internet uzilsa 15 soniyadan keyin qayta ko'taradi.
# Buni "Kassa bot" vazifasi chaqiradi (install.ps1 yaratadi). Qo'lda chaqirish shart emas.
# Fayl ataylab faqat ASCII.

$Root = $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "app\bootstrap.php"))) {
    $Root = Split-Path $PSScriptRoot -Parent
}
$Php = Join-Path $Root "runtime\php\php.exe"
if (-not (Test-Path $Php)) { $Php = "php.exe" }
$Logs = Join-Path $Root "logs"
$Log = Join-Path $Logs "bot-console.log"
$Out = Join-Path $Logs "bot-stdout.tmp"
$Err = Join-Path $Logs "bot-stderr.tmp"
New-Item -ItemType Directory -Force $Logs | Out-Null
Set-Location $Root

function Stamp { "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "]" }

while ($true) {
    # Jurnal cheksiz o'smasin
    if ((Test-Path $Log) -and ((Get-Item $Log).Length -gt 5MB)) {
        Move-Item $Log "$Log.old" -Force
    }
    Add-Content $Log "$(Stamp) start-bot: bot ishga tushirilmoqda" -Encoding UTF8
    $code = -1
    try {
        # Start-Process: yo'lda bo'sh joy bo'lsa ham to'g'ri uzatadi, chiqishni
        # bayt-bayt yozadi (PowerShell 5.1 ning *>> operatori UTF-16 qilib buzardi).
        # Botning o'z jurnali logs\bot.log da; bu yerga faqat PHP xatolari tushadi.
        $proc = Start-Process -FilePath $Php -ArgumentList "bin\bot.php" -WorkingDirectory $Root `
            -NoNewWindow -Wait -PassThru -RedirectStandardOutput $Out -RedirectStandardError $Err
        $code = $proc.ExitCode
    } catch {
        Add-Content $Log "$(Stamp) start-bot: ishga tushirib bo'lmadi: $($_.Exception.Message)" -Encoding UTF8
    }
    foreach ($f in $Out, $Err) {
        if ((Test-Path $f) -and ((Get-Item $f).Length -gt 0)) {
            Get-Content $f -Encoding UTF8 | Select-Object -Last 30 | Add-Content $Log -Encoding UTF8
        }
    }
    Add-Content $Log "$(Stamp) start-bot: bot to'xtadi (kod $code), 15 soniyadan keyin qayta" -Encoding UTF8
    Start-Sleep -Seconds 15
}
