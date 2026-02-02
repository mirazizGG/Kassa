$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/token" -Body @{username="admin"; password="123"} -ContentType "application/x-www-form-urlencoded"
$token = $response.access_token
Write-Host "Token: $token"

try {
    $logsResponse = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/audit/logs?start_date=2026-02-02&end_date=2026-02-02" -Headers @{Authorization = "Bearer $token"}
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    $stream = $_.Exception.Response.GetResponseStream()
    $reader = New-Object System.IO.StreamReader($stream)
    $errorBody = $reader.ReadToEnd()
    Write-Host "Error Body: $errorBody"
}
