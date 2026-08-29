# SmartKassa — kompyuter yonganda avtomatik ishga tushishi uchun
# Windows "Scheduled Task" yaratadi.
#
# Administrator PowerShell'da bajaring.

. "$PSScriptRoot\_paths.ps1"

$taskName = "SmartKassa-Autostart"
$startScript = Join-Path $ScriptsDir "start-all.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
	-Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startScript`""

# Tizim yonganda + har kuni 06:00 da (agar tunda o'chib qolgan bo'lsa)
$trigger1 = New-ScheduledTaskTrigger -AtStartup
$trigger2 = New-ScheduledTaskTrigger -Daily -At 6am

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2)

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
	Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action `
	-Trigger $trigger1,$trigger2 -Principal $principal -Settings $settings `
	-Description "SmartKassa: backend + Caddy + Cloudflare Tunnel avtomatik ishga tushirish"

Write-Ok "'$taskName' vazifasi yaratildi."
Write-Warn2 "Eslatma: kompyuter yonganda hech kim login qilmasa ham ishlashi uchun"
Write-Warn2 "Windows'da avtomatik login (autologon) yoqilgani ma'qul, yoki bu PC doim login holatida tursin."
Write-Host ""
Write-Host "Sinash:  Start-ScheduledTask -TaskName $taskName" -ForegroundColor White
Write-Host "O'chirish:  Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false" -ForegroundColor White
