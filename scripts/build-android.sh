#!/usr/bin/env bash
# Build with the project-local JDK when present, so no system Java install is
# required. Populate .tools/jdk-17 with an ARM64 JDK 17 distribution first.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -d .tools/jdk-17 ]; then
  export JAVA_HOME="$PWD/.tools/jdk-17"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

if [ -d .tools/android-sdk ]; then
  export ANDROID_HOME="$PWD/.tools/android-sdk"
  export ANDROID_SDK_ROOT="$ANDROID_HOME"
  printf 'sdk.dir=%s\n' "$ANDROID_HOME" > android/local.properties
fi

npm run android:sync
cd android
exec ./gradlew assembleDebug
