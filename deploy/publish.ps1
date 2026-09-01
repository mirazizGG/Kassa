<#
================================================================================
  SmartKassa - o'zgarishni chiqarish  (UYDAGI / dasturchi kompyuterda)
================================================================================
  Frontend'ni build qiladi, dist'ni ham qo'shib commit qiladi va push qiladi.
  Do'kon serveri hech narsa build qilmaydi - u tayyor `frontend/dist` ni oladi.

  ISHLATISH:
    .\deploy\publish.ps1 "o'zgarish haqida qisqa izoh"

  Izoh berilmasa - "update" yoziladi.
================================================================================
#>
param(
    [Parameter(Position = 0)]
    [string]$Message = "update"
)

$ErrorActionPreference = "Stop"
$RepoRoot   = Split-Path $PSScriptRoot -Parent
$FrontendDir = Join-Path $RepoRoot "frontend"

function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Die($m)  { Write-Host "  X   $m" -ForegroundColor Red; exit 1 }

Push-Location $RepoRoot
try {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Die "npm topilmadi (Node.js kerak - faqat shu kompyuterda)." }

    $branch = (git rev-parse --abbrev-ref HEAD).Trim()

    Step "Frontend build..."
    Push-Location $FrontendDir
    npm run build
    $ok = $LASTEXITCODE -eq 0
    Pop-Location
    if (-not $ok) { Die "Build xato berdi - push qilinmadi." }
    Ok "dist yangilandi"

    Step "Lint (ogohlantirish uchun)..."
    Push-Location $FrontendDir
    npm run lint
    Pop-Location

    Step "Git: commit + push ($branch)"
    git add -A
    $pending = git status --porcelain
    if (-not $pending) {
        Ok "O'zgarish yo'q - push shart emas."
        return
    }
    git commit -m $Message
    git push origin $branch
    Ok "Push qilindi. Endi do'konda 'Yangilash' tugmasini bosish mumkin."
}
finally {
    Pop-Location
}
