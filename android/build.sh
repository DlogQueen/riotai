#!/usr/bin/env bash
# Build the Ouija APK straight from the Android SDK — aapt2, javac, d8, apksigner.
# No Gradle, no AGP, nothing to resolve from a maven repo at build time.
#
#   ANDROID_HOME=/path/to/sdk ./android/build.sh
#
# Out: android/build/ouija.apk (debug-signed, sideloadable)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$HERE/build"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[ -n "$SDK" ] || { echo "set ANDROID_HOME to your Android SDK"; exit 1; }

BT="$(ls -d "$SDK"/build-tools/* | sort -V | tail -1)"
JAR="$(ls -d "$SDK"/platforms/* | sort -V | tail -1)/android.jar"
echo "🔨 build-tools: $(basename "$BT")   platform: $(basename "$(dirname "$JAR")")"

rm -rf "$BUILD/res" "$BUILD/gen" "$BUILD/classes" "$BUILD/dex" "$BUILD/apk"
mkdir -p "$BUILD"/{res,gen,classes,dex,apk,assets}

echo "🕯️  bundling the board"
python3 "$HERE/build_assets.py"

echo "📦 compiling resources"
"$BT/aapt2" compile --dir "$HERE/res" -o "$BUILD/res/res.zip"

echo "🔗 linking"
"$BT/aapt2" link \
  -I "$JAR" \
  --manifest "$HERE/AndroidManifest.xml" \
  -A "$BUILD/assets" \
  --min-sdk-version 24 --target-sdk-version 34 \
  --version-code 1 --version-name 1.0 \
  -o "$BUILD/apk/base.apk" \
  "$BUILD/res/res.zip"

echo "☕ javac"
# Every class here is top-level and no R.java is generated: the d8 shipped with
# build-tools 34 fails on nested class names, and the app reaches resources only
# through the manifest, so there is nothing to lose by staying flat.
find "$HERE/java" -name '*.java' > "$BUILD/sources.txt"
javac -nowarn --release 11 -classpath "$JAR" -d "$BUILD/classes" @"$BUILD/sources.txt"

echo "🎯 d8"
"$BT/d8" --lib "$JAR" --min-api 24 --release --output "$BUILD/dex" \
  $(find "$BUILD/classes" -name '*.class')

echo "🧷 packaging"
cp "$BUILD/apk/base.apk" "$BUILD/apk/unaligned.apk"
(cd "$BUILD/dex" && zip -q -X "$BUILD/apk/unaligned.apk" classes.dex)

KS="$BUILD/debug.keystore"
if [ ! -f "$KS" ]; then
  echo "🔑 minting a debug key"
  keytool -genkeypair -noprompt -keystore "$KS" -storepass android -keypass android \
    -alias ouija -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=RIOT AI Ouija, OU=Household Spirits, O=RIOT AI, C=US" >/dev/null 2>&1
fi

"$BT/zipalign" -f -p 4 "$BUILD/apk/unaligned.apk" "$BUILD/ouija.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
  --v1-signing-enabled true --v2-signing-enabled true "$BUILD/ouija.apk"
"$BT/apksigner" verify --print-certs "$BUILD/ouija.apk" | head -3

echo "✅ $BUILD/ouija.apk  ($(du -h "$BUILD/ouija.apk" | cut -f1))"
