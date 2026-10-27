#!/usr/bin/env python3
"""tvctl - drive an Android TV / Google TV from this laptop over ADB on Wi-Fi.

  ./tv find                 look for the TV on this network
  ./tv connect <ip>         pair over ADB (port 5555), remembered afterwards
  ./tv probe                model, Android version, RAM, current app
  ./tv remote               open the web remote in the browser  <- the main one
  ./tv mirror               show the TV on this laptop (scrcpy), mouse + keyboard
  ./tv key UP OK BACK       send remote keys
  ./tv type "stranger"      type into whatever box is focused on the TV
  ./tv apps                 list the TV's apps
  ./tv open netflix         launch an app by name or package
  ./tv shot out.png         screenshot the TV
  ./tv off                  close the ADB port on the TV when you are done
"""

import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, ".tv-state.json")
PORT = 8787

KEYS = {
    "UP": 19, "DOWN": 20, "LEFT": 21, "RIGHT": 22, "OK": 23, "ENTER": 23,
    "BACK": 4, "HOME": 3, "MENU": 82, "SEARCH": 84, "SETTINGS": 176,
    "VOLUP": 24, "VOLDOWN": 25, "MUTE": 164,
    "POWER": 26, "SLEEP": 223, "WAKE": 224,
    "PLAY": 85, "PAUSE": 85, "STOP": 86, "NEXT": 87, "PREV": 88,
    "FF": 90, "REW": 89, "INPUT": 178, "GUIDE": 172, "INFO": 165,
    "CAPTIONS": 175, "NOTIFICATIONS": 83, "DEL": 67, "ESCAPE": 111,
}


def adb_bin():
    for c in (shutil.which("adb"),
              os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
              "/opt/homebrew/bin/adb"):
        if c and os.path.exists(c):
            return c
    sys.exit("adb not found. Install it with: brew install --cask android-platform-tools")


ADB = adb_bin()


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(d):
    with open(STATE, "w") as f:
        json.dump(d, f, indent=2)


def target():
    """The TV's adb serial, e.g. 192.168.1.50:5555."""
    host = os.environ.get("TV_HOST") or load_state().get("host")
    if not host:
        sys.exit("No TV yet. Run:  ./tv find    then  ./tv connect <ip>")
    return host if ":" in host else host + ":5555"


class Shell:
    """One long-lived `adb shell` so a keypress costs ~5ms, not ~200ms."""

    def __init__(self, serial):
        self.serial = serial
        self.lock = threading.Lock()
        self.p = None
        self.n = 0

    def _spawn(self):
        self.p = subprocess.Popen(
            [ADB, "-s", self.serial, "shell"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1)

    def run(self, cmd, want_output=True):
        with self.lock:
            for attempt in (1, 2):
                if self.p is None or self.p.poll() is not None:
                    try:
                        self._spawn()
                    except Exception as e:
                        return f"ERROR {e}"
                self.n += 1
                mark = f"__TVCTL_{self.n}__"
                try:
                    self.p.stdin.write(f"{cmd}\necho {mark}\n")
                    self.p.stdin.flush()
                except Exception:
                    self.p = None
                    continue
                out = []
                while True:
                    line = self.p.stdout.readline()
                    if line == "":          # shell died
                        self.p = None
                        break
                    if mark in line:
                        return "".join(out).strip()
                    if want_output:
                        out.append(line)
                if attempt == 2:
                    return "ERROR shell closed"
        return ""


_shell = None


def sh(cmd, want_output=True):
    global _shell
    if _shell is None:
        _shell = Shell(target())
    return _shell.run(cmd, want_output)


def adb(*args, check=False, timeout=60):
    r = subprocess.run([ADB, *args], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        sys.exit((r.stderr or r.stdout).strip())
    return (r.stdout + r.stderr).strip()


# ---------------------------------------------------------------- discovery

def port_open(ip, port=5555, timeout=0.4):
    try:
        with socket.create_connection((ip, port), timeout):
            return True
    except Exception:
        return False


def my_subnet():
    r = subprocess.run(["ipconfig", "getifaddr", "en0"], capture_output=True, text=True)
    ip = r.stdout.strip()
    if not ip:
        for iface in ("en1", "en2", "en3", "en4"):
            ip = subprocess.run(["ipconfig", "getifaddr", iface],
                                capture_output=True, text=True).stdout.strip()
            if ip:
                break
    return ip


def cmd_find():
    ip = my_subnet()
    if not ip:
        sys.exit("This Mac has no network address. Join your home Wi-Fi first.")
    base = ip.rsplit(".", 1)[0]
    print(f"This Mac: {ip}   scanning {base}.1-254 for ADB on port 5555 ...")

    found, lock = [], threading.Lock()

    def probe(n):
        host = f"{base}.{n}"
        if host != ip and port_open(host, 5555):
            with lock:
                found.append(host)

    ts = [threading.Thread(target=probe, args=(n,)) for n in range(1, 255)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    if found:
        print("\nADB is open on:")
        for h in found:
            print(f"   {h}      ->  ./tv connect {h}")
    else:
        print("\nNothing answering on 5555.")
        print("On the TV: Settings > Device Preferences > About > press OK on 'Build' 7 times,")
        print("then back > Developer options > turn on USB debugging AND Network/ADB debugging.")
        print("Then run this again. Also check this Mac is on the same Wi-Fi as the TV.")

    print("\nOther devices visible on this network:")
    subprocess.run(f"arp -a -n | grep -v incomplete | grep -v 'ff:ff:ff' | grep -v '1:0:5e'",
                   shell=True)


def cmd_connect(ip):
    host = ip if ":" in ip else ip + ":5555"
    bare = host.split(":")[0]
    if not port_open(bare, int(host.split(":")[1])):
        print(f"Port {host.split(':')[1]} is closed on {bare}.")
        print("Turn on Developer options > Network/ADB debugging on the TV, then retry.")
    print(adb("connect", host))
    print("\nIf the TV shows 'Allow USB debugging?', accept it (tick 'Always allow'), then run ./tv probe")
    s = load_state()
    s["host"] = host
    save_state(s)


def cmd_probe():
    t = target()
    print(adb("connect", t))
    props = sh("getprop ro.product.model; getprop ro.product.manufacturer; "
               "getprop ro.build.version.release; getprop ro.build.version.sdk")
    lines = [l for l in props.splitlines() if l.strip()]
    labels = ["Model", "Make", "Android", "SDK"]
    for lab, val in zip(labels, lines):
        print(f"{lab:>10}: {val}")
    mem = sh("cat /proc/meminfo | head -2")
    for l in mem.splitlines():
        print(f"{'RAM':>10}: {l.strip()}")
    res = sh("wm size; wm density")
    for l in res.splitlines():
        print(f"{'Display':>10}: {l.strip()}")
    cur = sh("dumpsys activity activities | grep -m1 -E 'mResumedActivity|topResumedActivity'")
    print(f"{'On screen':>10}: {cur.strip()[:110]}")
    n = sh("pm list packages | wc -l").strip()
    d = sh("pm list packages -d | wc -l").strip()
    print(f"{'Packages':>10}: {n} installed, {d} already disabled")


# ---------------------------------------------------------------- actions

def send_key(name):
    code = KEYS.get(name.upper())
    if code is None:
        if name.upper().startswith("KEYCODE_") or name.isdigit():
            code = name
        else:
            return f"unknown key {name}"
    sh(f"input keyevent {code}", want_output=False)
    return "ok"


def send_text(txt):
    # adb's `input text` wants %s for spaces and no shell metacharacters
    safe = txt.replace("%", "%%").replace(" ", "%s")
    sh("input text " + shlex.quote(safe), want_output=False)
    return "ok"


_app_cache = {"t": 0, "v": []}


def list_apps(force=False):
    """Apps with a TV (leanback) home-screen entry, excluding disabled ones."""
    if not force and time.time() - _app_cache["t"] < 60 and _app_cache["v"]:
        return _app_cache["v"]

    raw = sh("cmd package query-activities -a android.intent.action.MAIN "
             "-c android.intent.category.LEANBACK_LAUNCHER 2>/dev/null | grep packageName=")
    if raw.startswith("ERROR"):
        return []

    # The output is verbose dumpsys style; the package appears as `packageName=<pkg>`
    # at both ActivityInfo and ApplicationInfo level, so dedupe.
    pkgs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("packageName="):
            continue
        pkg = line[len("packageName="):].strip()
        if pkg and "." in pkg and pkg not in pkgs:
            pkgs.append(pkg)

    if not pkgs:
        return []

    # A disabled package still has its activity listed; drop those.
    enabled = sh("pm list packages -e")
    if not enabled.startswith("ERROR"):
        live = {l[len("package:"):].strip() for l in enabled.splitlines()
                if l.startswith("package:")}
        pkgs = [p for p in pkgs if p in live]

    apps = [{"pkg": p, "name": pretty(p)} for p in pkgs]
    apps.sort(key=lambda a: a["name"].lower())
    _app_cache.update(t=time.time(), v=apps)
    return apps


NICE = {
    "com.netflix.ninja": "Netflix", "com.netflix.mediaclient": "Netflix",
    "com.amazon.amazonvideo.livingroom": "Prime Video",
    "com.amazon.avod.thirdpartyclient": "Prime Video",
    "com.google.android.youtube.tv": "YouTube", "com.google.android.youtube.tvunplugged": "YouTube TV",
    "in.startv.hotstar": "JioHotstar", "in.startv.hotstar.dplus.tv": "JioHotstar",
    "com.jio.jioplay.tv": "JioTV", "com.graymatrix.did": "ZEE5",
    "com.sonyliv": "SonyLIV", "com.apple.atve.androidtv.appletv": "Apple TV",
    "com.spotify.tv.android": "Spotify", "com.plexapp.android": "Plex",
    "org.jellyfin.androidtv": "Jellyfin", "com.google.android.tvlauncher": "Google TV Home",
    "com.google.android.apps.tv.launcherx": "Google TV Home",
    "com.mitv.tvhome": "PatchWall", "com.xiaomi.mitv.smartshare": "Mi Screen Mirroring",
    "com.android.tv.settings": "Settings", "com.google.android.katniss": "Google Assistant",
    "com.android.vending": "Play Store", "com.android.tv": "Live TV",
    "com.ionitech.airscreen": "AirScreen", "com.apowersoft.mirror.tv": "ApowerMirror",
    "de.twokit.castbrowsernexusplayer": "Cast Browser", "nextapp.fx": "FX Files",
    "com.yablio.sendfilestotv": "Send Files to TV", "com.mxtech.videoplayer.television": "MX Player",
    "com.jio.media.stb.ondemand": "JioCinema", "com.jio.media.stb.ondemand.xiaomi": "JioCinema (Mi)",
    "com.xiaomi.mitv.mediaexplorer": "Media Explorer",
    "com.google.android.apps.nbu.smartconnect.tv": "Smart Connect",
    "com.gathin.tvhome": "Home",
}


def pretty(pkg):
    if pkg in NICE:
        return NICE[pkg]
    tail = pkg.split(".")[-1]
    if tail in ("tv", "android", "androidtv", "client", "app"):
        parts = pkg.split(".")
        tail = parts[-2] if len(parts) > 1 else tail
    return re.sub(r"(?<!^)(?=[A-Z])", " ", tail).replace("_", " ").title()


def open_app(q):
    q = q.strip()
    apps = list_apps()
    pkg = None
    if "." in q and any(a["pkg"] == q for a in apps):
        pkg = q
    else:
        for a in apps:
            if a["name"].lower() == q.lower():
                pkg = a["pkg"]
                break
        if not pkg:
            for a in apps:
                if q.lower() in a["name"].lower() or q.lower() in a["pkg"].lower():
                    pkg = a["pkg"]
                    break
    if not pkg:
        pkg = q
    sh(f"monkey -p {shlex.quote(pkg)} -c android.intent.category.LEANBACK_LAUNCHER 1 "
       f">/dev/null 2>&1 || monkey -p {shlex.quote(pkg)} -c android.intent.category.LAUNCHER 1 "
       f">/dev/null 2>&1", want_output=False)
    return pkg


def open_url(url):
    sh(f"am start -a android.intent.action.VIEW -d {shlex.quote(url)}", want_output=False)
    return "ok"


def screenshot(path):
    sh("screencap -p /sdcard/__tvctl.png", want_output=False)
    adb("-s", target(), "pull", "/sdcard/__tvctl.png", path)
    sh("rm -f /sdcard/__tvctl.png", want_output=False)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    if size == 0:
        print("Empty screenshot - Netflix, Live TV and HDMI inputs block capture. "
              "That is the TV protecting the content, not a fault.")
    return size


_size = {"w": 1920, "h": 1080, "read": False}


def screen_size():
    """The TV's resolution, read once, used to map pad coords to the screen."""
    if not _size["read"]:
        out = sh("wm size")
        m = re.search(r"(\d+)x(\d+)", out or "")
        if m:
            _size["w"], _size["h"] = int(m.group(1)), int(m.group(2))
        _size["read"] = True
    return _size["w"], _size["h"]


def tap(nx, ny):
    """Tap at normalised coords (0..1) of the TV screen."""
    w, h = screen_size()
    x, y = int(max(0.0, min(1.0, nx)) * w), int(max(0.0, min(1.0, ny)) * h)
    sh(f"input tap {x} {y}", want_output=False)
    return x, y


def swipe(nx1, ny1, nx2, ny2, ms=200):
    w, h = screen_size()
    c = lambda v, m: int(max(0.0, min(1.0, v)) * m)
    sh(f"input swipe {c(nx1,w)} {c(ny1,h)} {c(nx2,w)} {c(ny2,h)} {int(ms)}",
       want_output=False)
    return "ok"


# PNG encoding on this TV costs ~1.2s (CPU-bound, 1920x1080). That is the floor for
# screencap, so instead of making the browser wait for one, a background thread captures
# continuously and every request is answered instantly from the newest frame.
_frame = {"t": 0.0, "png": b"", "blocked": False, "n": 0}
_frame_lock = threading.Lock()
_want_live = {"until": 0.0}
_grabber_started = False


def _capture_once():
    try:
        r = subprocess.run([ADB, "-s", target(), "exec-out", "screencap", "-p"],
                           capture_output=True, timeout=20)
        return r.stdout
    except Exception:
        return b""


def _grabber():
    """Captures while a browser is asking for frames, then idles."""
    while True:
        if time.time() > _want_live["until"]:
            time.sleep(0.25)
            continue
        png = _capture_once()
        with _frame_lock:
            if png[:4] == b"\x89PNG" and len(png) > 1000:
                _frame.update(t=time.time(), png=png, blocked=False, n=_frame["n"] + 1)
            else:
                # 0 bytes means the app on screen forbids capture (Netflix, Prime, HDMI).
                _frame.update(t=time.time(), blocked=True)


def start_grabber():
    global _grabber_started
    if not _grabber_started:
        threading.Thread(target=_grabber, daemon=True).start()
        _grabber_started = True


def keep_live(seconds=8.0):
    _want_live["until"] = time.time() + seconds


def grab_screen(max_age=0.8):
    """Newest frame, captured on demand if the grabber has nothing recent."""
    start_grabber()
    with _frame_lock:
        fresh = time.time() - _frame["t"] < max_age and _frame["png"]
        if fresh:
            return _frame["png"]
    png = _capture_once()
    with _frame_lock:
        if png[:4] == b"\x89PNG" and len(png) > 1000:
            _frame.update(t=time.time(), png=png, blocked=False, n=_frame["n"] + 1)
        else:
            _frame.update(t=time.time(), blocked=True)
        return _frame["png"]


_app_cache2 = {"t": 0.0, "v": "-"}


def current_app(max_age=4.0):
    if time.time() - _app_cache2["t"] < max_age:
        return _app_cache2["v"]
    cur = sh("dumpsys activity activities | grep -m1 -E "
             "'mResumedActivity|topResumedActivity'")
    m = re.search(r"([a-zA-Z0-9_.]+)/", cur or "")
    _app_cache2.update(t=time.time(), v=pretty(m.group(1)) if m else "-")
    return _app_cache2["v"]


def frame_info():
    with _frame_lock:
        return {"age": round(time.time() - _frame["t"], 2) if _frame["t"] else None,
                "blocked": _frame["blocked"], "n": _frame["n"],
                "have": bool(_frame["png"])}


def cmd_mirror(extra):
    if not shutil.which("scrcpy"):
        sys.exit("scrcpy not installed. Run: brew install scrcpy")
    print("Opening the TV on this laptop. Mouse clicks and your keyboard drive it. Close the window to stop.")
    os.execvp("scrcpy", ["scrcpy", "-s", target(), "--window-title=TV",
                         "--stay-awake", "--keyboard=uhid", *extra])


def cmd_off():
    print("Closing network ADB on the TV ...")
    sh("settings put global adb_wifi_enabled 0", want_output=False)
    sh("setprop service.adb.tcp.port -1", want_output=False)
    print(adb("disconnect", target()))
    print("Also switch USB debugging off on the TV: Settings > Device Preferences >")
    print("Developer options > USB debugging, and 'Revoke USB debugging authorisations'.")


# ---------------------------------------------------------------- web remote

def cmd_remote():
    import socketserver
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    t = target()
    ui = open(os.path.join(HERE, "ui.html"), "rb").read()
    threading.Thread(target=lambda: adb("connect", t), daemon=True).start()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(ui, "text/html; charset=utf-8")
            if self.path == "/apps":
                return self._send(list_apps())
            if self.path.startswith("/screen.png"):
                start_grabber()
                keep_live()
                png = grab_screen(max_age=30.0)
                if not png:
                    self.send_error(503, "no frame")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if self.path == "/frame":
                start_grabber()
                keep_live()
                info = frame_info()
                info["app"] = current_app()
                return self._send(info)
            if self.path == "/size":
                w, h = screen_size()
                return self._send({"w": w, "h": h})
            if self.path == "/status":
                cur = sh("dumpsys activity activities | grep -m1 -E "
                         "'mResumedActivity|topResumedActivity'")
                m = re.search(r"([a-zA-Z0-9_.]+)/", cur or "")
                return self._send({"ok": "ERROR" not in (cur or ""),
                                   "app": pretty(m.group(1)) if m else "-",
                                   "host": t})
            self.send_error(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            p = self.path
            if p == "/key":
                return self._send({"r": send_key(data.get("key", ""))})
            if p == "/text":
                return self._send({"r": send_text(data.get("text", ""))})
            if p == "/open":
                return self._send({"r": open_app(data.get("app", ""))})
            if p == "/url":
                return self._send({"r": open_url(data.get("url", ""))})
            if p == "/tap":
                x, y = tap(float(data.get("x", 0)), float(data.get("y", 0)))
                return self._send({"r": "ok", "x": x, "y": y})
            if p == "/swipe":
                return self._send({"r": swipe(float(data.get("x1", 0)), float(data.get("y1", 0)),
                                              float(data.get("x2", 0)), float(data.get("y2", 0)),
                                              data.get("ms", 200))})
            if p == "/mirror":
                subprocess.Popen(["scrcpy", "-s", t, "--window-title=TV",
                                  "--stay-awake", "--keyboard=uhid"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return self._send({"r": "ok"})
            self.send_error(404)

    class Srv(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

        def server_bind(self):
            # Skip HTTPServer's socket.getfqdn(): on a network with no reverse
            # DNS it blocks for ~30s before the page is ever served.
            socketserver.TCPServer.server_bind(self)
            self.server_name = "localhost"
            self.server_port = self.server_address[1]

    srv = Srv(("127.0.0.1", PORT), H)
    url = f"http://localhost:{PORT}"
    print(f"Remote running at {url}   (TV: {t})")
    print("Arrow keys / Enter / Backspace / H / +- work from your keyboard. Ctrl-C to stop.")
    subprocess.Popen(["open", url])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


# ---------------------------------------------------------------- cli

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    c = a[0]
    if c == "find":
        cmd_find()
    elif c == "connect":
        cmd_connect(a[1] if len(a) > 1 else sys.exit("usage: ./tv connect <ip>"))
    elif c == "probe":
        cmd_probe()
    elif c == "remote":
        cmd_remote()
    elif c == "mirror":
        cmd_mirror(a[1:])
    elif c == "key":
        for k in a[1:]:
            print(k, send_key(k))
    elif c == "type":
        print(send_text(" ".join(a[1:])))
    elif c == "apps":
        for app in list_apps(force=True):
            print(f"{app['name']:<28} {app['pkg']}")
    elif c == "open":
        print("launched", open_app(" ".join(a[1:])))
    elif c == "url":
        print(open_url(a[1]))
    elif c == "shot":
        path = a[1] if len(a) > 1 else "tv.png"
        print(f"{screenshot(path)} bytes -> {path}")
    elif c == "shell":
        print(sh(" ".join(a[1:])))
    elif c == "off":
        cmd_off()
    else:
        sys.exit(f"unknown command '{c}'. Run ./tv help")


if __name__ == "__main__":
    main()
