#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import hashlib

TARGET = Path("Dependencies/SideSign/Sources/DeveloperPortal/Authentication.swift")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def replace_first(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"{label}: anchor not found")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, new: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"{label}: start anchor not found")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"{label}: end anchor not found")
    return text[:start_index] + new + text[end_index:]


def main() -> int:
    if not TARGET.is_file():
        raise RuntimeError(f"missing SideSign source: {TARGET}")

    text = TARGET.read_text(encoding="utf-8")
    before = hashlib.sha256(text.encode("utf-8")).hexdigest()

    text = replace_once(
        text,
        "public extension DeveloperPortal {\n",
        """public typealias FreshAnisetteDataProvider = @Sendable () async throws -> AnisetteData

public extension DeveloperPortal {
""",
        "expose fresh Anisette provider type",
    )

    old_signature = """    func authenticate(appleID unsanitizedAppleID: String,
                      password: String,
                      anisetteData: AnisetteData,
                      xcodeVersion: String,
                      machinePassword: String? = nil,
                      verificationHandler: DeveloperPortal.VerificationHandler? = nil) async throws -> AuthSession
"""
    new_signature = """    func authenticate(appleID unsanitizedAppleID: String,
                      password: String,
                      anisetteData: AnisetteData,
                      xcodeVersion: String,
                      machinePassword: String? = nil,
                      anisetteDataProvider: FreshAnisetteDataProvider? = nil,
                      verificationHandler: DeveloperPortal.VerificationHandler? = nil) async throws -> AuthSession
"""
    compatibility_overload = """    // Keep the original protocol-compatible overload for callers that do not
    // provide an Anisette refresh callback.
    func authenticate(appleID unsanitizedAppleID: String,
                      password: String,
                      anisetteData: AnisetteData,
                      xcodeVersion: String,
                      machinePassword: String? = nil,
                      verificationHandler: DeveloperPortal.VerificationHandler? = nil) async throws -> AuthSession
    {
        try await authenticate(
            appleID: unsanitizedAppleID,
            password: password,
            anisetteData: anisetteData,
            xcodeVersion: xcodeVersion,
            machinePassword: machinePassword,
            anisetteDataProvider: nil,
            verificationHandler: verificationHandler
        )
    }

"""
    text = replace_once(
        text,
        old_signature,
        compatibility_overload + new_signature,
        "add provider-aware authenticate overload",
    )

    text = replace_once(
        text,
        """        let sanitizedAppleID = unsanitizedAppleID.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        debugLog("[SideSign] Starting authenticate...")
""",
        """        let sanitizedAppleID = unsanitizedAppleID.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let refreshAnisetteData: @Sendable () async throws -> AnisetteData = {
            if let provider = anisetteDataProvider {
                return try await provider()
            }
            return anisetteData
        }
        debugLog("[SideSign] Starting authenticate...")
""",
        "prepare per-operation Anisette refresh",
    )

    text = replace_once(
        text,
        """            try await requestTrustedDeviceTwoFactorCode(dsid: dsid, idmsToken: idmsToken, anisetteData: anisetteData, xcodeVersion: xcodeVersion, verificationHandler: verificationHandler)
""",
        """            try await requestTrustedDeviceTwoFactorCode(
                dsid: dsid,
                idmsToken: idmsToken,
                anisetteData: anisetteData,
                xcodeVersion: xcodeVersion,
                anisetteDataProvider: anisetteDataProvider,
                verificationHandler: verificationHandler
            )
""",
        "thread Anisette provider into trusted-device 2FA",
    )

    text = replace_first(
        text,
        """            return try await authenticate(appleID: unsanitizedAppleID, password: password, anisetteData: anisetteData, xcodeVersion: xcodeVersion, machinePassword: machinePassword, verificationHandler: verificationHandler)
""",
        """            let trustedDeviceAnisetteData = try await refreshAnisetteData()
            return try await authenticate(
                appleID: unsanitizedAppleID,
                password: password,
                anisetteData: trustedDeviceAnisetteData,
                xcodeVersion: xcodeVersion,
                machinePassword: machinePassword,
                anisetteDataProvider: anisetteDataProvider,
                verificationHandler: verificationHandler
            )
""",
        "refresh Anisette after trusted-device 2FA",
    )

    text = replace_once(
        text,
        """            try await requestSMSTwoFactorCode(mode: requestedMode, phoneID: initialPhoneID, dsid: dsid, idmsToken: idmsToken, anisetteData: anisetteData, xcodeVersion: xcodeVersion, verificationHandler: verificationHandler)
""",
        """            try await requestSMSTwoFactorCode(
                mode: requestedMode,
                phoneID: initialPhoneID,
                dsid: dsid,
                idmsToken: idmsToken,
                anisetteData: anisetteData,
                xcodeVersion: xcodeVersion,
                anisetteDataProvider: anisetteDataProvider,
                verificationHandler: verificationHandler
            )
""",
        "thread Anisette provider into SMS 2FA",
    )

    text = replace_once(
        text,
        """            return try await authenticate(appleID: unsanitizedAppleID, password: password, anisetteData: anisetteData, xcodeVersion: xcodeVersion, machinePassword: machinePassword, verificationHandler: verificationHandler)
""",
        """            let smsAnisetteData = try await refreshAnisetteData()
            return try await authenticate(
                appleID: unsanitizedAppleID,
                password: password,
                anisetteData: smsAnisetteData,
                xcodeVersion: xcodeVersion,
                machinePassword: machinePassword,
                anisetteDataProvider: anisetteDataProvider,
                verificationHandler: verificationHandler
            )
""",
        "refresh Anisette after SMS 2FA",
    )

    text = replace_between(
        text,
        "    private func requestTrustedDeviceTwoFactorCode(",
        "    private func sendPhonePut(",
        """    private func requestTrustedDeviceTwoFactorCode(dsid: String,
                                                   idmsToken: String,
                                                   anisetteData: AnisetteData,
                                                   xcodeVersion: String,
                                                   anisetteDataProvider: FreshAnisetteDataProvider?,
                                                   verificationHandler: VerificationHandler) async throws
    {
        debugLog("[SideSign] Requesting trusted device 2FA code...")
        let requestAnisetteData = try await anisetteDataProvider?() ?? anisetteData

        var request = makeTwoFactorRequest(
            url: Constants.URLs.trustedDevice,
            dsid: dsid,
            idmsToken: idmsToken,
            anisetteData: requestAnisetteData,
            xcodeVersion: xcodeVersion
        )
        request.httpMethod = "GET"

        let (data, response) = try await session.data(for: request)
        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.safeStatusCode ?? 0

        guard statusCode == HTTPStatusCodes.ok else {
            throw NSError(
                domain: "SideSign.GSA.trustedDevice",
                code: statusCode == 0 ? -3201 : statusCode,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple trusted-device verification request failed (HTTP \(statusCode))."
                ]
            )
        }

        var lastError: String?
        while true {
            let action: TwoFactorAction = try await withCheckedThrowingContinuation { continuation in
                verificationHandler(.trustedDevice(error: lastError)) { action in
                    continuation.resume(returning: action)
                }
            }

            switch action {
            case .code(let code):
                let verifyAnisetteData = try await anisetteDataProvider?() ?? anisetteData
                var verifyRequest = makeTwoFactorRequest(
                    url: Constants.URLs.grandSlamValidate,
                    dsid: dsid,
                    idmsToken: idmsToken,
                    anisetteData: verifyAnisetteData,
                    xcodeVersion: xcodeVersion
                )
                verifyRequest.setValue(code, forHTTPHeaderField: "security-code")

                let (verifyData, verifyResponse) = try await session.data(for: verifyRequest)
                let verifyHttpResponse = verifyResponse as? HTTPURLResponse
                let verifyStatusCode = verifyHttpResponse?.safeStatusCode ?? 0
                let verifyDictionary = parsePlistOrJSON(verifyData)
                let serviceError = parseServiceErrors(from: verifyDictionary).first
                let legacyErrorCode = integerValue(verifyDictionary?["ec"])
                let errorCode = serviceError?.code ?? legacyErrorCode ?? 0
                let errorMessage = serviceError?.message
                    ?? (verifyDictionary?["em"] as? String)
                    ?? ((verifyDictionary?["Status"] as? [String: any Sendable])?["em"] as? String)

                if errorCode == GrandSlamAuthErrorCodes.tooManyAttempts
                    || errorCode == GrandSlamAuthErrorCodes.tooManyCodesRequested
                    || errorCode == GrandSlamAuthErrorCodes.rateLimited
                    || verifyStatusCode == HTTPStatusCodes.tooManyRequests
                {
                    throw DeveloperPortalError.tooManyAttempts(
                        cause: errorMessage ?? "Too many verification code attempts. Please try again later."
                    )
                } else if errorCode == GrandSlamAuthErrorCodes.incorrectVerificationCode {
                    lastError = errorMessage ?? "Incorrect verification code. Please try again."
                    continue
                } else if errorCode != 0 {
                    throw NSError(
                        domain: "SideSign.GSA.trustedDevice.verify",
                        code: errorCode,
                        userInfo: [
                            NSLocalizedDescriptionKey: "Apple rejected the trusted-device verification code (\(errorCode))."
                        ]
                    )
                }

                guard verifyStatusCode == HTTPStatusCodes.ok else {
                    lastError = "Apple trusted-device verification returned HTTP \(verifyStatusCode)."
                    continue
                }

                return

            case .requestPhone(let targetPhoneID, let deliveryMode):
                try await requestSMSTwoFactorCode(
                    mode: deliveryMode.rawValue,
                    phoneID: targetPhoneID,
                    dsid: dsid,
                    idmsToken: idmsToken,
                    anisetteData: anisetteData,
                    xcodeVersion: xcodeVersion,
                    anisetteDataProvider: anisetteDataProvider,
                    verificationHandler: verificationHandler
                )
                return

            case .cancel:
                throw DeveloperPortalError.requiresTwoFactorAuthentication
            }
        }
    }

""",
        "refresh trusted-device 2FA Anisette",
    )

    text = replace_once(
        text,
        """    private func parseXMLUIAlertMessage(from data: Data) -> (title: String?, message: String?) {
""",
        """    private struct SMSServiceError: Error, Sendable {
        let code: Int
        let message: String
        let phoneNumbers: [TrustedPhoneNumber]
    }

    private func integerValue(_ value: Any?) -> Int? {
        if let value = value as? Int {
            return value
        }
        if let value = value as? NSNumber {
            return value.intValue
        }
        if let value = value as? String {
            return Int(value)
        }
        return nil
    }

    private func parseServiceErrors(from dictionary: [String: any Sendable]?) -> [(code: Int, message: String?)] {
        guard let dictionary else { return [] }

        var candidates: [[String: any Sendable]] = [dictionary]
        if let response = dictionary["Response"] as? [String: any Sendable] {
            candidates.append(response)
        }

        var errors: [(code: Int, message: String?)] = []
        for candidate in candidates {
            guard let rawErrors = candidate["serviceErrors"] as? [[String: any Sendable]] else {
                continue
            }
            for rawError in rawErrors {
                guard let code = integerValue(rawError["code"] ?? rawError["ec"]) else {
                    continue
                }
                let message = (rawError["message"] as? String)
                    ?? (rawError["em"] as? String)
                    ?? (rawError["title"] as? String)
                errors.append((code, message))
            }
        }
        return errors
    }

    private func isActiveSMSChallenge(
        _ dictionary: [String: any Sendable]?,
        requestedPhoneID: String
    ) -> Bool {
        guard let dictionary else { return false }
        let payload = (dictionary["Response"] as? [String: any Sendable]) ?? dictionary

        guard (payload["type"] as? String) == "verification",
              (payload["mode"] as? String) == "sms",
              (payload["authenticationType"] as? String) == "hsa2",
              let trustedPhone = payload["trustedPhoneNumber"] as? [String: any Sendable],
              let trustedPhoneID = (trustedPhone["id"] as? CustomStringConvertible)?.description,
              trustedPhoneID == requestedPhoneID,
              let trustedPhones = payload["trustedPhoneNumbers"] as? [[String: any Sendable]],
              trustedPhones.contains(where: {
                  (($0["id"] as? CustomStringConvertible)?.description ?? "") == requestedPhoneID
              }),
              let securityCode = payload["securityCode"] as? [String: any Sendable],
              integerValue(securityCode["length"]) == 6,
              (payload["tooManyCodesSent"] as? Bool) == false,
              (payload["tooManyCodesValidated"] as? Bool) == false,
              (payload["securityCodeLocked"] as? Bool) == false,
              (payload["securityCodeCooldown"] as? Bool) == false
        else {
            return false
        }

        return true
    }

    private func fetchTrustedPhoneNumbers(
        dsid: String,
        idmsToken: String,
        anisetteData: AnisetteData,
        xcodeVersion: String,
        anisetteDataProvider: FreshAnisetteDataProvider?
    ) async throws -> [TrustedPhoneNumber] {
        let requestAnisetteData = try await anisetteDataProvider?() ?? anisetteData
        var request = makeTwoFactorRequest(
            url: URL(string: "https://gsa.apple.com/auth")!,
            dsid: dsid,
            idmsToken: idmsToken,
            anisetteData: requestAnisetteData,
            xcodeVersion: xcodeVersion
        )
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.cachePolicy = .reloadIgnoringLocalCacheData

        let (data, response) = try await session.data(for: request)
        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.safeStatusCode ?? 0
        let contentType = httpResponse?.value(forHTTPHeaderField: "Content-Type") ?? "unknown"

        guard statusCode == HTTPStatusCodes.ok, let responseDictionary = parsePlistOrJSON(data) else {
            throw NSError(
                domain: "SideSign.GSA.trustedPhones",
                code: statusCode == 0 ? -3001 : statusCode,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple trusted-phone discovery failed (HTTP \(statusCode), content-type=\(contentType), bytes=\(data.count))."
                ]
            )
        }

        if let serviceError = parseServiceErrors(from: responseDictionary).first {
            throw NSError(
                domain: "SideSign.GSA.trustedPhones",
                code: serviceError.code,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple trusted-phone discovery was rejected (\(serviceError.code))."
                ]
            )
        }

        let numbers = parseTrustedPhoneNumbers(from: responseDictionary)
        guard !numbers.isEmpty else {
            throw NSError(
                domain: "SideSign.GSA.trustedPhones",
                code: -3002,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple trusted-phone discovery returned no selectable phone numbers."
                ]
            )
        }

        debugLog("[SideSign] trusted-phone discovery succeeded: count=\(numbers.count)")
        return numbers
    }

    private func parseXMLUIAlertMessage(from data: Data) -> (title: String?, message: String?) {
""",
        "insert trusted-phone discovery and service-error helpers",
    )

    text = replace_between(
        text,
        "    private func sendPhonePut(",
        "    private func requestSMSTwoFactorCode(",
        """    private func sendPhonePut(mode requestedMode: String,
                               phoneID requestedPhoneID: String? = nil,
                               knownPhoneNumbers: [TrustedPhoneNumber] = [],
                               dsid: String,
                               idmsToken: String,
                               anisetteData: AnisetteData,
                               xcodeVersion: String,
                               anisetteDataProvider: FreshAnisetteDataProvider?) async throws -> (phoneID: String, activeMode: String, phoneNumbers: [TrustedPhoneNumber], statusCode: Int)
    {
        guard let requestedPhoneID, let phoneNumberID = Int(requestedPhoneID) else {
            throw NSError(
                domain: "SideSign.GSA.sms",
                code: -3101,
                userInfo: [
                    NSLocalizedDescriptionKey: "SMS verification requires a trusted phone ID returned by Apple."
                ]
            )
        }

        let requestAnisetteData = try await anisetteDataProvider?() ?? anisetteData
        var request = makeTwoFactorRequest(
            url: URL(string: Constants.URLs.phoneBase)!,
            dsid: dsid,
            idmsToken: idmsToken,
            anisetteData: requestAnisetteData,
            xcodeVersion: xcodeVersion
        )
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.httpBody = try JSONSerialization.data(
            withJSONObject: [
                "phoneNumber": ["id": phoneNumberID],
                "mode": requestedMode
            ],
            options: []
        )

        let (data, response) = try await session.data(for: request)
        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.safeStatusCode ?? 0
        let contentType = httpResponse?.value(forHTTPHeaderField: "Content-Type") ?? "unknown"
        let responseDictionary = parsePlistOrJSON(data)
        let responseSummary = "HTTP \(statusCode), content-type=\(contentType), bytes=\(data.count)"
        verboseLog("[SideSign] sendPhonePut response summary: \(responseSummary)")

        let serviceErrors = parseServiceErrors(from: responseDictionary)
        if let serviceError = serviceErrors.first {
            let message = serviceError.message
                ?? "Apple did not accept the SMS verification request."
            if serviceError.code == -28248
                || serviceError.code == -22979
                || serviceError.code == -22981
            {
                throw SMSServiceError(
                    code: serviceError.code,
                    message: message,
                    phoneNumbers: knownPhoneNumbers
                )
            }
            throw NSError(
                domain: "SideSign.GSA.sms",
                code: serviceError.code,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple rejected the SMS request (\(serviceError.code))."
                ]
            )
        }

        let legacyErrorCode = integerValue(responseDictionary?["ec"])
        if let legacyErrorCode, legacyErrorCode != 0 {
            let message = (responseDictionary?["em"] as? String)
                ?? "Apple rejected the SMS verification request."
            if legacyErrorCode == -28248
                || legacyErrorCode == -22979
                || legacyErrorCode == -22981
            {
                throw SMSServiceError(
                    code: legacyErrorCode,
                    message: message,
                    phoneNumbers: knownPhoneNumbers
                )
            }
            throw NSError(
                domain: "SideSign.GSA.sms",
                code: legacyErrorCode,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple rejected the SMS request (\(legacyErrorCode))."
                ]
            )
        }

        let activeChallenge = statusCode == 412
            && isActiveSMSChallenge(responseDictionary, requestedPhoneID: requestedPhoneID)
        guard statusCode == HTTPStatusCodes.ok || activeChallenge else {
            throw NSError(
                domain: "SideSign.GSA.sms",
                code: statusCode == 0 ? -3102 : statusCode,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple SMS request did not produce a valid verification challenge (\(responseSummary))."
                ]
            )
        }

        var phoneNumbers = parseTrustedPhoneNumbers(from: responseDictionary)
        if phoneNumbers.isEmpty {
            phoneNumbers = knownPhoneNumbers
        }
        guard phoneNumbers.contains(where: { $0.id == requestedPhoneID }) else {
            throw NSError(
                domain: "SideSign.GSA.sms",
                code: -3103,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple SMS response did not confirm the requested trusted phone ID."
                ]
            )
        }

        let phoneDictionary = (responseDictionary?["phoneNumber"] as? [String: any Sendable])
            ?? (responseDictionary?["trustedPhoneNumber"] as? [String: any Sendable])
        if let responsePhoneID = (phoneDictionary?["id"] as? CustomStringConvertible)?.description,
           responsePhoneID != requestedPhoneID
        {
            throw NSError(
                domain: "SideSign.GSA.sms",
                code: -3104,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple SMS response identified a different trusted phone ID."
                ]
            )
        }

        let number = (phoneDictionary?["numberWithDialCode"] as? String)
            ?? (phoneDictionary?["obfuscatedNumber"] as? String)
            ?? (phoneDictionary?["lastTwoDigits"] as? String).map { "••\($0)" }
            ?? phoneNumbers.first(where: { $0.id == requestedPhoneID })?.number
            ?? "Phone \(requestedPhoneID)"

        if let index = phoneNumbers.firstIndex(where: { $0.id == requestedPhoneID }),
           !number.isEmpty
        {
            phoneNumbers[index] = TrustedPhoneNumber(id: requestedPhoneID, number: number)
        }

        let activeMode = (phoneDictionary?["mode"] as? String) ?? requestedMode
        debugLog("[SideSign] sendPhonePut accepted: phoneId=\(requestedPhoneID), mode=\(activeMode), status=\(statusCode), phoneCount=\(phoneNumbers.count)")
        return (requestedPhoneID, activeMode, phoneNumbers, statusCode)
    }

""",
        "replace SMS send with strict iLoader-compatible request",
    )

    text = replace_between(
        text,
        "    private func requestSMSTwoFactorCode(",
        "    private func makeTwoFactorRequest(",
        """    private func requestSMSTwoFactorCode(mode initialRequestedMode: String = "sms",
                                         phoneID initialPhoneID: String? = nil,
                                         knownPhoneNumbers: [TrustedPhoneNumber] = [],
                                         dsid: String,
                                         idmsToken: String,
                                         anisetteData: AnisetteData,
                                         xcodeVersion: String,
                                         anisetteDataProvider: FreshAnisetteDataProvider?,
                                         verificationHandler: VerificationHandler) async throws
    {
        let discoveredPhoneNumbers = try await fetchTrustedPhoneNumbers(
            dsid: dsid,
            idmsToken: idmsToken,
            anisetteData: anisetteData,
            xcodeVersion: xcodeVersion,
            anisetteDataProvider: anisetteDataProvider
        )

        let selectedPhoneID: String
        if let initialPhoneID,
           discoveredPhoneNumbers.contains(where: { $0.id == initialPhoneID })
        {
            selectedPhoneID = initialPhoneID
        } else if let first = discoveredPhoneNumbers.first {
            selectedPhoneID = first.id
        } else {
            throw NSError(
                domain: "SideSign.GSA.trustedPhones",
                code: -3003,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple did not return a selectable trusted phone number."
                ]
            )
        }

        var currentMode = initialRequestedMode == "voice" ? "voice" : "sms"
        var phoneID = selectedPhoneID
        var activeMode = currentMode
        var phoneNumbers = discoveredPhoneNumbers
        var statusCode = 0
        var lastError: String?

        do {
            let result = try await sendPhonePut(
                mode: currentMode,
                phoneID: phoneID,
                knownPhoneNumbers: phoneNumbers,
                dsid: dsid,
                idmsToken: idmsToken,
                anisetteData: anisetteData,
                xcodeVersion: xcodeVersion,
                anisetteDataProvider: anisetteDataProvider
            )
            phoneID = result.phoneID
            activeMode = result.activeMode
            phoneNumbers = result.phoneNumbers
            statusCode = result.statusCode
        } catch let serviceError as SMSServiceError
        {
            switch serviceError.code {
            case -28248:
                lastError = serviceError.message
                activeMode = currentMode
                phoneNumbers = serviceError.phoneNumbers.isEmpty ? phoneNumbers : serviceError.phoneNumbers
            case -22979, -22981:
                // Apple says the previous code may still be valid. Keep the
                // verification UI open and do not send a duplicate SMS.
                lastError = serviceError.message
                activeMode = currentMode
                phoneNumbers = serviceError.phoneNumbers.isEmpty ? phoneNumbers : serviceError.phoneNumbers
            default:
                throw serviceError
            }
        }

        while true {
            let twoFactorMode: TwoFactorMode = (activeMode == "voice")
                ? .voice(phoneNumbers: phoneNumbers, activeID: phoneID, error: lastError)
                : .sms(phoneNumbers: phoneNumbers, activeID: phoneID, error: lastError)

            let action: TwoFactorAction = try await withCheckedThrowingContinuation { continuation in
                verificationHandler(twoFactorMode) { action in
                    continuation.resume(returning: action)
                }
            }

            switch action {
            case .code(let code):
                let verifyAnisetteData = try await anisetteDataProvider?() ?? anisetteData
                var verifyRequest = makeTwoFactorRequest(
                    url: URL(string: Constants.URLs.phoneBase + "/securitycode")!,
                    dsid: dsid,
                    idmsToken: idmsToken,
                    anisetteData: verifyAnisetteData,
                    xcodeVersion: xcodeVersion
                )
                verifyRequest.httpMethod = "POST"
                verifyRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
                verifyRequest.setValue("application/json", forHTTPHeaderField: "Accept")
                verifyRequest.cachePolicy = .reloadIgnoringLocalCacheData
                let phoneNumberID = Int(phoneID) ?? -1
                guard phoneNumberID > 0 else {
                    throw NSError(
                        domain: "SideSign.GSA.sms.verify",
                        code: -3201,
                        userInfo: [
                            NSLocalizedDescriptionKey: "Apple verification requires a confirmed trusted phone ID."
                        ]
                    )
                }
                verifyRequest.httpBody = try JSONSerialization.data(
                    withJSONObject: [
                        "securityCode": ["code": code],
                        "phoneNumber": ["id": phoneNumberID],
                        "mode": activeMode
                    ],
                    options: []
                )

                let (verifyData, verifyResponse) = try await session.data(for: verifyRequest)
                let verifyHttpResponse = verifyResponse as? HTTPURLResponse
                let verifyStatusCode = verifyHttpResponse?.safeStatusCode ?? 0
                let verifyDictionary = parsePlistOrJSON(verifyData)
                let serviceError = parseServiceErrors(from: verifyDictionary).first
                let legacyErrorCode = integerValue(verifyDictionary?["ec"])
                let errorCode = serviceError?.code ?? legacyErrorCode ?? 0
                let errorMessage = serviceError?.message
                    ?? (verifyDictionary?["em"] as? String)
                    ?? ((verifyDictionary?["Status"] as? [String: any Sendable])?["em"] as? String)
                    ?? "Apple rejected the verification code."

                if errorCode == GrandSlamAuthErrorCodes.incorrectVerificationCode {
                    lastError = errorMessage
                    continue
                }

                if errorCode == GrandSlamAuthErrorCodes.tooManyAttempts
                    || errorCode == GrandSlamAuthErrorCodes.tooManyCodesRequested
                    || errorCode == GrandSlamAuthErrorCodes.rateLimited
                    || verifyStatusCode == HTTPStatusCodes.tooManyRequests
                {
                    throw DeveloperPortalError.tooManyAttempts(cause: errorMessage)
                }

                if errorCode != 0 {
                    throw NSError(
                        domain: "SideSign.GSA.sms.verify",
                        code: errorCode,
                        userInfo: [
                            NSLocalizedDescriptionKey: "Apple rejected the SMS verification request (\(errorCode))."
                        ]
                    )
                }

                guard verifyStatusCode == HTTPStatusCodes.ok else {
                    lastError = "Apple SMS verification returned HTTP \(verifyStatusCode)."
                    continue
                }

                let hasPEToken = verifyHttpResponse?.allHeaderFields.keys.contains(where: {
                    ($0 as? String)?.lowercased() == "x-apple-pe-token"
                }) == true
                guard hasPEToken else {
                    lastError = "Apple accepted the request but did not return a verification session token."
                    continue
                }

                return

            case .requestPhone(let targetPhoneID, let deliveryMode):
                let refreshedPhoneNumbers = try await fetchTrustedPhoneNumbers(
                    dsid: dsid,
                    idmsToken: idmsToken,
                    anisetteData: anisetteData,
                    xcodeVersion: xcodeVersion,
                    anisetteDataProvider: anisetteDataProvider
                )
                guard refreshedPhoneNumbers.contains(where: { $0.id == targetPhoneID }) else {
                    lastError = "Apple did not confirm the selected trusted phone number."
                    phoneNumbers = refreshedPhoneNumbers
                    continue
                }

                currentMode = deliveryMode.rawValue
                phoneID = targetPhoneID
                phoneNumbers = refreshedPhoneNumbers
                activeMode = currentMode
                do {
                    let result = try await sendPhonePut(
                        mode: currentMode,
                        phoneID: phoneID,
                        knownPhoneNumbers: phoneNumbers,
                        dsid: dsid,
                        idmsToken: idmsToken,
                        anisetteData: anisetteData,
                        xcodeVersion: xcodeVersion,
                        anisetteDataProvider: anisetteDataProvider
                    )
                    phoneID = result.phoneID
                    activeMode = result.activeMode
                    phoneNumbers = result.phoneNumbers
                    statusCode = result.statusCode
                    lastError = nil
                } catch let serviceError as SMSServiceError {
                    if serviceError.code == -28248
                        || serviceError.code == -22979
                        || serviceError.code == -22981
                    {
                        lastError = serviceError.message
                        phoneNumbers = serviceError.phoneNumbers.isEmpty ? phoneNumbers : serviceError.phoneNumbers
                        continue
                    }
                    throw serviceError
                }

            case .cancel:
                throw DeveloperPortalError.requiresTwoFactorAuthentication
            }
        }
    }

""",
        "replace SMS 2FA state machine",
    )

    after = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if before == after:
        raise RuntimeError("transform produced no change")

    TARGET.write_text(text, encoding="utf-8")
    print("P0 trusted-phone, fresh-Anisette, strict-412, and serviceErrors transforms applied")
    print(f"source_sha256={before}")
    print(f"patched_sha256={after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
