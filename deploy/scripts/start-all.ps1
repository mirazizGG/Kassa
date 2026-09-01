# SmartKassa - xizmatlarni ishga tushirish.
#   - Backend (uvicorn :8000) - frontendni ham o'zi beradi. LAN uchun shu yetadi.
#   - Caddy (:8080) va Cloudflare Tunnel - FAQAT internet orqali kirish kerak bo'lsa.
# Kompyuter yonganda avtomatik ishlashi uchun: install-autostart.ps1 ni bir marta bajaring.

. "$PSScriptRoot\_paths.ps1"

Write-Step "SmartKassa ishga tushmoqda..."

# --- 0. Tekshiruvlar ---
if (-not (Test-Path (Join-Path $BackendDir ".env"))) {
	Write-Err2 "backend\.env topilmadi. Avval first-time-setup.ps1 (yoki install-smartkassa.ps1) ni bajaring."
	exit 1
}
if (-not (Test-Path (Join-Path $DistDir "index.html"))) {
	if (Get-Command npm -ErrorAction SilentlyContinue) {
		Write-Warn2 "frontend\dist bo'sh. Build qilinmoqda..."
		Push-Location $FrontendDir
		npm run build
		Pop-Location
	} else {
		Write-Err2 "frontend\dist bo'sh va npm yo'q. Frontend uyda build qilinib repoga qo'shilishi kerak (deploy\publish.ps1)."
		exit 1
	}
}

# --- 1. Backend (uvicorn 0.0.0.0:8000, frontend ham shu yerda) ---
if (Get-PidFromFile $BackendPid) {
	Write-Warn2 "Backend allaqachon ishlayapti"
} else {
	$p = Start-Process -FilePath "python" -ArgumentList "main.py" `
		-WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru `
		-RedirectStandardOutput (Join-Path $RunDir "backend.out.log") `
		-RedirectStandardError  (Join-Path $RunDir "backend.err.log")
	$p.Id | Out-File $BackendPid -Encoding ascii
	Write-Ok "Backend ishga tushdi (PID $($p.Id)) - http://localhost:$BackendPort"
}

# --- 2. Caddy (ixtiyoriy: internet orqali kirish uchun) ---
$env:KASSA_DIST   = $DistDir
$env:KASSA_DEPLOY = $DeployDir
if (Get-PidFromFile $CaddyPid) {
	Write-Warn2 "Caddy allaqachon ishlayapti"
} elseif (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
	Write-Warn2 "caddy yo'q - o'tkazib yuborildi (LAN uchun kerak emas: http://SERVER-IP:$BackendPort)."
} else {
	$p = Start-Process -FilePath "caddy" -ArgumentList "run --config `"$CaddyfilePath`" --adapter caddyfile" `
		-WorkingDirectory $DeployDir -WindowStyle Hidden -PassThru `
		-RedirectStandardOutput (Join-Path $RunDir "caddy.out.log") `
		-RedirectStandardError  (Join-Path $RunDir "caddy.err.log")
	$p.Id | Out-File $CaddyPid -Encoding ascii
	Write-Ok "Caddy ishga tushdi (PID $($p.Id)) - http://localhost:$CaddyPort"
}

# --- 3. Cloudflare Tunnel (ixtiyoriy) ---
if (Get-PidFromFile $CloudflaredPid) {
	Write-Warn2 "Cloudflared allaqachon ishlayapti"
} elseif (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
	Write-Warn2 "cloudflared yo'q - tashqi kirish o'chiq (LAN ishlayveradi)."
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
