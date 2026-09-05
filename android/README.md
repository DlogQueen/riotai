# In the Raw — Android

Social media for actual life, as an installable app. Black chrome, state-coloured
cards, oversized display type, real photos with no filters on them.

**`InTheRaw.apk`** (committed; `build/InTheRaw.apk` is the fresh build output) —
install with `adb install -r InTheRaw.apk`, or copy it to a phone and open it
(allow "install from unknown sources" first; it is signed with a local key, not
a Play Store one).

## What works

Sign up, sign in, a full profile with a **profile picture**, posting with a
required state and an optional **photo**, reactions, comments, following, the
people mosaic and the chronological feed — all offline, all persisted on device.

The rules are enforced here exactly as on the server:

- every post names one of nine states, none of which is "living my best life"
- reactions instead of likes — *been there, i see you, holding this, proud of you, same*
- reaction counts render only for the author of the post; nobody else gets a number
- follower counts render only for the profile's owner
- the feed is sorted by time and nothing else
- posts can be deleted, never edited
- your profile's current state follows your last post automatically

## Photos

Pictures go through the system photo picker (`<input type="file">` handled by
`WebChromeClient.onShowFileChooser`). Every image is downscaled on the way in —
512px for avatars, 1280px for post photos, JPEG quality 0.72 — because a 12MP
camera file is not storable otherwise. **No filters and no adjustments are
offered, deliberately.**

Photo blobs live in IndexedDB; the data model only holds an id. Base64 in
`localStorage` would exhaust the ~5MB quota after a handful of posts.

## No third-party sign-in

There are no Google / Apple / Facebook buttons. There used to be four of them
and they did nothing, which was worse than not having them. Beyond that: signing
in through an identity provider tells that provider you have an account here,
and this is not a place that should report back to anyone. Accounts are local.

## How it is built

A single Activity hosting a WebView over a self-contained bundle in
`app/src/main/assets/www` (HTML, CSS and JS; no frameworks, no CDN).

**The app declares no permissions at all** — no `INTERNET`, no storage, no
camera. Nothing written in it, photos included, can leave the phone.

```bash
export ANDROID_HOME=/path/to/android-sdk    # platform 34 + build-tools 35.0.0
./build.sh
```

`build.sh` runs `aapt2 → javac → d8 → zipalign → apksigner` directly. No Gradle,
no third-party dependencies, so the build resolves nothing over the network and
takes a couple of seconds. It generates `raw-keystore.jks` on first run.

### A build-tools trap worth remembering

The `d8` in **build-tools 34.0.0** throws an internal `NullPointerException` on
non-static inner classes and on classes implementing a generic interface such as
`ValueCallback<Uri[]>` — which the file chooser needs. **35.0.0 fixes both**, and
that is why the build pins it. Do not drop back to 34.

## Not done yet

- **No server sync.** Accounts, posts and photos live on the one device; two
  phones share nothing. Connecting it to the Flask app in this repo needs JSON
  endpoints (the server renders HTML today) plus the `INTERNET` permission.
- **No moderation, blocking, or reporting.** This matters more once accounts sync.
- Signed with a generated debug keystore. A Play Store release needs a real
  upload key, and `raw-keystore.jks` must not be reused for that.
