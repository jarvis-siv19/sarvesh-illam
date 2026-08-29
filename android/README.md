# Sarvesh Illam Android APK

This is a Capacitor shell around the same `www/` dashboard used on the LAN.
On first launch, tap the server address beside **Sarvesh Illam** and enter the
dashboard address, for example `http://192.168.0.4:1984`.

## Build a release APK

Install Android Studio with Android SDK Platform 35 and JDK 17 or newer. Then:

```sh
npm install
npm run android:sync
cd android
./gradlew assembleRelease
```

The unsigned APK is written to `app/build/outputs/apk/release/`. Sign it with a
private keystore before installing/distributing it. Keep the same keystore for
all future updates or Android will reject updates to the app.

The app intentionally supports clear-text HTTP because this dashboard currently
runs only on a trusted LAN. Do not expose the service or APK's configured server
to the public internet. Move to an internal HTTPS hostname before enabling any
remote access.
