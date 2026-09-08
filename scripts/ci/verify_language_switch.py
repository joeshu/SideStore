#!/usr/bin/env python3
"""Guard the real in-app language switch contract."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "AltStore/Settings/SettingsViewController.swift"
STRINGS = ROOT / "AltStore/zh-Hans.lproj/Localizable.strings"


def fail(message: str) -> "NoReturn":
    print(f"[language switch] FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    settings = SETTINGS.read_text(encoding="utf-8")
    strings = STRINGS.read_text(encoding="utf-8")

    required_settings = [
        "enum SideStoreLanguage: String, CaseIterable",
        'UserDefaults.standard.string(forKey: "SideStorePreferredLanguage")',
        'UserDefaults.standard.set(language.rawValue, forKey: "SideStorePreferredLanguage")',
        'UserDefaults.standard.set([language.rawValue], forKey: "AppleLanguages")',
        'UserDefaults.standard.set(language.localeIdentifier, forKey: "AppleLocale")',
        "UIAlertController(",
        "SideStoreLanguage.allCases",
        "Restart SideStore",
        "exit(0)",
    ]
    missing_settings = [marker for marker in required_settings if marker not in settings]
    if missing_settings:
        fail("settings implementation is missing: " + ", ".join(missing_settings))

    if "UIApplication.openSettingsURLString" in settings:
        fail("language switch must not be a system-settings-only redirect")

    required_strings = [
        '"Choose SideStore language"',
        '"Simplified Chinese"',
        '"Language changed"',
        '"Restart SideStore"',
    ]
    missing_strings = [marker for marker in required_strings if marker not in strings]
    if missing_strings:
        fail("Chinese localization is missing: " + ", ".join(missing_strings))

    print("[language switch] PASS: in-app picker, persisted preference, restart, and zh-Hans copy are present")


if __name__ == "__main__":
    main()
