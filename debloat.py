#!/usr/bin/env python3
"""Disable the tested MiTV-AXSO2 package list, in batches, with a brick guard.

Packages are DISABLED for user 0, never uninstalled.  Undo with revert.py.
  python3 debloat.py --dry-run     show exactly what would happen
  python3 debloat.py               do it
"""
import os, re, subprocess, sys, time, datetime

HOST = os.environ.get("TV_HOST", "192.168.0.115")
T = HOST if ":" in HOST else HOST + ":5555"
ADB = os.environ.get("ADB", os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"))
ROOT = os.path.dirname(os.path.abspath(__file__))
LIST = os.path.join(ROOT, "cleanyourtv/examples/xiaomi-mitv-axso2/debloat.txt")
SHOTS = os.path.join(ROOT, "backups", "shots")
DRY = "--dry-run" in sys.argv

# Disabling any of these can stop the TV booting. Mi TV Stick, issue #884.
FORBIDDEN = re.compile(
    r"^(android"
    r"|com\.android\.systemui|com\.android\.shell|com\.android\.phone"
    r"|com\.android\.settings|com\.android\.tv\.settings"
    r"|(?:com\.android|com\.google\.android)\."
    r"(?:permissioncontroller|packageinstaller|ext\.services|ext\.shared|modulemetadata)"
    r"|com\.google\.android\.overlay\.modules.*"
    r"|com\.android\.providers\.(?!calendar|contacts|userdictionary|blockednumber).*"
    r")$")


def sh(cmd):
    r = subprocess.run([ADB, "-s", T, "shell", cmd], capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).replace("\r", "").strip()


def main():
    want = sorted({ln.split("#")[0].strip()
                   for ln in open(LIST) if ln.split("#")[0].strip()})

    print(f"Guard: checking {len(want)} packages against the never-disable list")
    bad = [p for p in want if FORBIDDEN.match(p)]
    if bad:
        print("  REFUSED — these would risk the TV not booting:")
        for p in bad:
            print("   ", p)
        sys.exit(1)
    print("  passed — none are core Android packages\n")

    installed = set(sh("pm list packages").replace("package:", "").split())
    present = [p for p in want if p in installed]
    print(f"{len(present)} of {len(want)} are installed here; {len(want)-len(present)} skipped.\n")

    if DRY:
        print("DRY RUN — would disable:")
        for p in present:
            print("  ", p)
        return

    os.makedirs(SHOTS, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log = os.path.join(ROOT, "backups", f"disabled-{stamp}.txt")
    with open(log, "w") as f:
        f.write("\n".join(present) + "\n")

    batch = 1
    for i, p in enumerate(present, 1):
        out = sh(f"pm disable-user --user 0 '{p}'")
        ok = "new state: disabled" in out
        print(f"  {p:<52} {'disabled' if ok else out}")
        if i % 6 == 0 or i == len(present):
            if sh("echo alive") != "alive":
                print("\n  TV stopped answering. STOPPING — run: python3 revert.py")
                sys.exit(1)
            sh("screencap -p /sdcard/__s.png")
            dest = os.path.join(SHOTS, f"batch-{batch}.png")
            subprocess.run([ADB, "-s", T, "pull", "/sdcard/__s.png", dest],
                           capture_output=True)
            size = os.path.getsize(dest) if os.path.exists(dest) else 0
            print(f"  --- batch {batch}: TV alive, screenshot {size} bytes ---")
            batch += 1

    print("\nWaiting 15s for Android to flush package state to disk ...")
    time.sleep(15)
    sh("sync")
    n = len([x for x in sh("pm list packages -d").split() if x.startswith("package:")])
    print(f"Disabled on the TV now: {n}")
    print(f"Recorded in: {log}")


if __name__ == "__main__":
    main()
