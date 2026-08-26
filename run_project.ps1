# Start Kassa System
# This script kills existing Python/Node processes to prevent conflicts and starts the system.

Write-Host "Kassa Tizimini ishga tushirish..." -ForegroundColor Green

# 1. Kill existing processes (Optional - prevents conflicts)
Write-Host "Eski jarayonlarni to'xtatish..." -ForegroundColor Yellow
Stop-Process -Name "python" -ErrorAction SilentlyContinue
Stop-Process -Name "node" -ErrorAction SilentlyContinue
Stop-Process -Name "uvicorn" -ErrorAction SilentlyContinue

# 2. Check Database
if (-not (Test-Path "backend/market.db")) {
    Write-Host "Database topilmadi. Yangi yaratilmoqda..." -ForegroundColor Yellow
    # Trigger init_db via main.py implicitly or separate script if needed
    # main.py does init_db on startup, so we are good.
}

# 3. Start Backend
Write-Host "Back-end ishga tushirilmoqda..." -ForegroundColor Green
Start-Process -FilePath "python" -ArgumentList "backend/main.py" -WorkingDirectory "$PSScriptRoot" -WindowStyle Minimized

# Wait for backend to initialize
Start-Sleep -Seconds 5

# 4. Start Frontend
Write-Host "Front-end ishga tushirilmoqda..." -ForegroundColor Green
Set-Location "frontend"
if (-not (Test-Path "node_modules")) {
    Write-Host "Node modules o'rnatilmoqda..." -ForegroundColor Yellow
    npm install
}
Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory "$PSScriptRoot/frontend"

Write-Host "Tizim ishga tushdi!" -ForegroundColor Cyan
Write-Host "Backend: http://localhost:8000"
Write-Host "Frontend: http://localhost:5173"
