# SmartKassa - xizmatlar holati.

. "$PSScriptRoot\_paths.ps1"

function Show($name, $pidFile) {
	$id = Get-PidFromFile $pidFile
	if ($id) { Write-Host ("  {0,-12} ISHLAYAPTI (PID {1})" -f $name, $id) -ForegroundColor Green }
	else     { Write-Host ("  {0,-12} O'CHIQ" -f $name) -ForegroundColor Red }
}

Show "Backend"     $BackendPid
Show "Caddy"       $CaddyPid
Show "Cloudflared" $CloudflaredPid

Write-Host ""
try {
	$null = Invoke-WebRequest "http://127.0.0.1:$BackendPort/health" -TimeoutSec 5 -UseBasicParsing
	Write-Host "  Backend /health:   OK" -ForegroundColor Green
} catch {
	Write-Host "  Backend /health:   JAVOB YO'Q" -ForegroundColor Red
}
try {
	$r = Invoke-WebRequest "http://127.0.0.1:$BackendPort/" -TimeoutSec 5 -UseBasicParsing
	if ($r.Content -match "<div id=`"root`"") {
		Write-Host "  Frontend:          OK (backend beryapti)" -ForegroundColor Green
	} else {
		Write-Host "  Frontend:          index.html topilmadi - frontend\dist bo'sh?" -ForegroundColor Yellow
	}
} catch {
	Write-Host "  Frontend:          JAVOB YO'Q" -ForegroundColor Red
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp,Manual -ErrorAction SilentlyContinue |
	Where-Object { $_.IPAddress -notlike "169.*" -and $_.IPAddress -ne "127.0.0.1" } | Select-Object -First 1).IPAddress
if ($ip) {
	Write-Host ""
	Write-Host "  Do'kon ichidan kirish:  http://${ip}:$BackendPort" -ForegroundColor Cyan
	if (Get-PidFromFile $CaddyPid) {
		Write-Host "  Caddy orqali (:8080):   http://${ip}:$CaddyPort" -ForegroundColor DarkGray
	}
}
