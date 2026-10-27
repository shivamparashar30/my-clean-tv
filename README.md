# Mi TV project — MiTV-AXSO2 (dangalUHD, Android 9)

TV: `192.168.0.115`  ·  Mac: `192.168.0.116`

| Folder / file | What it is |
|---|---|
| `laptop-remote/` | Your Mac as a remote, and the TV's screen on your Mac. **Working.** |
| `cleanyourtv/` | The debloat + launcher project (Gathin23, MIT). |
| `backup-tv.sh` | Records the TV's full state. Run before any change. |
| `debloat.py` | Disables the tested package list, in batches, with a brick guard. **Done.** |
| `revert.py` | Undoes everything. Dry-run verified. |
| `backups/` | Every backup, the disabled-package log, and screenshots. |

---

## Done

**Debloat — 26 packages, verified after reboot**

| | Before | After |
|---|---|---|
| RAM available | 69 MB free | 160 MB free / 964 MB available |
| Storage | 3.7 GB used (85%) | 2.7 GB used (64%) |
| Disabled packages | 0 | 26, all survived reboot |
| Boot time | — | 34 s |

Off: PatchWall, Mi analytics, Xiaomi statistics, Sensara, Mi TV+, TV Manager,
the firmware updater, partner auto-installers, Play Music, Play Movies, Mi Music, Mi Gallery.
Kept: Google Assistant, Chromecast, every streaming app.

Also uninstalled at your request (reinstallable from the Play Store):
Aptoide TV, ATV Launcher Free, live.tech.storm, IPTV player, WhatsApp, Meet, Dialer.

**Laptop remote** — `laptop-remote/tv remote`. Verified against the real TV: app list (16 apps,
correct names, disabled ones excluded), key sending, app launch, HOME.

**Mirroring, both directions**
- *Laptop to TV, Google Cast* — live now. TV advertises as `MiTV-AXSO2`. Chrome ⋮ → Cast → Cast desktop. Free.
- *Laptop to TV, AirPlay* — AirScreen was already installed; started it, and the TV now advertises
  `AS-MiTVAXSO2[AirPlay]`. Keeps advertising in the background. Control Centre → Screen Mirroring.
- *TV to laptop* — `laptop-remote/tv mirror` (scrcpy).

**Clean launcher — installed and default**

`com.gathin.tvhome`, built from the repo (532 KB, debug-signed). Survived a reboot: Home resolves
to it, the stock launcher stays disabled, 27 packages disabled in total.

- Dock: Netflix, Prime Video, YouTube, JioHotstar
- Greeting, clock and date top left; Inputs / Wi-Fi / Settings pills top right
- App grid below the dock, glass highlight on focus, ambient glow sampled from the focused app
- Inputs menu lists HDMI1 (shown Connected), HDMI2, HDMI3, AV and Live TV
- No ads, no sponsored rows, no recommendations

Two things worth recording for next time:
- `cmd package set-home-activity` returned `Success` and changed nothing. The handover only happened
  once the stock launcher was disabled. Always verify with `dumpsys activity activities`, never trust
  the return value.
- `config.xml` needed `live_tv_package` changed to `com.android.tv`; the shipped default is the
  MediaTek app, and this board is Amlogic. The stock file is kept at `backups/config.xml.stock`.

## Final state

| | Start | Now |
|---|---|---|
| RAM available | 69 MB free | **967 MB** |
| Storage free | 679 MB | **1.5 GB** |
| Disabled packages | 0 | 27 |
| Home screen | Google TV, ads | Clean custom launcher |
| Boot | — | 42 s |

## Not started

Personalisation: wallpaper, white logos + taglines, My Favourites lineup, mood cards.
The launcher is in place now, so these are unblocked — they need you to collect images first
(see the guide: an evening's work for the favourites and the mood cards).

## Rebuilding the launcher after a config change

    cd cleanyourtv/launcher
    export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home
    export ANDROID_HOME=~/Library/Android/sdk
    ./gradlew assembleRelease
    adb -s 192.168.0.115:5555 install -r app/build/outputs/apk/release/app-release.apk

Do not leave stray files in `app/src/main/res/values/` — anything not ending in `.xml` fails the
resource merge.

## Known limitation

Typing from the laptop (`tv type`) only lands in a **focused text field**. It works for app search
boxes, passwords and login forms; it does nothing on Google TV's home search, which is voice-driven.

## Putting it all back

    python3 revert.py --dry-run     # show what would be undone
    python3 revert.py               # undo it

Re-enables all 26 packages, removes the custom launcher, hands Home back to Google's launcher,
restores recorded settings, and lists the apps to reinstall. Apps were disabled, never uninstalled.

## When you are finished

    laptop-remote/tv off

Then switch USB debugging off on the TV and revoke the debugging authorisations.
Port 5555 is plaintext and gives full control of the TV to anything on your network.
