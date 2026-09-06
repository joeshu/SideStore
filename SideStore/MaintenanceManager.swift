//
//  MaintenanceManager.swift
//  SideStore
//
//  Created by Magesh K on 22/08/26.
//  Copyright © 2026 SideStore. All rights reserved.
//

import Foundation

public final class MaintenanceManager {
    public static let shared = MaintenanceManager()

    // Increment this counter whenever you want to trigger another maintenance pass in future updates
    public static let currentMaintenanceCounter = 1

    public static let maintenanceCounterFileName = ".maintenance_counter"

    private var maintenanceCounterFileURL: URL? {
        FileManager.default.altstoreSharedDirectory?.appendingPathComponent(Self.maintenanceCounterFileName)
    }

    private init() {}

    public func performMaintenanceIfNeeded() {
        guard let fileURL = maintenanceCounterFileURL else {
            debugLog("[MaintenanceManager] ERROR: Unable to resolve App Group shared directory.")
            return
        }

        let completedCounter: Int
        if let data = try? Data(contentsOf: fileURL),
           let str = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
           let val = Int(str) {
            completedCounter = val
        } else {
            completedCounter = 0
        }

        let currentVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""

        // Preserve account credentials across embedded SideStore upgrades. A pairing
        // migration must never clear unrelated Apple authentication state.
        if completedCounter < Self.currentMaintenanceCounter && currentVersion.hasPrefix("0.6.4") {
            debugLog("[MaintenanceManager] Marking maintenance complete without modifying Keychain.")

            let counterString = "\(Self.currentMaintenanceCounter)"
            do {
                try counterString.data(using: .utf8)?.write(to: fileURL, options: .atomic)
                debugLog("[MaintenanceManager] Saved maintenance counter \(Self.currentMaintenanceCounter) to App Group at \(fileURL.path).")
            } catch {
                debugLog("[MaintenanceManager] ERROR: Failed to save maintenance counter to App Group: \(error)")
            }
        }
    }
}
