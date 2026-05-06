$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

python -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
  python -m pip install pyinstaller
}

python -m PyInstaller BirdSoundTrainer.spec --noconfirm

Write-Host "Built dist\BirdSoundTrainer\BirdSoundTrainer.exe"

