# Android Build

The Android V1 app is a native Java APK with the `Northeast / Ohio Valley` pack bundled for offline use. It does not need a server, internet access, Python, or Xeno-canto at runtime.

Current local artifact:

```text
dist/android/ChirpWise-Northeast-v0.2.0.apk
```

Current bundled pack:

- Region: `Northeast / Ohio Valley`
- Species: 316
- Clips: 346
- Clip length: 20 seconds
- Audio source: real Xeno-canto recordings
- APK size: about 81 MB
- Android support: API 23+ / Android 6.0+

V0.2 adds the ChirpWise visual shell: rounded touch controls, splash screen, fixed bottom tabs, instant bird lookup, alphabetical study mode, quiz mode, local progress tracking, a progress ring, recent birds, and a needs-practice list.

## Install On Android

Send the APK through a download link, Google Drive, GitHub Release, USB transfer, or direct file transfer.

On the phone:

1. Open the APK file.
2. Allow installs from that source when Android asks.
3. Tap install.
4. If Play Protect blocks it, open the details prompt and choose the install-anyway option.
5. Open `Bird Sound Trainer`.

This is sideloading, so Android will warn because the APK is not coming from Google Play.

## Launch On This Computer

Use the Android emulator preview:

```powershell
.\tools\run_android_preview.ps1
```

That script launches the `ChirpWise_Preview` virtual phone, installs the current APK, and opens the app. This is the closest desktop workflow because it runs the same Android package that will be sideloaded on the phone.

## Build Locally

The portable Android build chain is stored locally under `tools/android-build/` and intentionally ignored by Git.

```powershell
$base = (Resolve-Path 'tools/android-build').Path
$env:JAVA_HOME = Join-Path $base 'jdk-17'
$env:ANDROID_HOME = Join-Path $base 'android-sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:PATH = "$env:JAVA_HOME/bin;$base/gradle-8.10.2/bin;$env:ANDROID_HOME/platform-tools;$env:ANDROID_HOME/build-tools/35.0.0;$env:PATH"

python tools/update_region_membership_from_xeno.py --region northeast
python tools/backfill_region_audio.py --region northeast
python tools/create_training_clips.py --seconds 20 --bitrate 96k
python tools/build_android_assets.py --region northeast --pack-name "Northeast / Ohio Valley" --clean
gradle -p android assembleRelease
```

The release APK is written to:

```text
android/app/build/outputs/apk/release/app-release.apk
```

For local sharing, copy it to:

```text
dist/android/ChirpWise-Northeast-v0.2.0.apk
```
