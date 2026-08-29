# SmartKassa - SERVER kompyuterda bir marta bajariladigan sozlash.

. "$PSScriptRoot\_paths.ps1"

Write-Step "Dasturlar tekshirilmoqda..."
$missing = @()
foreach ($cmd in "git","python","node","npm") {
	if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { $missing += $cmd }
}
if ($missing) { Write-Err2 "Topilmadi: $($missing -join ', '). Avval o'rnating."; exit 1 }
Write-Ok ("git={0}  python={1}  node={2}" -f (git --version), (python --version), (node --version))

if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
	Write-Warn2 "caddy yo'q. O'rnatish:  winget install CaddyServer.Caddy"
}
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
	Write-Warn2 "cloudflared yo'q. O'rnatish:  winget install Cloudflare.cloudflared"
}

# --- backend/.env ---
$beEnv = Join-Path $BackendDir ".env"
if (-not (Test-Path $beEnv)) {
	Copy-Item (Join-Path $DeployDir "env\backend.env.example") $beEnv
	$key = python -c "import secrets; print(secrets.token_hex(32))"
	(Get-Content $beEnv) -replace "BU_YERGA_TASODIFIY_64_BELGILI_KALIT", $key | Set-Content $beEnv -Encoding utf8
	Write-Ok "backend\.env yaratildi (SECRET_KEY avtomatik to'ldirildi)"
	Write-Warn2 "backend\.env ni oching va ALLOWED_ORIGINS ga o'z domeningizni yozing."
} else {
	Write-Ok "backend\.env allaqachon mavjud"
}

# frontend/.env.production repo bilan birga keladi (VITE_API_URL=/api) - o'zgartirish shart emas.

# --- Kutubxonalar ---
Write-Step "Backend kutubxonalari (pip install)..."
python -m pip install -r (Join-Path $BackendDir "requirements.txt")

Write-Step "Frontend kutubxonalari (npm ci)..."
Push-Location $FrontendDir
npm ci
Write-Step "Frontend build..."
npm run build
Pop-Location

Write-Ok "Sozlash tugadi."
Write-Host ""
Write-Step "Keyingi qadamlar:"
Write-Host "  1. backend\.env da ALLOWED_ORIGINS ni tekshiring" -ForegroundColor White
Write-Host "  2. Cloudflare Tunnel yarating (deploy\README.md 3-bo'lim)" -ForegroundColor White
Write-Host "  3. .\start-all.ps1" -ForegroundColor White
Write-Host "  4. .\install-autostart.ps1  (kompyuter yonganda avtomatik ishlashi uchun)" -ForegroundColor White
