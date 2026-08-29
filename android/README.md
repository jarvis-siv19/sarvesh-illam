# Sarvesh Illam Android APK

This is a Capacitor shell around the same `www/` dashboard used on the LAN.
On first launch, tap the server address beside **Sarvesh Illam** and enter the
dashboard address, for example `http://192.168.0.4:1984`.

## Build a release APK

Install Android Studio with Android SDK Platform 35. This repository's build
script uses `.tools/jdk-17` automatically when it exists, so a system JDK is
not required. Then:

```sh
npm install
./scripts/build-android.sh
```

The debug APK is written to `android/app/build/outputs/apk/debug/`. For a
release APK, run `./gradlew assembleRelease` from `android/` using the same
`JAVA_HOME`. Sign it with a
private keystore before installing/distributing it. Keep the same keystore for
all future updates or Android will reject updates to the app.

The app intentionally supports clear-text HTTP because this dashboard currently
runs only on a trusted LAN. Do not expose the service or APK's configured server
to the public internet. Move to an internal HTTPS hostname before enabling any
remote access.
