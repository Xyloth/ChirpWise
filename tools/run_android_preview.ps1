$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $root "tools\android-build"
$env:JAVA_HOME = Join-Path $buildRoot "jdk-17"
$env:ANDROID_HOME = Join-Path $buildRoot "android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:PATH = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:ANDROID_HOME\emulator;$env:ANDROID_HOME\platform-tools;$env:PATH"

$adb = Join-Path $env:ANDROID_HOME "platform-tools\adb.exe"
$emulator = Join-Path $env:ANDROID_HOME "emulator\emulator.exe"
$apk = Join-Path $root "dist\android\ChirpWise-Northeast-v0.2.2.apk"

if (!(Test-Path $apk)) {
    throw "APK not found: $apk"
}

$running = & $adb devices | Select-String -Pattern "emulator-\d+\s+device"
if (!$running) {
    Start-Process -FilePath $emulator -ArgumentList @("-avd", "ChirpWise_Preview", "-no-snapshot-load", "-gpu", "swiftshader_indirect")
}

& $adb wait-for-device
$deadline = (Get-Date).AddMinutes(5)
do {
    Start-Sleep -Seconds 3
    $booted = (& $adb shell getprop sys.boot_completed 2>$null).Trim()
} while ($booted -ne "1" -and (Get-Date) -lt $deadline)

if ($booted -ne "1") {
    throw "Android emulator did not finish booting within 5 minutes."
}

& $adb install -r $apk
& $adb shell monkey -p com.xyflow.birdtrainer -c android.intent.category.LAUNCHER 1 | Out-Null
Write-Host "ChirpWise is running in the Android emulator."
