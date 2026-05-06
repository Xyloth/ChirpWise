# Android Packaging Notes

Current status: the desktop/local-web product is Android-ready at the data layer, but this machine does not currently have the Android build chain installed.

Missing local tools:

- Java/JDK
- Gradle
- Android SDK
- adb

The practical Android path is:

1. Build the app as a small Android shell around the existing local web UI.
2. Bundle the default `Northeast / Ohio Valley` pack first.
3. Keep other packs downloadable or copied into app storage later.
4. Ship an APK or AAB.

The 20-second MP3 clip dataset is ready for that. The current full clipped audio set is about 228 MB, while the raw original audio is about 3.5 GB and should not be bundled into a phone app.

For a direct text-message install link, the APK needs to be hosted somewhere reachable, such as a GitHub Release, Google Drive, or a small static download page. Android will require sideload approval unless the app is distributed through Google Play.

