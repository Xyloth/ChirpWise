$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Bird Sound Trainer.lnk"
$ExePath = Join-Path $Root "dist\BirdSoundTrainer\BirdSoundTrainer.exe"
$PythonLauncher = Join-Path $Root "tools\run_app.py"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)

if (Test-Path $ExePath) {
  $Shortcut.TargetPath = $ExePath
  $Shortcut.Arguments = ""
  $Shortcut.IconLocation = "$ExePath,0"
} else {
  $Shortcut.TargetPath = "python"
  $Shortcut.Arguments = "`"$PythonLauncher`""
  $Shortcut.IconLocation = "python.exe,0"
}

$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "Open Bird Sound Trainer"
$Shortcut.Save()

Write-Host "Created $ShortcutPath"

