//
//  DeveloperPortalService.swift
//  SideStore
//
//  Created by Magesh K on 2026-06-29.
//  Copyright © 2026 SideStore. All rights reserved.
//

@preconcurrency import UIKit
import SideSign

private let sideStoreAuthStageKey = "SideStoreAuthStage"
private let sideStoreAuthOriginalDomainKey = "SideStoreAuthOriginalDomain"
private let sideStoreAuthOriginalCodeKey = "SideStoreAuthOriginalCode"

private struct AuthSubstageSample: Codable {
    enum Outcome: String, Codable {
        case event
        case succeeded
        case failed
    }

    let stage: String
    let startedAt: Date
    let completedAt: Date
    let elapsedMilliseconds: Int
    let outcome: Outcome
    let errorDomain: String?
    let errorCode: Int?
    let metadata: String?
}

private struct AuthSubstageTrace: Codable {
    let version: Int
    let updatedAt: Date
    let samples: [AuthSubstageSample]
}

private final class AuthSubstageTraceStore {
    static let shared = AuthSubstageTraceStore()
    static let defaultsKey = "SideStoreLastAuthSubstageTrace"

    private let lock = NSLock()
    private var samples: [AuthSubstageSample] = []

    private init() {}

    func reset() {
        self.lock.lock()
        defer { self.lock.unlock() }
        self.samples = []
        self.persistLocked()
    }

    func markEvent(_ stage: String, metadata: String? = nil) {
        let now = Date()
        let sample = AuthSubstageSample(
            stage: stage,
            startedAt: now,
            completedAt: now,
            elapsedMilliseconds: 0,
            outcome: .event,
            errorDomain: nil,
            errorCode: nil,
            metadata: metadata
        )
        self.append(sample)
        debugLog("[AuthTrace] stage=\(stage) event metadata=\(metadata ?? "none")")
    }

    func begin(_ stage: String) -> Date {
        let startedAt = Date()
        debugLog("[AuthTrace] stage=\(stage) start")
        return startedAt
    }

    func finish(_ stage: String, startedAt: Date, error: NSError? = nil) {
        let completedAt = Date()
        let elapsedMilliseconds = max(0, Int(completedAt.timeIntervalSince(startedAt) * 1000))
        let sample = AuthSubstageSample(
            stage: stage,
            startedAt: startedAt,
            completedAt: completedAt,
            elapsedMilliseconds: elapsedMilliseconds,
            outcome: error == nil ? .succeeded : .failed,
            errorDomain: error?.domain,
            errorCode: error?.code,
            metadata: nil
        )
        self.append(sample)
        debugLog(
            "[AuthTrace] stage=\(stage) outcome=\(sample.outcome.rawValue) elapsedMs=\(elapsedMilliseconds) domain=\(error?.domain ?? "none") code=\(error?.code ?? 0)"
        )
    }

    private func append(_ sample: AuthSubstageSample) {
        self.lock.lock()
        defer { self.lock.unlock() }
        self.samples.append(sample)
        self.persistLocked()
    }

    private func persistLocked() {
        let trace = AuthSubstageTrace(version: 1, updatedAt: Date(), samples: self.samples)
        do {
            let data = try JSONEncoder().encode(trace)
            UserDefaults.standard.set(data, forKey: Self.defaultsKey)
        } catch {
            let nsError = error as NSError
            debugLog("[AuthTrace] persist failure domain=\(nsError.domain) code=\(nsError.code)")
        }
    }
}

private func classifiedAuthStage(for error: Error, fallback: String) -> String {
    var currentError: NSError? = error as NSError
    var domains: [String] = []
    var visited = Set<ObjectIdentifier>()

    while let nsError = currentError {
        let identity = ObjectIdentifier(nsError)
        guard visited.insert(identity).inserted else { break }
        domains.append(nsError.domain)
        currentError = nsError.userInfo[NSUnderlyingErrorKey] as? NSError
    }

    if domains.contains(where: { $0 == "SideSign.DeveloperPortal.account" }) {
        return "developer_portal_account"
    }
    if domains.contains(where: {
        $0 == "SideSign.GSA.sms.verify" || $0 == "SideSign.GSA.trustedDevice.verify"
    }) {
        return "two_factor_verify"
    }
    if domains.contains(where: {
        $0 == "SideSign.GSA.trustedPhones"
            || $0 == "SideSign.GSA.sms"
            || $0 == "SideSign.GSA.trustedDevice"
    }) {
        return "two_factor"
    }
    if domains.contains(where: { $0 == "SideSign.GSA.apptokens" }) {
        return "app_token"
    }
    if domains.contains(where: { $0 == "SideSign.GSA.init" || $0 == "SideSign.GSA.complete" }) {
        return "gsa_srp"
    }
    return fallback
}

private func stagedAuthError(_ error: Error, stage: String) -> NSError {
    let nsError = error as NSError
    let effectiveStage = classifiedAuthStage(for: error, fallback: stage)
    var userInfo = nsError.userInfo
    userInfo[sideStoreAuthStageKey] = effectiveStage
    userInfo[sideStoreAuthOriginalDomainKey] = nsError.domain
    userInfo[sideStoreAuthOriginalCodeKey] = nsError.code
    // Preserve the original NSError so UI diagnostics can surface the real domain/code
    // without copying authentication credentials, tokens, Anisette data or 2FA values.
    userInfo[NSUnderlyingErrorKey] = nsError

    return NSError(
        domain: "SideStore.Authentication",
        code: nsError.code,
        userInfo: userInfo
    )
}

public class DeveloperPortalService {
    public static let shared: DeveloperPortalService = DeveloperPortalAuthService()
    
    fileprivate init() {}
    
    public func fetchTeams(for account: ALTAccount, session: ALTAppleAPISession) async throws -> [ALTTeam] {
        try await ALTAppleAPI.shared.fetchTeams(for: account, session: session)
    }
    
    public func fetchCertificates(team: ALTTeam, session: ALTAppleAPISession) async throws -> [ALTX509Certificate] {
        try await ALTAppleAPI.shared.fetchCertificates(for: team, session: session)
    }
    
    public func createCertificate(machineName: String, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTCertificate {
        try await ALTAppleAPI.shared.addCertificate(machineName: machineName, to: team, session: session)
    }
    
    public func revokeCertificate(_ certificate: ALTX509Certificate, team: ALTTeam, session: ALTAppleAPISession) async throws -> Bool {
        try await ALTAppleAPI.shared.revokeCertificate(certificate, for: team, session: session)
    }
    
    public func fetchDevices(for team: ALTTeam, types: ALTDeviceType, session: ALTAppleAPISession) async throws -> [ALTDevice] {
        try await ALTAppleAPI.shared.fetchDevices(for: team, types: types, session: session)
    }
    
    public func registerDevice(name: String, identifier: String, type: ALTDeviceType, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTDevice {
        try await ALTAppleAPI.shared.registerDevice(name: name, identifier: identifier, type: type, team: team, session: session)
    }

    public func updateDevice(_ device: ALTDevice, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTDevice {
        try await ALTAppleAPI.shared.updateDevice(device, team: team, session: session)
    }

    public func disableDevice(_ device: ALTDevice, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTDevice {
        try await ALTAppleAPI.shared.disableDevice(device, team: team, session: session)
    }

    public func deleteDevice(_ device: ALTDevice, team: ALTTeam, session: ALTAppleAPISession) async throws -> Bool {
        try await ALTAppleAPI.shared.deleteDevice(device, team: team, session: session)
    }

    public func fetchAppIDs(team: ALTTeam, session: ALTAppleAPISession) async throws -> [ALTAppID] {
        try await ALTAppleAPI.shared.fetchAppIDs(for: team, session: session)
    }

    public func addAppID(name: String, bundleIdentifier: String, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTAppID {
        try await ALTAppleAPI.shared.addAppID(withName: name, bundleIdentifier: bundleIdentifier, team: team, session: session)
    }

    public func updateAppID(_ appID: ALTAppID, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTAppID {
        try await ALTAppleAPI.shared.updateAppID(appID, team: team, session: session)
    }

    public func deleteAppID(_ appID: ALTAppID, team: ALTTeam, session: ALTAppleAPISession) async throws -> Bool {
        try await ALTAppleAPI.shared.deleteAppID(appID, for: team, session: session)
    }

    public func fetchAppGroups(team: ALTTeam, session: ALTAppleAPISession) async throws -> [ALTAppGroup] {
        try await ALTAppleAPI.shared.fetchAppGroups(for: team, session: session)
    }

    public func addAppGroup(name: String, groupIdentifier: String, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTAppGroup {
        try await ALTAppleAPI.shared.addAppGroup(name: name, groupIdentifier: groupIdentifier, team: team, session: session)
    }

    public func updateAppGroup(_ group: ALTAppGroup, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTAppGroup {
        try await ALTAppleAPI.shared.updateAppGroup(group, team: team, session: session)
    }

    public func assignAppID(_ appID: ALTAppID, to groups: [ALTAppGroup], team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTAppID {
        try await ALTAppleAPI.shared.assign(appID, to: groups, team: team, session: session)
    }

    public func deleteAppGroup(_ group: ALTAppGroup, team: ALTTeam, session: ALTAppleAPISession) async throws -> Bool {
        try await ALTAppleAPI.shared.deleteAppGroup(group, team: team, session: session)
    }

    public func fetchProvisioningProfiles(team: ALTTeam, session: ALTAppleAPISession) async throws -> [ALTProvisioningProfile] {
        try await ALTAppleAPI.shared.fetchProvisioningProfiles(for: team, session: session)
    }

    public func downloadProvisioningProfile(for appID: ALTAppID, deviceType: ALTDeviceType = .iphone, team: ALTTeam, session: ALTAppleAPISession) async throws -> ALTProvisioningProfile {
        try await ALTAppleAPI.shared.downloadProvisioningProfile(for: appID, deviceType: deviceType, team: team, session: session)
    }

    public func deleteProvisioningProfile(_ profile: ALTProvisioningProfile, team: ALTTeam, session: ALTAppleAPISession) async throws -> Bool {
        try await ALTAppleAPI.shared.deleteProvisioningProfile(profile, team: team, session: session)
    }
}

class DeveloperPortalAuthService: DeveloperPortalService {
    fileprivate override init() {
        super.init()
    }

    func fetchAccount(session: ALTAppleAPISession) async throws -> ALTAccount {
        let startedAt = AuthSubstageTraceStore.shared.begin("developer_portal_account")
        debugLog("[AuthStage] developer_portal_account start")
        do {
            let account = try await ALTAppleAPI.shared.fetchAccount(session: session)
            AuthSubstageTraceStore.shared.finish("developer_portal_account", startedAt: startedAt)
            debugLog("[AuthStage] developer_portal_account success")
            return account
        } catch {
            let nsError = error as NSError
            AuthSubstageTraceStore.shared.finish("developer_portal_account", startedAt: startedAt, error: nsError)
            debugLog("[AuthStage] developer_portal_account failure domain=\(nsError.domain) code=\(nsError.code)")
            throw stagedAuthError(error, stage: "developer_portal_account")
        }
    }

    func authenticate(
        appleID: String,
        password: String,
        anisetteData: ALTAnisetteData,
        xcodeVersion: String,
        anisetteDataProvider: (@Sendable () async throws -> ALTAnisetteData)? = nil,
        verificationHandler: DeveloperPortal.VerificationHandler? = nil
    ) async throws -> (ALTAccount, ALTAppleAPISession) {
        // Reaching this boundary proves Anisette data is already available. The SideSign
        // authenticate call below includes GSA/SRP, optional 2FA, token acquisition and
        // its internal account fetch, so we record that real boundary as apple_authenticate
        // rather than inventing narrower successful timings that SideSign does not expose.
        AuthSubstageTraceStore.shared.reset()
        AuthSubstageTraceStore.shared.markEvent("anisette_ready")
        let startedAt = AuthSubstageTraceStore.shared.begin("apple_authenticate")
        debugLog("[AuthStage] anisette success; gsa_srp start")

        let stagedVerificationHandler: DeveloperPortal.VerificationHandler? = verificationHandler.map { originalHandler in
            return { mode, completionHandler in
                let modeName: String
                switch mode {
                case .trustedDevice:
                    modeName = "trusted_device"
                case .sms:
                    modeName = "sms"
                case .voice:
                    modeName = "voice"
                }
                AuthSubstageTraceStore.shared.markEvent("two_factor_requested", metadata: modeName)
                debugLog("[AuthStage] two_factor requested mode=\(modeName)")
                originalHandler(mode) { action in
                    let actionName: String
                    switch action {
                    case .code:
                        actionName = "code_submitted"
                    case .requestPhone:
                        actionName = "delivery_requested"
                    case .cancel:
                        actionName = "cancelled"
                    }
                    AuthSubstageTraceStore.shared.markEvent("two_factor_action", metadata: actionName)
                    completionHandler(action)
                }
            }
        }

        do {
            let authSession = try await ALTAppleAPI.shared.authenticate(
                appleID: appleID,
                password: password,
                anisetteData: anisetteData,
                xcodeVersion: xcodeVersion,
                verificationHandler: stagedVerificationHandler
            )
            AuthSubstageTraceStore.shared.finish("apple_authenticate", startedAt: startedAt)
            debugLog("[AuthStage] gsa_srp success")
            return (authSession.account, authSession.session)
        } catch {
            let nsError = error as NSError
            AuthSubstageTraceStore.shared.finish("apple_authenticate", startedAt: startedAt, error: nsError)
            debugLog("[AuthStage] gsa_srp failure domain=\(nsError.domain) code=\(nsError.code)")
            throw stagedAuthError(error, stage: "gsa_srp")
        }
    }
    
    func authenticateWithToken(adsid: String, xcodeToken: String, anisetteData: ALTAnisetteData, xcodeVersion: String) async throws -> (ALTAccount, ALTAppleAPISession) {
        AuthSubstageTraceStore.shared.reset()
        AuthSubstageTraceStore.shared.markEvent("anisette_ready")
        let startedAt = AuthSubstageTraceStore.shared.begin("token_session")
        debugLog("[AuthStage] token_session start")
        do {
            let session = ALTAppleAPISession(dsid: adsid, authToken: xcodeToken, anisetteData: anisetteData, xcodeVersion: xcodeVersion)
            let account = try await fetchAccount(session: session)
            AuthSubstageTraceStore.shared.finish("token_session", startedAt: startedAt)
            debugLog("[AuthStage] token_session success")
            return (account, session)
        } catch {
            let nsError = error as NSError
            AuthSubstageTraceStore.shared.finish("token_session", startedAt: startedAt, error: nsError)
            debugLog("[AuthStage] token_session failure domain=\(nsError.domain) code=\(nsError.code)")
            throw error
        }
    }
}
