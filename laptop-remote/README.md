# Laptop ↔ TV

Everything here talks to the TV over your home Wi-Fi using ADB. No cables, no root,
nothing installed on the TV for the remote itself.

## One-time setup

**On the TV:** Settings → Device Preferences → About → press OK on **Build** seven times.
Go back → **Developer options** → turn on **USB debugging** *and* **Network/ADB debugging**
(Mi TVs list both).

**On this Mac:** make sure it is on the *same Wi-Fi* as the TV, then:

```bash
cd ~/Documents/TV/laptop-remote
./tv find                 # finds the TV's IP
./tv connect 192.168.x.x  # accept "Allow USB debugging?" on the TV, tick "Always allow"
./tv probe                # should print the model, Android version and RAM
```

The IP is remembered in `.tv-state.json`, so you only do this once (until the TV's IP changes).

## The remote

```bash
./tv remote
```

Opens `http://localhost:8787`. Two tabs.

**Remote** — D-pad, volume, playback, your installed apps as buttons, and a quick text box.

**Touchpad & typing** — a pad that *is* the TV screen, with a picture of the TV behind it:

| Gesture | What it does |
|---|---|
| Click | Taps that exact spot on the TV (`input tap`) |
| Drag | Swipes from where you pressed to where you released |
| Scroll wheel | Scrolls the TV |
| Refresh now / Pause | The pad goes live automatically when you open the tab |

Under the pad: **Back, Home, Vol −, Mute, Vol +**, so you do not have to switch tabs for the
things you reach for constantly. The tab bar stays pinned to the top as you scroll.

**Why it is about 1 fps.** The TV itself needs ~1.2 s to PNG-encode a 1920x1080 frame — it is
CPU-bound on a 2 GB Amlogic chip, and no ADB trick gets around it (a persistent `adb shell` made
no difference at all). So captures run **continuously in a background thread** and the browser is
served the newest one instantly: `/screen.png` answers in **0.003 s** instead of 1.2-1.7 s, and your
clicks never wait for a screenshot. The picture still only updates about once a second.
For real-time video use **Open mirror** (scrcpy), which uses the hardware H.264 encoder.

**Apps that block capture.** Netflix, Prime Video and HDMI inputs refuse screen capture at the OS
level — `screencap` returns 0 bytes. The pad detects this and says so instead of showing a frozen
old frame. Your clicks still reach the app; you just cannot see it. Use the Remote tab's D-pad there.

Android TV has no mouse cursor, so a relative trackpad would have nothing to move; mapping the pad
to screen coordinates is what actually works here. Verified on this TV: a click at pad position
(0.607, 0.761) taps (1166, 822) and launches the app under it.

The big type box has **Send** and **Send + OK** (types, then presses OK to submit).

Your Mac keyboard drives it directly: arrows move, <kbd>⏎</kbd> is OK, <kbd>⌫</kbd> is Back,
<kbd>H</kbd> is Home, <kbd>+</kbd>/<kbd>−</kbd> volume, <kbd>M</kbd> mute, <kbd>space</kbd> play/pause.

It keeps one long-lived `adb shell` open, so a keypress lands in milliseconds rather than
the ~200ms a fresh `adb` call costs.

## Seeing the TV on your laptop

```bash
./tv mirror
```

Opens the TV's screen in a window (scrcpy). Click with the mouse, type with the keyboard.
Netflix, Prime Video, Live TV and HDMI inputs appear black — those apps block capture at the
hardware level. That is the TV protecting the content, not a fault here.

## Mirroring the *laptop* onto the TV

Different direction, different technology — ADB can't do it. Two options:

| | How | Quality |
|---|---|---|
| **AirPlay** (recommended) | Install **AirScreen** from the Play Store on the TV and open it once. Your Mac then sees the TV in Control Centre → Screen Mirroring, like an Apple TV. | Full desktop, audio, best |
| **Google Cast** | Mi TVs have Chromecast built in. In Chrome: ⋮ → Cast → choose the TV → *Cast desktop*. | Fine for a tab, laggier for the desktop |

macOS cannot use the TV's own "Mi Screen Mirroring" / Miracast — that is a Windows and
Android protocol.

## Typing: what it can and cannot do

`tv type` and both text boxes use `input text`, which goes to whatever field currently has
**focus** on the TV. That means it works in app search boxes, password fields and login forms —
and does nothing on Google TV's own home search, which is voice-driven. Focus the field first.

## Everything else

```bash
./tv apps                 # list the TV's apps
./tv open netflix         # launch one by name
./tv key HOME DOWN OK     # send remote keys
./tv type "stranger things"
./tv url https://www.netflix.com/title/80057281
./tv shot screen.png      # screenshot the TV
./tv shell "pm list packages -d"
./tv off                  # close the ADB port when you're done
```

## Security

Port 5555 is plaintext and gives full control of the TV to anything on your network.
It is fine while you are working, but run `./tv off` and switch Developer options back off
when you are done. Never forward that port through your router.
