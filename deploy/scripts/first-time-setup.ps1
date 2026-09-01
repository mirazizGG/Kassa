# SmartKassa - SERVER kompyuterda bir marta bajariladigan sozlash.
#
# Kerak: Git + Python.  Node.js/Caddy SHART EMAS (frontend repodagi dist'dan olinadi,
# backend uni o'zi beradi). install-smartkassa.ps1 bularning hammasini o'zi qiladi.

. "$PSScriptRoot\_paths.ps1"

Write-Step "Dasturlar tekshirilmoqda..."
$missing = @()
foreach ($cmd in "git", "python") {
	if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { $missing += $cmd }
}
if ($missing) { Write-Err2 "Topilmadi: $($missing -join ', '). Avval o'rnating."; exit 1 }
Write-Ok ("git={0}  python={1}" -f (git --version), (python --version))

$hasNode = [bool](Get-Command npm -ErrorAction SilentlyContinue)
if (-not $hasNode) { Write-Warn2 "Node.js/npm yo'q - frontend repodagi tayyor dist'dan olinadi (bu normal)." }
if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
	Write-Warn2 "caddy yo'q - LAN uchun kerak emas (backend :8000 da frontendni ham beradi)."
}

# --- backend/.env ---
$beEnv = Join-Path $BackendDir ".env"
if (-not (Test-Path $beEnv)) {
	Copy-Item (Join-Path $DeployDir "env\backend.env.example") $beEnv
	$key = python -c "import secrets; print(secrets.token_hex(32))"
	(Get-Content $beEnv) -replace "BU_YERGA_TASODIFIY_64_BELGILI_KALIT", $key | Set-Content $beEnv -Encoding utf8
	Write-Ok "backend\.env yaratildi (SECRET_KEY avtomatik to'ldirildi)"
} else {
	Write-Ok "backend\.env allaqachon mavjud"
}

# --- Backend kutubxonalari ---
Write-Step "Backend kutubxonalari (pip install)..."
python -m pip install --upgrade pip
python -m pip install -r (Join-Path $BackendDir "requirements.txt")

# --- Frontend ---
if (Test-Path (Join-Path $DistDir "index.html")) {
	Write-Ok "frontend\dist tayyor (repodan keldi)"
} elseif ($hasNode) {
	Write-Step "Frontend build (npm ci + build)..."
	Push-Location $FrontendDir
	npm ci
	npm run build
	Pop-Location
} else {
	Write-Err2 "frontend\dist ham yo'q, npm ham yo'q. Uyda 'deploy\publish.ps1' bilan build qilib push qiling."
	exit 1
}

Write-Ok "Sozlash tugadi."
Write-Host ""
Write-Step "Keyingi qadam:  .\start-all.ps1   (yoki install-autostart.ps1 bilan avtomat qiling)"
