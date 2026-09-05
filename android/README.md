# RAW for Android

The RAW social network as an installable app. Black chrome, state-coloured
cards, oversized display type — the visual language of the reference designs,
carrying RAW's rules.

**`RAW.apk`** (committed; `build/RAW.apk` is the fresh build output) — install with
`adb install -r RAW.apk`, or copy it to
a phone and open it (allow "install from unknown sources" first, since it is
signed with a local debug key rather than a Play Store one).

## What works

Sign up, sign in, edit a full profile, post with a required state, react,
comment, follow, browse the mosaic of people, and the chronological feed —
all offline, all persisted on the device.

The rules are enforced here exactly as on the server:

- every post names one of nine states, none of which is "living my best life"
- reactions instead of likes — *been there, i see you, holding this, proud of you, same*
- reaction counts render only for the author of the post; nobody else gets a number
- follower counts render only for the profile's owner
- the feed is sorted by time and nothing else
- posts can be deleted, never edited
- your profile's current state follows your last post automatically

## How it is built

A single Activity hosting a WebView over a self-contained bundle in
`app/src/main/assets/www` (~35KB of HTML, CSS and JS, no frameworks, no CDN).

**The app declares no `INTERNET` permission.** Nothing written in it can leave
the phone, which is the right default for a place people describe their worst
weeks. That also means it does not yet talk to the Flask server in this repo —
see "Not done yet" below.

```bash
export ANDROID_HOME=/path/to/android-sdk    # needs platform 34 + build-tools 34.0.0
./build.sh
```

`build.sh` runs `aapt2 → javac → d8 → zipalign → apksigner` directly. There is no
Gradle and there are no third-party dependencies, so the build resolves nothing
over the network and takes a couple of seconds. It generates `raw-keystore.jks`
on first run.

### Two build-tools quirks worth remembering

The `d8` in build-tools 34.0.0 throws an internal `NullPointerException` on
**non-static inner classes** and on classes implementing a **generic interface**
(`ValueCallback<String>`). Both are avoided in `MainActivity.java`: the JS bridge
is a static nested class, and the back button is handed to the web layer, which
calls `RawHost.exitApp()` when it has nothing left to pop. Reintroducing either
pattern breaks the build with a stack trace that does not name the cause.

## Not done yet

- **No server sync.** Accounts and posts live in the device's WebView storage
  only; two phones running this app share nothing. Connecting it to the Flask
  app in this repo needs JSON endpoints (the server currently renders HTML) plus
  the `INTERNET` permission — a deliberate next step, not an oversight.
- **No moderation, blocking, or reporting**, same as the web app. This matters
  more once accounts sync between people.
- Text posts only.
- Signed with a generated debug keystore. A Play Store release needs a real
  upload key, and `raw-keystore.jks` must not be reused for that.
