#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
LPROJ = ROOT / "AltStore" / "zh-Hans.lproj"
LOCALIZABLE = LPROJ / "Localizable.strings"
INFO = ROOT / "AltStore" / "Info.plist"

required_files = [
    LOCALIZABLE,
    LPROJ / "InfoPlist.strings",
    LPROJ / "Main.strings",
    LPROJ / "Sources.strings",
    LPROJ / "Authentication.strings",
    LPROJ / "Settings.strings",
]

required_keys = {
    "Settings",
    "News",
    "Sources",
    "Browse",
    "My Apps",
    "Welcome to SideStore.",
    "Sign in with your Apple ID to get started.",
    "Refresh All",
    "No Updates Available",
    "Health Check",
    "Developer Options",
    "Action Required",
    "Pairing file",
    "Minimuxer readiness",
    "Apple Authentication",
    "Connection Configuration",
    "LOGGING & DIAGNOSTICS",
    "DATABASE OPTIONS",
    "WIREGUARD CONFIGURATION",
}

errors = []

for path in required_files:
    if not path.is_file():
        errors.append(f"missing localization resource: {path.relative_to(ROOT)}")

if INFO.is_file():
    info = INFO.read_text(encoding="utf-8")
    if "<key>CFBundleLocalizations</key>" not in info:
        errors.append("Info.plist does not declare CFBundleLocalizations")
    if "<string>zh-Hans</string>" not in info:
        errors.append("Info.plist does not declare zh-Hans")
else:
    errors.append("AltStore/Info.plist is missing")

if LOCALIZABLE.is_file():
    text = LOCALIZABLE.read_text(encoding="utf-8")
    pairs = dict(re.findall(r'^\s*"((?:\\.|[^"])*)"\s*=\s*"((?:\\.|[^"])*)"\s*;', text, re.MULTILINE))
    if len(pairs) < 140:
        errors.append(f"zh-Hans catalog is unexpectedly small: {len(pairs)} entries")
    missing = sorted(required_keys - pairs.keys())
    if missing:
        errors.append("missing critical zh-Hans keys: " + ", ".join(missing))
    untranslated = sorted(key for key in required_keys if pairs.get(key) == key)
    if untranslated:
        errors.append("critical keys still equal English source: " + ", ".join(untranslated))

# Dynamic SwiftUI String values bypass LocalizedStringKey. Guard the two high-risk pages.
dev = ROOT / "SideStore/Views/Settings/Diagnostics/DeveloperOptionsView.swift"
if dev.is_file():
    source = dev.read_text(encoding="utf-8")
    if "private func toggleRow(title: LocalizedStringKey" not in source:
        errors.append("DeveloperOptionsView toggleRow is not localization-aware")
    for key in ["WIDGET OPTIONS", "Reload All Widgets", "Rotate Widget Log"]:
        if f'let title = "{key}"' in source:
            errors.append(f"DeveloperOptionsView still uses a verbatim dynamic String: {key}")
else:
    errors.append("DeveloperOptionsView.swift is missing")

health = ROOT / "SideStore/Views/Settings/TechyThings/HealthCheck/HealthCheckView.swift"
if health.is_file():
    source = health.read_text(encoding="utf-8")
    if "private func healthLocalized(_ key: String)" not in source:
        errors.append("HealthCheckView dynamic text is not localization-aware")
    if "Text(healthLocalized(title))" not in source:
        errors.append("HealthCheck DependencyRow does not localize dynamic titles")
else:
    errors.append("HealthCheckView.swift is missing")

if errors:
    print("Simplified Chinese localization audit FAILED:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("Simplified Chinese localization audit passed")
