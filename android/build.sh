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

for tool in javac keytool zip unzip sha256sum; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 1; }
done

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
# Keep javac's exit status: `| grep ... || true` would swallow a real compile
# error and let d8 dex whatever stale classes were lying around.
if ! javac -nowarn -source 8 -target 8 -bootclasspath "$JAR" -classpath "$JAR" \
     -d "$OUT/classes" @"$OUT/sources.txt" 2>"$OUT/javac.log"; then
  grep -v 'bootstrap class path\|source value 8\|target value 8\|deprecat' "$OUT/javac.log" >&2 || true
  echo "!! javac failed" >&2
  exit 1
fi
grep -v 'bootstrap class path\|source value 8\|target value 8\|deprecat' "$OUT/javac.log" || true

echo "==> dex"
find "$OUT/classes" -name '*.class' > "$OUT/classes.txt"
"$BT/d8" --min-api 24 --lib "$JAR" --output "$OUT" @"$OUT/classes.txt"

echo "==> package"
cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT" && zip -q unsigned.apk classes.dex)

# The keystore is gitignored, so a fresh clone has none. Minting one silently
# would produce an APK signed by a different key: installing it over an existing
# copy fails with INSTALL_FAILED_UPDATE_INCOMPATIBLE, and the only way through is
# uninstalling, which destroys every post and photo on that phone. So say so.
STOREPASS="${RAW_KEYSTORE_PASS:-rawrawraw}"
if [ ! -f raw-keystore.jks ]; then
  echo "==> no raw-keystore.jks found - generating a new signing key"
  echo "    WARNING: an APK signed with this key CANNOT update an install signed"
  echo "    with a different one. Anyone already running the app must uninstall"
  echo "    first, losing their local posts and photos. Keep this keystore safe,"
  echo "    and back it up before you ever hand the app to someone else."
  if [ -t 0 ] && [ -z "${RAW_KEYSTORE_YES:-}" ]; then
    read -r -p "    Generate one now? [y/N] " reply
    case "$reply" in [yY]*) ;; *) echo "aborted"; exit 1 ;; esac
  fi
  keytool -genkeypair -keystore raw-keystore.jks -alias intheraw -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass "$STOREPASS" -keypass "$STOREPASS" \
    -dname "CN=In the Raw, OU=riotai, O=In the Raw, L=, S=, C=US" >/dev/null 2>&1
fi

"$BT/zipalign" -f 4 "$OUT/unsigned.apk" "$OUT/InTheRaw.apk"
"$BT/apksigner" sign --ks raw-keystore.jks --ks-pass "pass:$STOREPASS" --key-pass "pass:$STOREPASS" \
  --v1-signing-enabled true --v2-signing-enabled true "$OUT/InTheRaw.apk"
"$BT/apksigner" verify "$OUT/InTheRaw.apk" && echo "==> signature OK"

# Copy to the tracked path in the same breath, so the committed APK cannot lag
# behind the build output.
cp "$OUT/InTheRaw.apk" InTheRaw.apk

echo "==> assets in the APK match the working tree?"
for f in index.html app.css app.js; do
  a=$(unzip -p InTheRaw.apk "assets/www/$f" | sha256sum | cut -d" " -f1)
  b=$(sha256sum "$SRC/assets/www/$f" | cut -d" " -f1)
  if [ "$a" = "$b" ]; then echo "    $f OK"; else echo "    $f STALE"; exit 1; fi
done

ls -lh InTheRaw.apk
