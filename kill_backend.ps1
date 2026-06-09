# Tue les processus uvicorn éventuellement restés en place (en cas de plantage Tauri).

Get-Process | Where-Object {
    $_.ProcessName -in @("python", "python3", "uvicorn", "backend") -and
    $_.MainWindowTitle -notlike "*PowerShell*"
} | ForEach-Object {
    try {
        $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdline -match "backend.main|run_backend|uvicorn") {
            Write-Host "Kill PID $($_.Id) : $cmdline"
            Stop-Process -Id $_.Id -Force
        }
    } catch {}
}
