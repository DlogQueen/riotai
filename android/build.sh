#!/usr/bin/env bash
# Build InTheRaw.apk without Gradle: aapt2 -> javac -> d8 -> zipalign -> apksigner.
# The app has no third-party dependencies, so there is nothing to resolve and
# the build stays fast and offline after the SDK is present.
set -euo pipefail

: "${ANDROID_HOME:?set ANDROID_HOME to your Android SDK root}"
# build-tools 34.0.0 ships a d8 that fails to dex non-static inner classes and
# classes implementing a generic interface. 35.0.0 fixes both.
BT="$ANDROID_HOME/build-tools/35.0.0"
JAR="$ANDROID_HOME/platforms/android-34/android.jar"

cd "$(dirname "$0")"
SRC=app/src/main
OUT=build
rm -rf "$OUT"; mkdir -p "$OUT/res" "$OUT/classes"

echo "==> resources"
"$BT/aapt2" compile --dir "$SRC/res" -o "$OUT/res.zip"
"$BT/aapt2" link \
  -o "$OUT/base.apk" \
  -I "$JAR" \
  --manifest "$SRC/AndroidManifest.xml" \
  -A "$SRC/assets" \
  --java "$OUT" \
  --min-sdk-version 24 --target-sdk-version 34 \
  "$OUT/res.zip"

echo "==> java"
find "$SRC/java" "$OUT/com" -name '*.java' > "$OUT/sources.txt" 2>/dev/null || \
  find "$SRC/java" -name '*.java' > "$OUT/sources.txt"
javac -nowarn -source 8 -target 8 -bootclasspath "$JAR" -classpath "$JAR" \
  -d "$OUT/classes" @"$OUT/sources.txt" 2>&1 | grep -v 'bootstrap class path\|source value 8\|target value 8\|deprecat' || true

echo "==> dex"
"$BT/d8" --min-api 24 --output "$OUT" $(find "$OUT/classes" -name '*.class')

echo "==> package"
cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT" && zip -q unsigned.apk classes.dex)

if [ ! -f raw-keystore.jks ]; then
  echo "==> keystore"
  keytool -genkeypair -keystore raw-keystore.jks -alias intheraw -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass rawrawraw -keypass rawrawraw \
    -dname "CN=In the Raw, OU=riotai, O=In the Raw, L=, S=, C=US" >/dev/null 2>&1
fi

"$BT/zipalign" -f 4 "$OUT/unsigned.apk" "$OUT/InTheRaw.apk"
"$BT/apksigner" sign --ks raw-keystore.jks --ks-pass pass:rawrawraw --key-pass pass:rawrawraw \
  --v1-signing-enabled true --v2-signing-enabled true "$OUT/InTheRaw.apk"
"$BT/apksigner" verify "$OUT/InTheRaw.apk" && echo "==> signature OK"

ls -lh "$OUT/InTheRaw.apk"
