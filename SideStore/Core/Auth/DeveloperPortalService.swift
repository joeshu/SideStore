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

extension Notification.Name {
    static let sideStoreAuthTraceDidUpdate = Notification.Name("SideStoreAuthTraceDidUpdate")
}

/// Process-local, metadata-only authentication performance trace.
/// Never records Apple ID, password, 2FA values, Anisette payloads, DSID/ADSID,
/// tokens or session material.
final class SideStoreAuthPerformanceTrace {
    static let shared = SideStoreAuthPerformanceTrace()

    private let lock = NSLock()
    private var flowStartedAt: CFAbsoluteTime?
    private var stageStartedAt: [String: CFAbsoluteTime] = [:]
    private var latestDurationsMS: [String: Int] = [:]

    private init() {}

    func reset() {
        lock.lock()
        flowStartedAt = CFAbsoluteTimeGetCurrent()
        stageStartedAt.removeAll(keepingCapacity: true)
        latestDurationsMS.removeAll(keepingCapacity: true)
        lock.unlock()
        post(stage: "sign_in", state: "started", durationMS: nil, totalMS: 0)
    }

    func begin(_ stage: String) {
        let now = CFAbsoluteTimeGetCurrent()
        lock.lock()
        if flowStartedAt == nil { flowStartedAt = now }
        stageStartedAt[stage] = now
        let totalMS = elapsedMS(from: flowStartedAt, to: now)
        lock.unlock()
        debugLog("[AuthTrace] stage=\(stage) state=start total_ms=\(totalMS)")
        post(stage: stage, state: "started", durationMS: nil, totalMS: totalMS)
    }

    @discardableResult
    func finish(_ stage: String, success: Bool) -> Int? {
        let now = CFAbsoluteTimeGetCurrent()
        lock.lock()
        let durationMS = elapsedMS(from: stageStartedAt.removeValue(forKey: stage), to: now)
        if let durationMS { latestDurationsMS[stage] = durationMS }
        let totalMS = elapsedMS(from: flowStartedAt, to: now)
        lock.unlock()

        let state = success ? "success" : "failure"
        debugLog("[AuthTrace] stage=\(stage) state=\(state) duration_ms=\(durationMS ?? -1) total_ms=\(totalMS)")
        post(stage: stage, state: state, durationMS: durationMS, totalMS: totalMS)
        return durationMS
    }

    func complete() {
        let now = CFAbsoluteTimeGetCurrent()
        lock.lock()
        let totalMS = elapsedMS(from: flowStartedAt, to: now)
        flowStartedAt = nil
        stageStartedAt.removeAll(keepingCapacity: true)
        lock.unlock()
        debugLog("[AuthTrace] stage=sign_in state=success total_ms=\(totalMS)")
        post(stage: "sign_in", state: "success", durationMS: nil, totalMS: totalMS)
    }

    func snapshot() -> [String: Int] {
        lock.lock()
        defer { lock.unlock() }
        return latestDurationsMS
    }

    private func elapsedMS(from start: CFAbsoluteTime?, to end: CFAbsoluteTime) -> Int {
        guard let start else { return 0 }
        return max(0, Int(((end - start) * 1000.0).rounded()))
    }

    private func post(stage: String, state: String, durationMS: Int?, totalMS: Int) {
        var userInfo: [String: Any] = [
            "stage": stage,
            "state": state,
            "total_ms": totalMS
        ]
        if let durationMS { userInfo["duration_ms"] = durationMS }
        NotificationCenter.default.post(name: .sideStoreAuthTraceDidUpdate, object: nil, userInfo: userInfo)
    }
}

private func stagedAuthError(_ error: Error, stage: String) -> NSError {
    let nsError = error as NSError
    var userInfo = nsError.userInfo
    userInfo[sideStoreAuthStageKey] = stage
    userInfo[sideStoreAuthOriginalDomainKey] = nsError.domain
    userInfo[sideStoreAuthOriginalCodeKey] = nsError.code
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
        SideStoreAuthPerformanceTrace.shared.begin("developer_portal_account")
        debugLog("[AuthStage] developer_portal_account start")
        do {
            let account = try await ALTAppleAPI.shared.fetchAccount(session: session)
            SideStoreAuthPerformanceTrace.shared.finish("developer_portal_account", success: true)
            debugLog("[AuthStage] developer_portal_account success")
            return account
        } catch {
            SideStoreAuthPerformanceTrace.shared.finish("developer_portal_account", success: false)
            let nsError = error as NSError
            debugLog("[AuthStage] developer_portal_account failure domain=\(nsError.domain) code=\(nsError.code)")
            throw stagedAuthError(error, stage: "developer_portal_account")
        }
    }

    func authenticate(appleID: String, password: String, anisetteData: ALTAnisetteData, xcodeVersion: String, verificationHandler: DeveloperPortal.VerificationHandler?) async throws -> (ALTAccount, ALTAppleAPISession) {
        SideStoreAuthPerformanceTrace.shared.begin("gsa_srp")
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
                debugLog("[AuthStage] two_factor requested mode=\(modeName)")
                originalHandler(mode, completionHandler)
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
            SideStoreAuthPerformanceTrace.shared.finish("gsa_srp", success: true)
            debugLog("[AuthStage] gsa_srp success")
            return (authSession.account, authSession.session)
        } catch {
            SideStoreAuthPerformanceTrace.shared.finish("gsa_srp", success: false)
            let nsError = error as NSError
            debugLog("[AuthStage] gsa_srp failure domain=\(nsError.domain) code=\(nsError.code)")
            throw stagedAuthError(error, stage: "gsa_srp")
        }
    }

    func authenticateWithToken(adsid: String, xcodeToken: String, anisetteData: ALTAnisetteData, xcodeVersion: String) async throws -> (ALTAccount, ALTAppleAPISession) {
        SideStoreAuthPerformanceTrace.shared.begin("token_session")
        debugLog("[AuthStage] token_session start")
        do {
            let session = ALTAppleAPISession(dsid: adsid, authToken: xcodeToken, anisetteData: anisetteData, xcodeVersion: xcodeVersion)
            let account = try await fetchAccount(session: session)
            SideStoreAuthPerformanceTrace.shared.finish("token_session", success: true)
            debugLog("[AuthStage] token_session success")
            return (account, session)
        } catch {
            SideStoreAuthPerformanceTrace.shared.finish("token_session", success: false)
            throw error
        }
    }
}
