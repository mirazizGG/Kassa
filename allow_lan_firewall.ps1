New-NetFirewallRule -DisplayName "Kassa Backend (8000)" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Domain
New-NetFirewallRule -DisplayName "Kassa Frontend (5173)" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Private,Domain
Write-Output "Firewall qoidalari qo'shildi."
