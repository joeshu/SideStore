//
//  InterfaceLocalization.swift
//  AltStore
//
//  Runtime fallback for storyboard/static interface strings that are not
//  currently resolved through zh-Hans storyboard localization resources.
//

@preconcurrency import UIKit

private enum InterfaceLocalization
{
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
        "Change App Icon",
        "Background Refresh",
        "Disable Idle Timeout",
        "Storage Explorer",
        "Clear Data Cache...",
        "Developers",
        "UI Designer",
        "Asset Designer",
        "Licenses",
        "Enable Beta Updates",
        "Beta Updates Track",
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
        "View App IDs"
    ]

    static func localized(_ string: String?) -> String?
    {
        guard let string, !string.isEmpty, storyboardKeys.contains(string) else {
            return string
        }

        return Bundle.main.localizedString(forKey: string, value: string, table: nil)
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
