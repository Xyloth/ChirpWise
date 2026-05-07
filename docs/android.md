# Android Build

The Android V1 app is a native Java APK with the full bird-sound pack bundled for offline use. Northeast / Ohio Valley is selected by default, but the app also includes an `All birds` tab. It does not need a server, internet access, Python, or Xeno-canto at runtime.

Current local artifact:

```text
dist/android/ChirpWise-Full-v0.2.6.apk
```

Current bundled pack:

- Default region: `Northeast / Ohio Valley`
- Default region species: 316
- Full app species with clips: 1,084
- Clips: 1,114
- Clip length: 20 seconds
- Audio source: real Xeno-canto recordings
- APK size: about 265 MB
- Android support: API 23+ / Android 6.0+
- SHA256: `E2387BBBA28139857AE358EE14197529ACD153654D0A5D02B345DDF26705D71D`

V0.2 adds the ChirpWise visual shell: rounded touch controls, splash screen, fixed bottom tabs, instant bird lookup, alphabetical study mode, quiz mode, local progress tracking, a progress ring, recent birds, and a needs-practice list. V0.2.2 adds real waveform metadata, live quiz playback progress, play/pause, and five-second seeking. V0.2.3 adds full Study/Listen browsing, letter filters, focused quiz packs, and custom quiz sets. V0.2.4 bundles the full clip catalog, keeps Northeast / Ohio Valley as the default region, and adds direct A-Z no-typing filters. V0.2.5 adds a bug-report email action and fuller quiz-source attribution for each revealed recording. V0.2.6 makes bug-report email prefill more reliable across Android email clients and adds app acknowledgements.

## Install On Android

Send the APK through a download link, Google Drive, GitHub Release, USB transfer, or direct file transfer.

On the phone:

1. Open the APK file.
2. Allow installs from that source when Android asks.
3. Tap install.
4. If Play Protect blocks it, open the details prompt and choose the install-anyway option.
5. Open `ChirpWise`.

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
python tools/build_android_assets.py --region all --pack-name "Full bird pack / Northeast focus" --clean
gradle -p android assembleRelease
```

The release APK is written to:

```text
android/app/build/outputs/apk/release/app-release.apk
```

For local sharing, copy it to:

```text
dist/android/ChirpWise-Full-v0.2.6.apk
```
