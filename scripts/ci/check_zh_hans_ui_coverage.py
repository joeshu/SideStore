#!/usr/bin/env python3
"""Regression guard for the SideStore zh-Hans UI coverage fixed from device QA."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FALLBACK = ROOT / "AltStore/zh-Hans.lproj/InterfaceFallback.strings"
HELPER = ROOT / "AltStore/Core/Utilities/InterfaceLocalization.swift"
TAB_ROOT = ROOT / "AltStore/TabBarController.swift"

# English strings that were visibly left untranslated in the 2026-09-07
# real-device screenshots. Product/service names may intentionally remain Latin.
REQUIRED_KEYS = {
    "Settings",
    "My Apps",
    "News",
    "Sources",
    "Name",
    "Email",
    "Type",
    "Support the team",
    "Support the SideStore Team",
    "Support the SideStore Team by following our socials or becoming a patron!",
    "Change App Icon",
    "Personalize your SideStore experience by choosing an alternate app icon.",
    "Background Refresh",
    "Disable Idle Timeout",
    "Storage Explorer",
    "Clear Data Cache...",
    "Free up disk space by removing non-essential data, such as temporary files and backups for uninstalled apps.",
    "CREDITS",
    "Developers",
    "UI Designer",
    "Asset Designer",
    "Licenses",
    "Enable Beta Updates",
    "Beta Updates Track",
    "Opt in for beta testing to receive regular updates and early previews of upcoming releases.",
    "Please note that these builds are experimental and may be unstable or break unexpectedly.",
    "View Refresh Attempts",
    "SideJITServer",
    "Reset Pairing File",
    "Anisette Servers",
    "Connection Config",
    "Developer Portal Services",
    "Certificate Management",
    "Backup & Restore",
    "User Customizations",
    "Developer Options",
    "Experimental Features",
    "View App IDs",
    "Refresh App ID cache",
    "%d App IDs Remaining",
}

INTENTIONALLY_UNCHANGED = {"SideJITServer"}


def parse_strings(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'^\s*"((?:\\.|[^"\\])*)"\s*=\s*"((?:\\.|[^"\\])*)"\s*;\s*$', re.MULTILINE)
    return {key: value for key, value in pattern.findall(text)}


def fail(message: str) -> None:
    print(f"[zh-Hans UI guard] FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    for path in (FALLBACK, HELPER, TAB_ROOT):
        if not path.is_file():
            fail(f"missing required file: {path.relative_to(ROOT)}")

    translations = parse_strings(FALLBACK)
    missing = sorted(REQUIRED_KEYS - translations.keys())
    if missing:
        fail("missing translations: " + ", ".join(repr(item) for item in missing))

    untranslated = sorted(
        key
        for key in REQUIRED_KEYS - INTENTIONALLY_UNCHANGED
        if not translations[key].strip() or translations[key] == key
    )
    if untranslated:
        fail("English fallback remains for: " + ", ".join(repr(item) for item in untranslated))

    helper = HELPER.read_text(encoding="utf-8")
    for marker in (
        'table: "InterfaceFallback"',
        '" App ID Remaining"',
        '" App IDs Remaining"',
        "applySideStoreInterfaceLocalization()",
        "SideStoreLocalizationBundleMarker",
        "Bundle(for: SideStoreLocalizationBundleMarker.self)",
    ):
        if marker not in helper:
            fail(f"runtime localization helper lost marker: {marker}")

    if "Bundle.main.localizedString" in helper:
        fail("localization helper must not read resources from host Bundle.main in embedded LiveContainer mode")

    tab_root = TAB_ROOT.read_text(encoding="utf-8")
    if "override func viewDidLayoutSubviews()" not in tab_root:
        fail("TabBarController must re-apply localization as lazily loaded tab views appear")
    if tab_root.count("applySideStoreInterfaceLocalization()") < 3:
        fail("TabBarController no longer applies the localization fallback at lifecycle/route boundaries")

    print(f"[zh-Hans UI guard] PASS: {len(REQUIRED_KEYS)} device-visible keys covered with embedded-bundle isolation")


if __name__ == "__main__":
    main()
