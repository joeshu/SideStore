//
//  RemoveAppExtensionsOperation.swift
//  AltStore
//
//  Created by Riley Testut on 2/27/20.
//  Copyright © 2020 Riley Testut. All rights reserved.
//


import Foundation
import SideSign

final class RemoveAppExtensionsOperation: BasePipelineOperation<InstallAppOperationContext, ALTApplication>, @unchecked Sendable {
    private static let keepAppExtensionsInfoKey = "ALTKeepAppExtensions"

    let localAppExtensions: Set<ALTApplication>?
    
    init(context: InstallAppOperationContext, localAppExtensions: Set<ALTApplication>?) throws {
        self.localAppExtensions = localAppExtensions
        try super.init(context: context)
    }
    
    override func execute(parentProgress: Progress?) async throws -> ALTApplication {
        let startTime = CFAbsoluteTimeGetCurrent()
        debugLog("[RemoveAppExtensionsOperation] execute() started")
        defer {
            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            debugLog("[RemoveAppExtensionsOperation] execute() took: \(String(format: "%.3fs", elapsed))")
        }
        try await super.executePreconditionCheck(parentProgress: parentProgress)
        self.setProgress(10)
        
        guard let targetAppBundle = context.targetAppBundle else {
            throw OperationError.invalidParameters("RemoveAppExtensionsOperation: context.appBundle is nil")
        }
        
        // target App Bundle doesn't contain extensions so don't bother
        guard !targetAppBundle.appExtensions.isEmpty else {
            self.setProgress(100)
            return targetAppBundle
        }

        // Some host applications depend on their bundled extensions to function correctly.
        // Such apps can opt out of SideStore's extension-pruning behavior by declaring
        // ALTKeepAppExtensions = true in their Info.plist. This is intentionally checked
        // before comparing against the currently installed app: a reinstall must be able
        // to restore an extension that a previous install accidentally stripped.
        //
        // Reusing the main profile is the existing SideStore mode for preserving all
        // extensions without consuming one App ID per extension on free developer teams.
        if self.shouldKeepAllAppExtensions(for: targetAppBundle) {
            self.context.useMainProfile = true
            self.debugLog("[RemoveAppExtensionsOperation] ALTKeepAppExtensions is enabled; preserving all \(targetAppBundle.appExtensions.count) extensions and using the main profile.")
            self.setProgress(100)
            return targetAppBundle
        }
        
        self.setProgress(30)
        let excessExtensions = processExtensionsInfo(from: targetAppBundle, localAppExtensions: localAppExtensions)
        
        let handler = self.context.handler.extensionRemovalHandler
        guard UserDefaults.standard.customizeAppExtensions else {
            // perform silent extensions cleanup for those that aren't already present in existing app
            // background mode: remove only the excess extensions automatically for re-installs
            //                  keep all extensions for fresh install (localAppBundle = nil)
            try self.removeExtensions(from: excessExtensions, endPercent: 100)
            return targetAppBundle
        }
        
        self.setProgress(50)
        let decision = try await handler.selectAppExtensionsToRemove(
            appBundle: targetAppBundle,
            localAppExtensions: Array(localAppExtensions ?? []),
            excessExtensions: excessExtensions
        )
        
        switch decision {
        case .cancel:
            throw OperationError.cancelled
            
        case .keepAll(let useMainProfile):
            self.context.useMainProfile = useMainProfile
            self.setProgress(100)
            
        case .removeAll:
            try self.removeExtensions(from: targetAppBundle.appExtensions, endPercent: 85)
            try self.updateManifest()
            self.setProgress(100)
            
        case .removeSelected(let selection):
            try self.removeExtensions(from: selection, endPercent: 100)
            self.setProgress(100)
        }
        
        return targetAppBundle
    }

    private func shouldKeepAllAppExtensions(for appBundle: ALTApplication) -> Bool {
        let infoPlistURL = appBundle.fileURL.appendingPathComponent("Info.plist")
        guard
            let data = try? Data(contentsOf: infoPlistURL),
            let propertyList = try? PropertyListSerialization.propertyList(from: data, options: [], format: nil),
            let infoDictionary = propertyList as? [String: Any]
        else {
            return false
        }

        return infoDictionary[Self.keepAppExtensionsInfoKey] as? Bool == true
    }
    
    private func removeExtensions(from extensions: Set<ALTApplication>, endPercent: Int64) throws {
        let isLoggingEnabled = OperationsLoggingControl.isLoggingEnabled(for: RemoveAppExtensionsOperation.self)
        let startProgress = self.progress.completedUnitCount
        let range = endPercent - startProgress
        guard !extensions.isEmpty else {
            self.setProgress(endPercent)
            return
        }
        let array = Array(extensions)
        let count = array.count
        for (index, appExtension) in array.enumerated() {
            if range > 0 {
                let percent = startProgress + Int64(Double(index + 1) / Double(count) * Double(range))
                self.setProgress(percent)
            }
            if isLoggingEnabled {
                debugLog("Deleting extension \(appExtension.bundleIdentifier)")
            }
            try FileManager.default.removeItem(at: appExtension.fileURL)
        }
    }

    private func updateManifest() throws {
        guard let appBundle = context.targetAppBundle else {
            return
        }
        
        let scInfoURL = appBundle.fileURL.appendingPathComponent("SC_Info")
        let manifestPlistURL = scInfoURL.appendingPathComponent("Manifest.plist")
        
        if let manifestPlist = NSMutableDictionary(contentsOf: manifestPlistURL),
           let sinfReplicationPaths = manifestPlist["SinfReplicationPaths"] as? [String] {
            let replacementPaths = sinfReplicationPaths.filter { !$0.starts(with: "PlugIns/") } // Filter out app extension paths.
            manifestPlist["SinfReplicationPaths"] = replacementPaths
            try manifestPlist.write(to: manifestPlistURL)
        }
    }
    
    struct ExtensionsInfo {
        let excessInTarget: Set<ALTApplication>
        let necessaryInExisting: Set<ALTApplication>
    }
    
    private func processExtensionsInfo(from targetAppBundle: ALTApplication,
                                       localAppExtensions: Set<ALTApplication>?) -> Set<ALTApplication> {
        //App-Extensions: Ensure existing app's extensions in DB and currently installing app bundle's extensions must match
        let targetAppEx: Set<ALTApplication> = targetAppBundle.appExtensions
        let targetAppExNames  = targetAppEx.map { appEx in appEx.bundleIdentifier }

        guard let extensionsInExistingApp = localAppExtensions else {
            let diagnosticsMsg = "RemoveAppExtensionsOperation: ExistingApp is nil, Hence keeping all app extensions from targetAppBundle"
                               + "RemoveAppExtensionsOperation: ExistingAppEx: nil; targetAppBundleEx: \(targetAppExNames)"
            verboseLog(diagnosticsMsg)
            return Set()    // nothing is excess since we are keeping all, so returning empty
        }
        
        let existingAppEx: Set<ALTApplication> = extensionsInExistingApp
        let existingAppExNames = existingAppEx.map { appEx in appEx.bundleIdentifier }
        
        let excessExtensionsInTargetApp = targetAppEx.filter {
            !(existingAppExNames.contains($0.bundleIdentifier))
        }
        let isMatching = (targetAppEx.count == existingAppEx.count) && excessExtensionsInTargetApp.isEmpty
        let diagnosticsMsg = "RemoveAppExtensionsOperation: App Extensions in localAppBundle and targetAppBundle are matching: \(isMatching)\n"
                            + "RemoveAppExtensionsOperation: \nlocalAppBundleEx: \(existingAppExNames); \ntargetAppBundleEx: \(String(describing: targetAppExNames))\n"
        verboseLog(diagnosticsMsg)

        return excessExtensionsInTargetApp
    }
}
