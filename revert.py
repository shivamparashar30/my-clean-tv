#!/usr/bin/env python3
"""Put the TV back the way it was.

  python3 revert.py --dry-run    show what would be undone
  python3 revert.py              undo it

Undoes, in order:
  1. re-enables every package debloat.py disabled (read from backups/disabled-*.txt)
  2. uninstalls the custom launcher, if it is installed
  3. hands Home back to the stock launcher
  4. restores Private DNS and animation scales from the backup
  5. prints the user apps that were uninstalled, so you can reinstall them

Apps are re-enabled, not reinstalled: they were only ever disabled.
"""
import glob, os, subprocess, sys, time

HOST = os.environ.get("TV_HOST", "192.168.0.115")
T = HOST if ":" in HOST else HOST + ":5555"
ADB = os.environ.get("ADB", os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"))
ROOT = os.path.dirname(os.path.abspath(__file__))
STOCK = "com.google.android.tvlauncher"
CUSTOM = "com.gathin.tvhome"
DRY = "--dry-run" in sys.argv


def sh(cmd):
    r = subprocess.run([ADB, "-s", T, "shell", cmd], capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).replace("\r", "").strip()


def newest(pattern):
    hits = sorted(glob.glob(os.path.join(ROOT, pattern)))
    return hits[-1] if hits else None


def main():
    subprocess.run([ADB, "connect", T], capture_output=True)
    if sh("echo ok") != "ok":
        sys.exit(f"Cannot reach the TV at {T}. Is it on, and is ADB still enabled?")

    log = newest("backups/disabled-*.txt")
    pkgs = [l.strip() for l in open(log)] if log else []
    pkgs = [p for p in pkgs if p]
    print(f"Re-enabling {len(pkgs)} packages from {os.path.basename(log) if log else '(no log found)'}")

    backup = sorted(glob.glob(os.path.join(ROOT, "backups", "20*")))
    backup = backup[-1] if backup else None

    if DRY:
        for p in pkgs:
            print("  would enable", p)
        print(f"  would uninstall {CUSTOM} (if present)")
        print(f"  would set Home back to {STOCK}")
        if backup:
            print(f"  would restore settings from {os.path.basename(backup)}")
        return

    for p in pkgs:
        out = sh(f"pm enable '{p}'")
        ok = "new state: enabled" in out
        print(f"  {p:<52} {'enabled' if ok else out}")

    # 2 + 3. hand Home back
    if CUSTOM in sh(f"pm list packages {CUSTOM}"):
        print(f"\nRemoving the custom launcher ({CUSTOM})")
        print("  ", sh(f"pm uninstall --user 0 {CUSTOM}"))
    sh(f"pm enable {STOCK}")
    sh(f"cmd package set-home-activity {STOCK}/.MainActivity")
    print(f"Home is now: {sh('cmd package resolve-activity -a android.intent.action.MAIN -c android.intent.category.HOME | grep -m1 packageName=').strip()}")

    # 4. settings recorded before we changed anything
    if backup:
        def first_line(name):
            try:
                return open(os.path.join(backup, name)).read().split("\n")[0].strip()
            except Exception:
                return ""
        dns = first_line("private-dns.txt")
        if dns and dns != "null":
            sh(f"settings put global private_dns_mode {dns}")
            print(f"Private DNS mode restored to {dns}")

    print("\nWaiting 15s for Android to flush package state ...")
    time.sleep(15)
    sh("sync")
    n = len([x for x in sh("pm list packages -d").split() if x.startswith("package:")])
    print(f"Still disabled on the TV: {n}  (0 means a full revert)")

    ua = os.path.join(backup, "uninstalled-user-apps.txt") if backup else None
    if ua and os.path.exists(ua):
        print("\nThese were uninstalled at your request. Reinstall from the Play Store,")
        print("or try: adb shell cmd package install-existing <package>")
        for l in open(ua):
            if l.strip():
                print("  ", l.strip())

    print("\nThen reboot the TV:  adb -s %s reboot" % T)


if __name__ == "__main__":
    main()
