# SmartKassa — GitHub'dan yangilanishlarni olish va qayta ishga tushirish.
#
# Uydan / boshqa kompyuterdan o'zgartirish kiritib GitHub'ga push qilganingizdan keyin,
# do'kondagi SERVER kompyuterda shu skriptni bir marta bajaring.
#
# Ishlatilishi (server kompyuterda, PowerShell'da):
#   cd <repo>\deploy\scripts
#   .\update.ps1
#
# Savdo vaqtida bajarmang — backend 5-10 soniyaga to'xtaydi.

. "$PSScriptRoot\_paths.ps1"

Push-Location $RepoRoot
try {
	# --- 1. O'zgarishlarni tekshirish ---
	Write-Step "GitHub'dan tekshirilmoqda..."
	git fetch origin
	$local  = (git rev-parse HEAD).Trim()
	$remote = (git rev-parse '@{u}').Trim()

	if ($local -eq $remote) {
		Write-Ok "Hammasi eng yangi. Yangilanish shart emas."
		exit 0
	}

	$dirty = git status --porcelain
	if ($dirty) {
		Write-Err2 "Server kompyuterda saqlanmagan o'zgarishlar bor:"
		git status --short
		Write-Err2 "Ularni bekor qilish uchun:  git checkout -- .   keyin qayta urinib ko'ring."
		exit 1
	}

	Write-Step "Yangi commitlar:"
	git --no-pager log --oneline "$local..$remote"

	# --- 2. Kodni tortib olish ---
	Write-Step "git pull..."
	git pull --ff-only origin (git rev-parse --abbrev-ref HEAD)

	# --- 3. Backend kutubxonalari ---
	$reqChanged = git --no-pager diff --name-only "$local..$remote" | Select-String "backend/requirements.txt"
	if ($reqChanged) {
		Write-Step "requirements.txt o'zgardi — pip install..."
		python -m pip install -r (Join-Path $BackendDir "requirements.txt")
	}

	# --- 4. Frontend ---
	$feChanged = git --no-pager diff --name-only "$local..$remote" | Select-String "^frontend/"
	if ($feChanged) {
		Write-Step "Frontend o'zgardi — npm ci + build..."
		Push-Location $FrontendDir
		if (git --no-pager diff --name-only "$local..$remote" | Select-String "frontend/package-lock.json") {
			npm ci
		}
		npm run build
		Pop-Location
		Write-Ok "Frontend qayta yig'ildi (Caddy o'zi yangi fayllarni beradi)"
	}

	# --- 5. Backendni qayta ishga tushirish ---
	Write-Step "Backend qayta ishga tushmoqda..."
	Stop-ByPidFile $BackendPid "Backend"
	Start-Sleep -Seconds 2
	$p = Start-Process -FilePath "python" -ArgumentList "main.py" `
		-WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru `
		-RedirectStandardOutput (Join-Path $RunDir "backend.out.log") `
		-RedirectStandardError  (Join-Path $RunDir "backend.err.log")
	$p.Id | Out-File $BackendPid -Encoding ascii
	Write-Ok "Backend ishga tushdi (PID $($p.Id))"

	Start-Sleep -Seconds 5
	& "$PSScriptRoot\status.ps1"
	Write-Ok "Yangilanish tugadi: $remote"
}
finally {
	Pop-Location
}
