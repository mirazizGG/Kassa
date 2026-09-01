# SmartKassa - GitHub'dan yangilanishlarni olish va qayta ishga tushirish.
#
# 2 xil ishlatiladi:
#   1) Qo'lda:   .\update.ps1
#   2) Ilova ichidagi "Yangilash" tugmasi:  .\update.ps1 -FromApp
#      (backend uni alohida jarayonda ishga tushiradi va holatni
#       deploy\run\update-status.json ga yozib boradi)
#
# Savdo vaqtida bajarmang - backend 5-10 soniyaga to'xtaydi.

param(
	[switch]$FromApp
)

. "$PSScriptRoot\_paths.ps1"

$StatusFile = Join-Path $RunDir "update-status.json"

function Set-Status {
	param([string]$Phase, [string]$Message, $Ok = $null, [switch]$Running)
	$obj = [ordered]@{
		running    = [bool]$Running
		ok         = $Ok
		phase      = $Phase
		message    = $Message
		updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
		commit     = (git -C $RepoRoot rev-parse --short HEAD 2>$null)
	}
	$obj | ConvertTo-Json -Compress | Set-Content -Path $StatusFile -Encoding utf8
}

function Fail-Status($msg) {
	Write-Err2 $msg
	if ($FromApp) { Set-Status -Phase "error" -Message $msg -Ok $false }
	exit 1
}

Push-Location $RepoRoot
try {
	if ($FromApp) { Set-Status -Phase "tekshirilmoqda" -Message "GitHub tekshirilmoqda..." -Running }

	Write-Step "GitHub'dan tekshirilmoqda..."
	git fetch origin
	if ($LASTEXITCODE -ne 0) { Fail-Status "GitHub bilan bog'lanib bo'lmadi (internet?)" }

	$branch = (git rev-parse --abbrev-ref HEAD).Trim()
	$local  = (git rev-parse HEAD).Trim()
	$remote = (git rev-parse "origin/$branch").Trim()

	if ($local -eq $remote) {
		Write-Ok "Hammasi eng yangi. Yangilanish shart emas."
		if ($FromApp) { Set-Status -Phase "done" -Message "Allaqachon eng yangi versiya" -Ok $true }
		exit 0
	}

	$dirty = git status --porcelain
	if ($dirty) {
		Fail-Status "Serverda saqlanmagan o'zgarishlar bor. 'git checkout -- .' qiling."
	}

	Write-Step "Yangi commitlar:"
	git --no-pager log --oneline "$local..$remote"

	# --- Bazadan zahira nusxa (yangilanishdan oldin, ehtiyot uchun) ---
	if ($FromApp) { Set-Status -Phase "zahira" -Message "Bazadan zahira nusxa olinmoqda..." -Running }
	Write-Step "Zahira nusxa olinmoqda..."
	Push-Location $BackendDir
	$bk = python -c "from utils.backup import create_backup; p = create_backup(); print(p or '')" 2>&1
	Pop-Location
	if ($bk -and (Test-Path $bk)) {
		Write-Ok "Zahira: $bk"
	} else {
		Write-Warn2 "Zahira olinmadi (SQLite emasmi?) - yangilanish davom etadi: $bk"
	}

	# --- Kodni tortib olish ---
	if ($FromApp) { Set-Status -Phase "yuklanmoqda" -Message "Yangi kod yuklanmoqda..." -Running }
	Write-Step "git pull..."
	git pull --ff-only origin $branch
	if ($LASTEXITCODE -ne 0) { Fail-Status "git pull xato berdi" }

	$changed = git --no-pager diff --name-only "$local..$remote"

	# --- Backend kutubxonalari ---
	if ($changed | Select-String "backend/requirements.txt") {
		if ($FromApp) { Set-Status -Phase "kutubxonalar" -Message "Kutubxonalar o'rnatilmoqda..." -Running }
		Write-Step "requirements.txt o'zgardi - pip install..."
		python -m pip install -r (Join-Path $BackendDir "requirements.txt")
	}

	# --- Frontend ---
	# frontend/dist repo bilan birga keladi (uyda `deploy\publish.ps1` build qilgan).
	# Shuning uchun serverda npm/build KERAK EMAS - `git pull` yangi dist'ni ham oldi.
	if ($changed | Select-String "^frontend/dist/") {
		Write-Ok "Frontend yangilandi (tayyor dist repodan keldi)"
	} elseif (($changed | Select-String "^frontend/") -and (Get-Command npm -ErrorAction SilentlyContinue)) {
		if ($FromApp) { Set-Status -Phase "qurilmoqda" -Message "Frontend qurilmoqda..." -Running }
		Write-Step "Frontend manbasi o'zgardi, dist yangilanmagan - npm build..."
		Push-Location $FrontendDir
		if ($changed | Select-String "frontend/package-lock.json") { npm ci }
		npm run build
		$buildOk = $LASTEXITCODE -eq 0
		Pop-Location
		if (-not $buildOk) { Fail-Status "Frontend build xato berdi" }
	}

	# --- Backendni qayta ishga tushirish ---
	if ($FromApp) { Set-Status -Phase "qayta_ishga_tushmoqda" -Message "Backend qayta ishga tushmoqda..." -Running }
	Write-Step "Backend qayta ishga tushmoqda..."

	# PID fayli bo'lsa - o'shani; bo'lmasa main.py ishlatayotgan python'ni topamiz
	$stopped = $false
	$id = Get-PidFromFile $BackendPid
	if ($id) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; $stopped = $true }
	if (-not $stopped) {
		Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
			Where-Object { $_.CommandLine -like "*main.py*" } |
			ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
	}
	Start-Sleep -Seconds 2

	$p = Start-Process -FilePath "python" -ArgumentList "main.py" `
		-WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru `
		-RedirectStandardOutput (Join-Path $RunDir "backend.out.log") `
		-RedirectStandardError  (Join-Path $RunDir "backend.err.log")
	$p.Id | Out-File $BackendPid -Encoding ascii
	Write-Ok "Backend ishga tushdi (PID $($p.Id))"

	# Backend javob berguncha kutamiz
	$up = $false
	for ($i = 0; $i -lt 30; $i++) {
		Start-Sleep -Seconds 1
		try {
			$null = Invoke-WebRequest "http://127.0.0.1:$BackendPort/health" -TimeoutSec 3 -UseBasicParsing
			$up = $true; break
		} catch {}
	}
	if (-not $up) { Fail-Status "Backend qayta ishga tushmadi. deploy\run\backend.err.log ni ko'ring." }

	$new = (git rev-parse --short HEAD).Trim()
	Write-Ok "Yangilanish tugadi: $new"
	if ($FromApp) { Set-Status -Phase "done" -Message "Yangilandi ($new)" -Ok $true }
}
catch {
	Fail-Status "Kutilmagan xato: $_"
}
finally {
	Pop-Location
}
