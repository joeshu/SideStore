//
//  InterfaceLocalization.swift
//  AltStore
//
//  Runtime fallback for storyboard/static interface strings that are not
//  currently resolved through zh-Hans storyboard localization resources.
//

@preconcurrency import UIKit

/// Bundle marker whose image lives with SideStore itself. In standalone mode
/// this resolves to SideStore.app; when LiveContainer dylibifies SideStore into
/// SideStoreApp.framework it resolves to that embedded framework instead of the
/// LiveContainer host bundle.
private final class SideStoreLocalizationBundleMarker: NSObject {}

private enum InterfaceLocalization
{
    private static let resourceBundle = Bundle(for: SideStoreLocalizationBundleMarker.self)
    private static let languagePreferenceKey = "SideStorePreferredLanguage"

    private static var activeBundle: Bundle
    {
        guard let languageCode = UserDefaults.standard.string(forKey: languagePreferenceKey),
              languageCode != "en",
              let path = resourceBundle.path(forResource: languageCode, ofType: "lproj"),
              let bundle = Bundle(path: path) else
        {
            // English is the source language. Returning the framework bundle
            // keeps base English strings intact when no explicit Chinese
            // preference is selected.
            return resourceBundle
        }
        return bundle
    }

    // Keep this intentionally scoped to static interface copy. This prevents
    // user/app-provided content from being translated merely because it happens
    // to match a localization key.
    static let storyboardKeys: Set<String> = [
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
        "Refresh App ID cache"
    ]

    static func localized(_ string: String?) -> String?
    {
        guard let string, !string.isEmpty else { return string }

        // Prefer SideStore's normal localization table first. Do not use
        // Bundle.main here: in LiveContainer integration Bundle.main belongs to
        // the host app while SideStore's lproj files remain in its framework.
        let standard = activeBundle.localizedString(forKey: string, value: string, table: nil)
        if standard != string
        {
            return standard
        }

        // My Apps renders the remaining App ID count dynamically. Handle both
        // singular and plural English output without changing model/user data.
        for suffix in [" App ID Remaining", " App IDs Remaining"]
        {
            if string.hasSuffix(suffix)
            {
                let countText = String(string.dropLast(suffix.count))
                if let count = Int(countText)
                {
                    let key = "%d App IDs Remaining"
                    let format = activeBundle.localizedString(forKey: key, value: key, table: "InterfaceFallback")
                    if format != key
                    {
                        return String(format: format, count)
                    }
                }
            }
        }

        guard storyboardKeys.contains(string) else { return string }
        return activeBundle.localizedString(forKey: string, value: string, table: "InterfaceFallback")
    }

    static func localize(_ item: UIBarButtonItem?)
    {
        guard let item, let title = localized(item.title), title != item.title else { return }
        item.title = title
    }
}

extension UIView
{
    /// Applies a narrowly-scoped localization fallback to visible static UI.
    /// Dynamic/model content is deliberately left untouched.
    func applySideStoreInterfaceLocalization()
    {
        if let label = self as? UILabel,
           let localized = InterfaceLocalization.localized(label.text),
           localized != label.text
        {
            label.text = localized
        }

        if let button = self as? UIButton
        {
            let states: [UIControl.State] = [.normal, .highlighted, .selected, .disabled]
            for state in states
            {
                guard let title = button.title(for: state),
                      let localized = InterfaceLocalization.localized(title),
                      localized != title else { continue }
                button.setTitle(localized, for: state)
            }
        }

        if let segmentedControl = self as? UISegmentedControl
        {
            for index in 0..<segmentedControl.numberOfSegments
            {
                guard let title = segmentedControl.titleForSegment(at: index),
                      let localized = InterfaceLocalization.localized(title),
                      localized != title else { continue }
                segmentedControl.setTitle(localized, forSegmentAt: index)
            }
        }

        if let textField = self as? UITextField,
           let localized = InterfaceLocalization.localized(textField.placeholder),
           localized != textField.placeholder
        {
            textField.placeholder = localized
        }

        if let searchBar = self as? UISearchBar,
           let localized = InterfaceLocalization.localized(searchBar.placeholder),
           localized != searchBar.placeholder
        {
            searchBar.placeholder = localized
        }

        for subview in subviews
        {
            subview.applySideStoreInterfaceLocalization()
        }
    }
}

extension UIViewController
{
    /// Localizes static controller metadata and any currently-loaded view tree
    /// without forcing lazy tab contents to load.
    func applySideStoreInterfaceLocalization()
    {
        if let localized = InterfaceLocalization.localized(title), localized != title
        {
            title = localized
        }

        if let localized = InterfaceLocalization.localized(navigationItem.title), localized != navigationItem.title
        {
            navigationItem.title = localized
        }

        if let localized = InterfaceLocalization.localized(tabBarItem.title), localized != tabBarItem.title
        {
            tabBarItem.title = localized
        }

        InterfaceLocalization.localize(navigationItem.backBarButtonItem)
        navigationItem.leftBarButtonItems?.forEach { InterfaceLocalization.localize($0) }
        navigationItem.rightBarButtonItems?.forEach { InterfaceLocalization.localize($0) }

        if isViewLoaded
        {
            view.applySideStoreInterfaceLocalization()
        }

        for child in children
        {
            // Metadata can be localized without loading the child's view.
            if let localized = InterfaceLocalization.localized(child.title), localized != child.title
            {
                child.title = localized
            }
            if let localized = InterfaceLocalization.localized(child.tabBarItem.title), localized != child.tabBarItem.title
            {
                child.tabBarItem.title = localized
            }

            if child.isViewLoaded
            {
                child.applySideStoreInterfaceLocalization()
            }
        }
    }
}
