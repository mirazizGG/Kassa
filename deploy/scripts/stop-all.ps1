# SmartKassa - hamma xizmatlarni to'xtatish.

. "$PSScriptRoot\_paths.ps1"

Write-Step "SmartKassa to'xtatilmoqda..."
Stop-ByPidFile $CloudflaredPid "Cloudflared"
Stop-ByPidFile $CaddyPid       "Caddy"
Stop-ByPidFile $BackendPid     "Backend"
Write-Ok "Tugadi."
