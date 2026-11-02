$ErrorActionPreference = 'Stop'
$dashboardPython = 'E:\python.exe'
& $dashboardPython -m streamlit run "$PSScriptRoot\dashboard.py" --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
