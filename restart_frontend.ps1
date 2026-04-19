# Clean restart script for Streamlit frontend

# Kill any existing Streamlit processes
Write-Host "Killing existing Streamlit processes..." -ForegroundColor Yellow
Get-Process streamlit -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*streamlit*"} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Clear Python cache
Write-Host "Clearing Python bytecode cache..." -ForegroundColor Yellow
Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Filter "*.pyc" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Clear Streamlit cache
Write-Host "Clearing Streamlit cache..." -ForegroundColor Yellow
$streamlitCache = "$env:USERPROFILE\.streamlit\cache"
if (Test-Path $streamlitCache) {
    Remove-Item $streamlitCache -Recurse -Force -ErrorAction SilentlyContinue
}

# Activate venv and restart
Write-Host "Starting fresh Streamlit instance..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1
python -m streamlit run frontend/app.py
