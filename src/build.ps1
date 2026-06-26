# Build script for DBAdmin CLI
$AppName = "DB-CLI"
$MainScript = "main.py"
$IconPath = "assets\icon.ico"

Write-Host "Starting build process for $AppName..." -ForegroundColor Cyan

# 1. Clean previous builds and specs
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "DBAdmin.spec") { Remove-Item -Force "DBAdmin.spec" }
if (Test-Path "DBAdmin_Portable.spec") { Remove-Item -Force "DBAdmin_Portable.spec" }

# 2. Run PyInstaller
# --onefile: creates a single standalone executable (the definitive one)
# --name: the name of the executable
# --clean: clean cache before building
$PyInstallerArgs = @("--onefile", "--name", $AppName, "--clean", "--noconfirm", $MainScript)
if (Test-Path $IconPath) {
    $PyInstallerArgs = @("--onefile", "--name", $AppName, "--icon", $IconPath, "--clean", "--noconfirm", $MainScript)
} else {
    Write-Host "Icon not found at $IconPath; building without a custom icon." -ForegroundColor Yellow
}

& pyinstaller @PyInstallerArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nBuild completed successfully!" -ForegroundColor Green
    Write-Host "Copying the definitive executable to the main folder..." -ForegroundColor Yellow
    Copy-Item "dist\$AppName.exe" -Destination ".\$AppName.exe" -Force
    if (Test-Path "..\media") {
        Copy-Item "dist\$AppName.exe" -Destination "..\media\$AppName.exe" -Force
    }
    Write-Host "Done! DB-CLI.exe is ready and linked properly to your HTML landing page." -ForegroundColor Green
} else {
    Write-Host "`nBuild failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Write-Host "Asegúrate de haber instalado pyinstaller (pip install pyinstaller)" -ForegroundColor Yellow
}
