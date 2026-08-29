# SmartKassa — xizmatlar holati.

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
	$h = Invoke-RestMethod "http://127.0.0.1:$BackendPort/health" -TimeoutSec 5
	Write-Host "  Backend /health: OK" -ForegroundColor Green
} catch {
	Write-Host "  Backend /health: JAVOB YO'Q" -ForegroundColor Red
}
try {
	$null = Invoke-WebRequest "http://127.0.0.1:$CaddyPort/" -TimeoutSec 5 -UseBasicParsing
	Write-Host "  Frontend (Caddy): OK" -ForegroundColor Green
} catch {
	Write-Host "  Frontend (Caddy): JAVOB YO'Q" -ForegroundColor Red
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp,Manual -ErrorAction SilentlyContinue |
	Where-Object { $_.IPAddress -notlike "169.*" } | Select-Object -First 1).IPAddress
if ($ip) {
	Write-Host ""
	Write-Host "  Do'kon ichidan kirish:  http://${ip}:$CaddyPort" -ForegroundColor Cyan
}
