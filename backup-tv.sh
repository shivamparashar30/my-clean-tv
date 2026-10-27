#!/usr/bin/env bash
# Record everything about the TV that we might change, before we change it.
# Re-runnable: each run goes in its own timestamped folder.
set -uo pipefail

TV_HOST="${TV_HOST:-192.168.0.115}"
T="${TV_HOST}:5555"
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
OUT="$(dirname "$0")/backups/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$OUT"

say() { printf '  %-34s' "$1"; }
cap() { # cap <file> <adb shell command>
  say "$1"
  "$ADB" -s "$T" shell "$2" 2>&1 | tr -d '\r' > "$OUT/$1"
  printf '%s lines\n' "$(wc -l < "$OUT/$1" | tr -d ' ')"
}

echo "Backing up $T -> $OUT"
echo

echo "Identity"
cap getprop.txt                 "getprop"
cap build.txt                   "getprop ro.product.device; getprop ro.product.model; getprop ro.build.display.id; getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.product.board"

echo "Packages"
cap packages-all.txt            "pm list packages"
cap packages-enabled.txt        "pm list packages -e"
cap packages-disabled.txt       "pm list packages -d"
cap packages-system.txt         "pm list packages -s"
cap packages-third-party.txt    "pm list packages -3"
cap packages-with-paths.txt     "pm list packages -f"

echo "Home / launcher"
cap home-activities.txt         "cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.HOME"
cap home-resolved.txt           "cmd package resolve-activity -a android.intent.action.MAIN -c android.intent.category.HOME"
cap leanback-activities.txt     "cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.LEANBACK_LAUNCHER"
cap preferred-activities.txt    "dumpsys package preferred-activities"

echo "Settings (all three namespaces)"
cap settings-global.txt         "settings list global"
cap settings-secure.txt         "settings list secure"
cap settings-system.txt         "settings list system"

echo "Display / input / state"
cap display.txt                 "wm size; wm density; settings get secure display_density_forced"
cap inputs.txt                  "dumpsys tv_input_manager | head -80"
cap meminfo.txt                 "cat /proc/meminfo"
cap storage.txt                 "df -h"
cap accessibility.txt           "settings get secure enabled_accessibility_services"
cap ime.txt                     "settings get secure default_input_method; ime list -s"
cap private-dns.txt             "settings get global private_dns_mode; settings get global private_dns_specifier"
cap animation-scales.txt        "settings get global window_animation_scale; settings get global transition_animation_scale; settings get global animator_duration_scale"

# A human-readable summary at the top of the folder
{
  echo "TV backup — $(date)"
  echo "Host: $T"
  echo
  sed 's/^/  /' "$OUT/build.txt"
  echo
  echo "Packages: $(grep -c package: "$OUT/packages-all.txt") installed, \
$(grep -c package: "$OUT/packages-disabled.txt") disabled, \
$(grep -c package: "$OUT/packages-third-party.txt") third-party"
  echo "Home resolves to: $(grep -m1 'packageName=' "$OUT/home-resolved.txt" | tr -d ' ')"
  echo
  echo "To see what changed later:  diff -u $OUT/packages-disabled.txt <new backup>/packages-disabled.txt"
} > "$OUT/SUMMARY.txt"

echo
cat "$OUT/SUMMARY.txt"
echo
echo "Saved to $OUT"
