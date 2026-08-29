# SmartKassa — hamma xizmatlarni ishga tushirish (backend + Caddy + Cloudflare Tunnel).
# Kompyuter yonganda avtomatik ishlashi uchun: install-autostart.ps1 ni bir marta bajaring.

. "$PSScriptRoot\_paths.ps1"

Write-Step "SmartKassa ishga tushmoqda..."

# --- 0. Tekshiruvlar ---
if (-not (Test-Path (Join-Path $BackendDir ".env"))) {
	Write-Err2 "backend\.env topilmadi. Avval first-time-setup.ps1 ni bajaring."
	exit 1
}
if (-not (Test-Path (Join-Path $DistDir "index.html"))) {
	Write-Warn2 "frontend\dist bo'sh. Build qilinmoqda..."
	Push-Location $FrontendDir
	npm run build
	Pop-Location
}

# --- 1. Backend (uvicorn 0.0.0.0:8000) ---
if (Get-PidFromFile $BackendPid) {
	Write-Warn2 "Backend allaqachon ishlayapti"
} else {
	$p = Start-Process -FilePath "python" -ArgumentList "main.py" `
		-WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru `
		-RedirectStandardOutput (Join-Path $RunDir "backend.out.log") `
		-RedirectStandardError  (Join-Path $RunDir "backend.err.log")
	$p.Id | Out-File $BackendPid -Encoding ascii
	Write-Ok "Backend ishga tushdi (PID $($p.Id))"
}

# --- 2. Caddy (frontend + /api reverse proxy, :8080) ---
$env:KASSA_DIST   = $DistDir
$env:KASSA_DEPLOY = $DeployDir
if (Get-PidFromFile $CaddyPid) {
	Write-Warn2 "Caddy allaqachon ishlayapti"
} elseif (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
	Write-Err2 "caddy topilmadi. O'rnatish: winget install CaddyServer.Caddy"
	exit 1
} else {
	$p = Start-Process -FilePath "caddy" -ArgumentList "run --config `"$CaddyfilePath`" --adapter caddyfile" `
		-WorkingDirectory $DeployDir -WindowStyle Hidden -PassThru `
		-RedirectStandardOutput (Join-Path $RunDir "caddy.out.log") `
		-RedirectStandardError  (Join-Path $RunDir "caddy.err.log")
	$p.Id | Out-File $CaddyPid -Encoding ascii
	Write-Ok "Caddy ishga tushdi (PID $($p.Id)) — http://localhost:$CaddyPort"
}

# --- 3. Cloudflare Tunnel ---
if (Get-PidFromFile $CloudflaredPid) {
	Write-Warn2 "Cloudflared allaqachon ishlayapti"
} elseif (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
	Write-Warn2 "cloudflared topilmadi — tashqi kirish ishlamaydi (lokal LAN ishlayveradi)."
	Write-Warn2 "O'rnatish: winget install Cloudflare.cloudflared"
} else {
	$p = Start-Process -FilePath "cloudflared" -ArgumentList "tunnel run" `
		-WindowStyle Hidden -PassThru `
		-RedirectStandardOutput (Join-Path $RunDir "cloudflared.out.log") `
		-RedirectStandardError  (Join-Path $RunDir "cloudflared.err.log")
	$p.Id | Out-File $CloudflaredPid -Encoding ascii
	Write-Ok "Cloudflared ishga tushdi (PID $($p.Id))"
}

Start-Sleep -Seconds 4
Write-Step "Holat:"
& "$PSScriptRoot\status.ps1"
