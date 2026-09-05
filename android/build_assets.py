#!/usr/bin/env python3
"""
Turn templates/ouija.html into the standalone board that ships inside the APK.

The app has no server of its own: the board runs entirely from file:///android_asset,
answers from its local oracle, and only reaches the network if you point it at a
RIOT AI box under ⚙ LINK.
"""

import base64
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "build" / "assets"
CACHE = Path(__file__).resolve().parent / "build" / "fontcache"
FONT_CSS = ("https://fonts.googleapis.com/css2?family=Pirata+One"
            "&family=IM+Fell+English:ital@0;1&family=Roboto+Mono:wght@400;700&display=swap")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}


def get(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def embedded_fonts() -> str:
    """Bake the webfonts into the page. No network at seance time."""
    CACHE.mkdir(parents=True, exist_ok=True)
    css_file = CACHE / "fonts.css"
    try:
        if not css_file.exists():
            css_file.write_bytes(get(FONT_CSS))
        css = css_file.read_text()
    except Exception as e:
        print(f"⚠️  fonts unreachable ({e}); falling back to system faces")
        return ""

    def inline(m):
        url = m.group(1)
        name = url.rsplit("/", 1)[-1]
        blob = CACHE / name
        try:
            if not blob.exists():
                blob.write_bytes(get(url))
        except Exception as e:
            print(f"⚠️  could not fetch {name}: {e}")
            return m.group(0)
        fmt = "woff2" if name.endswith(".woff2") else "truetype"
        mime = "font/woff2" if name.endswith(".woff2") else "font/ttf"
        b64 = base64.b64encode(blob.read_bytes()).decode()
        return f"url(data:{mime};base64,{b64}) format('{fmt}')"

    css = re.sub(r"url\((https://fonts\.gstatic\.com/[^)]+)\)\s*format\('[^']+'\)", inline, css)
    # only keep faces that actually got embedded
    faces = [b for b in re.findall(r"@font-face\s*\{[^}]*\}", css) if "base64," in b]
    print(f"   embedded {len(faces)} font faces")
    return "\n".join(faces)


def render() -> str:
    from jinja2 import Environment, FileSystemLoader
    sys.path.insert(0, str(ROOT))
    from ouija import SPIRITS
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
    return env.get_template("ouija.html").render(config={}, spirits=SPIRITS)


def patch(html: str, fonts: str) -> str:
    # 1. fonts: swap the Google import for embedded faces
    html = html.replace(
        "@import url('https://fonts.googleapis.com/css2?family=Permanent+Marker&family=Roboto+Mono:wght@400;700&display=swap');", "")
    html = re.sub(r"@import url\('https://fonts\.googleapis\.com[^']*'\);", "", html)
    html = html.replace("<style>", "<style>\n" + fonts, 1)

    # 2. no manifest, no service worker, no icons over http — this is a file:// app
    html = re.sub(r'<link rel="manifest"[^>]*>\n?', "", html)
    html = re.sub(r'<link rel="(icon|apple-touch-icon)"[^>]*>\n?', "", html)
    html = re.sub(r"if \('serviceWorker' in navigator\) \{.*?\.catch\(err => console\.warn\('the worker would not stay:', err\)\)\);\n\}",
                  "", html, flags=re.S)

    # 3. the header: no web page to go back to. offer the link to a RIOT AI box instead.
    html = html.replace('<a class="back" href="/">← BACK TO THE LIVING</a>',
                        '<button id="link" class="back" style="cursor:pointer;">⚙ LINK</button>')
    html = html.replace('<button id="install" class="back" hidden style="cursor:pointer;">⤓ INSTALL BOARD</button>', '')
    html = html.replace('<span id="offline" class="back" hidden style="border-color:#7a2b12; color:#ff8c42;">NO SIGNAL</span>',
                        '<span id="offline" class="back" style="border-color:#7a2b12; color:#ff8c42;">LOCAL SPIRITS</span>')

    # 4. install/online plumbing has no meaning here; swap in the LINK dialog and haptics
    old = html[html.index("/* ── install it."):html.index("/* the planchette can be pushed around")]
    new = """/* ── the board can be pointed at a RIOT AI box on your network ─────── */
const OFFLINE = document.getElementById('offline');
const LINK = document.getElementById('link');
let SERVER = localStorage.getItem('ouija.server') || '';
function markSource(){
  OFFLINE.textContent = SERVER ? 'LINKED' : 'LOCAL SPIRITS';
  OFFLINE.style.borderColor = SERVER ? '#2a5c2a' : '#7a2b12';
  OFFLINE.style.color = SERVER ? '#7fd97f' : '#ff8c42';
}
markSource();
LINK.onclick = () => {
  const v = prompt('RIOT AI server (blank = local spirits only)\\ne.g. http://192.168.1.42:5001', SERVER);
  if (v === null) return;
  SERVER = v.trim().replace(/\\/$/, '');
  localStorage.setItem('ouija.server', SERVER);
  markSource(); knock();
};

/* the phone knocks back — haptics through the Android bridge */
function haptic(ms){ try { if (window.Board) Board.knock(ms); } catch(_){} }

"""
    html = html.replace(old, new)

    # 5. asking: only reach out when a box is linked, otherwise the local oracle answers
    html = html.replace("""  let data;
  try {
    const res = await fetch('/api/ouija/ask', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ question, spirit, dinner: !!isDinner })
    });
    data = await res.json();
  } catch(e) {
    data = offlineOracle();   // no signal. they're still in the walls.
  }""",
"""  let data;
  if (SERVER) {
    try {
      const res = await fetch(SERVER + '/api/ouija/ask', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ question, spirit, dinner: !!isDinner })
      });
      data = await res.json();
    } catch(e) {
      data = offlineOracle();   // the box didn't answer. they're still in the walls.
    }
  } else {
    await wait(900 + Math.random() * 900);   // it takes them a moment
    data = offlineOracle();
  }""")

    # 6. every landing knocks in your hand
    html = html.replace("  el.classList.add('lit'); knock();",
                        "  el.classList.add('lit'); knock(); haptic(18);")
    html = html.replace("  startDrone(); bell();\n  BOARD.classList.add('summoned');",
                        "  startDrone(); bell(); haptic(140);\n  BOARD.classList.add('summoned');")
    html = html.replace("    if (p % 26 < 3) knock();", "    if (p % 26 < 3) { knock(); haptic(12); }")
    return html


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("🕯️  building the bundled board")
    html = patch(render(), embedded_fonts())
    (OUT / "ouija.html").write_text(html)
    kb = len(html.encode()) / 1024
    print(f"   assets/ouija.html — {kb:.0f} KB")
    for leftover in ("serviceWorker", "manifest.webmanifest", "beforeinstallprompt"):
        if leftover in html:
            print(f"⚠️  {leftover} still present in the bundled page")


if __name__ == "__main__":
    main()
