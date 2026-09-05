# OUIJA — Android

A real, sideloadable APK. The board lives in `assets/`, runs entirely from
`file:///android_asset/ouija.html`, and answers from its own local oracle — so
the app works with the radio off, on a plane, in a basement.

Point it at a RIOT AI server with **⚙ LINK** (e.g. `http://192.168.1.42:5001`)
and the spirits start speaking through the model instead. Leave it blank and
nothing ever leaves the phone.

## What's in the app

- Fullscreen, edge to edge, screen stays awake — a seance shouldn't time out.
- **Haptics**: the phone knocks in your hand every time the planchette lands on
  a letter, taps through the opening ritual, and thumps once for the dinner bell.
- Fonts are baked into the page as data URIs; no network at seance time.
- Two permissions: `VIBRATE`, and `INTERNET` — the latter used only when a
  server is linked.

## Build

Needs a JDK and an Android SDK with build-tools and a platform installed
(`sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"`).

```sh
ANDROID_HOME=/path/to/android-sdk ./android/build.sh
# → android/build/ouija.apk   (debug-signed, ~476 KB)
```

No Gradle and no Android Gradle Plugin: the script drives `aapt2`, `javac`,
`d8`, `zipalign` and `apksigner` directly, so there is nothing to resolve from a
maven repo at build time. `build_assets.py` regenerates the bundled page from
`templates/ouija.html`, so the app and the web board never drift apart.

Two constraints worth knowing if you touch the Java: every class is top-level
and no `R.java` is generated. The `d8` in build-tools 34 fails on nested class
names, and the app reaches its resources only through the manifest, so staying
flat costs nothing.

## Install

```sh
adb install -r android/build/ouija.apk
```

Or copy the APK to the phone and open it — Android will ask you to allow
installs from that source. It is **debug-signed**, so it will not update over a
Play Store copy, and Play Protect may warn about an unknown developer.

Always say goodbye.
