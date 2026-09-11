#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import hashlib
import sys

TARGET = Path("Dependencies/SideSign/Sources/DeveloperPortal/Authentication.swift")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if not TARGET.is_file():
        raise RuntimeError(f"missing SideSign source: {TARGET}")

    text = TARGET.read_text(encoding="utf-8")
    before = hashlib.sha256(text.encode("utf-8")).hexdigest()

    old_client_dictionary = '''        let clientDictionary: [String: any Sendable] = [
            "bootstrap": true,
            "icscrec": true,
            "pbe": false,
            "prkgen": true,
            "svct": Constants.grandSlamService,
            "loc": anisetteData.locale.identifier.components(separatedBy: "@").first ?? "en_US",
            "X-Apple-Locale": anisetteData.locale.identifier.components(separatedBy: "@").first ?? "en_US",
            "X-Apple-I-MD": anisetteData.oneTimePassword,
            "X-Apple-I-MD-M": anisetteData.machineID,
            "X-Mme-Device-Id": anisetteData.deviceUniqueIdentifier,
            "X-Apple-I-MD-LU": anisetteData.localUserID,
            "X-Apple-I-MD-RINFO": anisetteData.routingInfo,
            "X-Apple-I-SRL-NO": anisetteData.deviceSerialNumber,
            "X-Apple-I-Client-Time": formatDate(anisetteData.date),
            "X-Apple-I-TimeZone": anisetteData.timeZone.abbreviation(for: anisetteData.date) ?? "PST"
        ]
'''
    new_client_dictionary = '''        // Match iLoader 2.3.3's GrandSlam CPD shape and value types.
        // The base request headers carry the Xcode/App-Info fingerprint; CPD only
        // contains the three device identity fields used by iLoader.
        let clientDictionary: [String: any Sendable] = [
            "bootstrap": "true",
            "icscrec": "true",
            "loc": "en_US",
            "pbe": "false",
            "prkgen": "true",
            "svct": Constants.grandSlamService,
            "X-Mme-Device-Id": anisetteData.deviceUniqueIdentifier,
            "X-Apple-I-MD": anisetteData.oneTimePassword,
            "X-Apple-I-MD-M": anisetteData.machineID
        ]
'''
    text = replace_once(text, old_client_dictionary, new_client_dictionary, "align GrandSlam CPD with iLoader 2.3.3")
    text = replace_once(
        text,
        '        let initResponse = try await sendAuthenticationRequest(parameters: initParameters, anisetteData: anisetteData)',
        '''        let initResponse = try await sendAuthenticationRequest(
            parameters: initParameters,
            anisetteData: anisetteData,
            xcodeVersion: xcodeVersion,
            phase: "init"
        )''',
        "thread xcodeVersion into SRP init",
    )

    text = replace_once(
        text,
        '        let completeResponseDictionary = try await sendAuthenticationRequest(parameters: completeParameters, anisetteData: anisetteData)',
        '''        let completeResponseDictionary = try await sendAuthenticationRequest(
            parameters: completeParameters,
            anisetteData: anisetteData,
            xcodeVersion: xcodeVersion,
            closeConnection: true,
            phase: "complete"
        )''',
        "thread xcodeVersion/Connection-close into SRP complete",
    )

    text = replace_once(
        text,
        '            let fetchedToken = try await fetchAuthToken(app: app, parameters: appTokensParameters, sessionKey: sessionKey, anisetteData: anisetteData)',
        '''            let fetchedToken = try await fetchAuthToken(
                app: app,
                parameters: appTokensParameters,
                sessionKey: sessionKey,
                anisetteData: anisetteData,
                xcodeVersion: xcodeVersion
            )''',
        "thread xcodeVersion into app-token request",
    )

    old_request_start = '''    func sendAuthenticationRequest(parameters requestParameters: [String: any Sendable], anisetteData: AnisetteData) async throws -> [String: any Sendable] {
        let requestURL = Constants.URLs.grandSlamAuth
'''
    new_request_start = '''    private func resolveGrandSlamServiceURL(anisetteData: AnisetteData, xcodeVersion: String?) async throws -> URL {
        var request = URLRequest(url: Constants.URLs.grandSlamLookup)
        request.httpMethod = "GET"
        request.setValue("text/x-xml-plist", forHTTPHeaderField: "Accept")
        request.setValue(anisetteData.deviceDescription, forHTTPHeaderField: "X-MMe-Client-Info")
        request.setValue(Constants.userAgent, forHTTPHeaderField: "User-Agent")
        request.setValue("27.0 (27A5218g)", forHTTPHeaderField: "X-Xcode-Version")
        request.setValue(Constants.authApp, forHTTPHeaderField: "X-Apple-App-Info")
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("close", forHTTPHeaderField: "Connection")

        let (data, response) = try await session.data(for: request)
        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.statusCode ?? 0
        let contentType = httpResponse?.value(forHTTPHeaderField: "Content-Type") ?? "unknown"

        guard (200...299).contains(statusCode), !data.isEmpty else {
            debugLog("[SideSign] GrandSlam lookup failed: HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)")
            throw ServerError.badServerResponse(
                reason: "GrandSlam lookup failed (HTTP \\(statusCode))",
                jsonPayload: "contentType=\\(contentType), bytes=\\(data.count)"
            )
        }

        guard let lookup = parsePlistOrJSON(data),
              let urls = lookup["urls"] as? [String: any Sendable],
              let service = urls["gsService"] as? String,
              let resolvedURL = URL(string: service)
        else {
            debugLog("[SideSign] GrandSlam lookup response could not resolve gsService: HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)")
            throw ServerError.invalidResponseFormat(
                rawPayload: "GrandSlam lookup: HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)"
            )
        }

        debugLog("[SideSign] Resolved GrandSlam gsService host: \\(resolvedURL.host ?? \"unknown\")")
        return resolvedURL
    }

    func sendAuthenticationRequest(
        parameters requestParameters: [String: any Sendable],
        anisetteData: AnisetteData,
        xcodeVersion: String? = nil,
        closeConnection: Bool = false,
        phase: String = "unknown"
    ) async throws -> [String: any Sendable] {
        let requestURL: URL
        do {
            requestURL = try await resolveGrandSlamServiceURL(anisetteData: anisetteData, xcodeVersion: xcodeVersion)
        } catch {
            let nsError = error as NSError
            debugLog("[SideSign] GrandSlam lookup unavailable (\\(nsError.domain):\\(nsError.code)); falling back to static GsService2")
            requestURL = Constants.URLs.grandSlamAuth
        }
'''
    text = replace_once(text, old_request_start, new_request_start, "insert dynamic GrandSlam URL lookup")

    old_headers = '''        let headers: [String: String] = [
            "Content-Type": "text/x-xml-plist",
            "X-MMe-Client-Info": anisetteData.deviceDescription,
            "Accept": "*/*",
            "User-Agent": Constants.userAgent
        ]
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
'''
    new_headers = '''        let headers: [String: String] = [
            "Content-Type": "text/x-xml-plist",
            "X-MMe-Client-Info": anisetteData.deviceDescription,
            "Accept": "text/x-xml-plist",
            "User-Agent": Constants.userAgent,
            "X-Apple-App-Info": Constants.authApp
        ]
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
        request.setValue("27.0 (27A5218g)", forHTTPHeaderField: "X-Xcode-Version")
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("close", forHTTPHeaderField: "Connection")
        debugLog("[SideSign] GSA phase=\(phase), xcode=27.0 (27A5218g), requestedClose=\(closeConnection)")
'''
    text = replace_once(text, old_headers, new_headers, "align GrandSlam request headers")

    old_diagnostics = '''        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.statusCode ?? 0

        guard !data.isEmpty else {
            debugLog("[SideSign] Auth endpoint returned 0 bytes (HTTP \\(statusCode))")
            throw ServerError.badServerResponse(reason: "Auth endpoint returned empty response (0 bytes)", jsonPayload: "0 bytes")
        }

        guard let responseDictionary = parsePlistOrJSON(data) else {
            let rawStr = String(data: data, encoding: .utf8) ?? data.hexEncodedString()
            debugLog("[SideSign] Auth endpoint returned invalid response format: \\(rawStr)")
            throw ServerError.invalidResponseFormat(rawPayload: rawStr)
        }

        let dictionary = (responseDictionary["Response"] as? [String: any Sendable]) ?? responseDictionary
        guard let status = dictionary["Status"] as? [String: any Sendable] else {
            let rawStr = prettyJSONString(from: responseDictionary)
            debugLog("[SideSign] Auth endpoint response missing 'Status': \\(rawStr)")
            throw ServerError.missingKey(key: "Status", jsonPayload: rawStr)
        }
'''
    new_diagnostics = '''        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.statusCode ?? 0
        let contentType = httpResponse?.value(forHTTPHeaderField: "Content-Type") ?? "unknown"

        guard !data.isEmpty else {
            debugLog("[SideSign] Auth endpoint returned 0 bytes: HTTP \\(statusCode), contentType=\\(contentType)")
            throw ServerError.badServerResponse(
                reason: "Auth endpoint returned empty response (HTTP \\(statusCode))",
                jsonPayload: "contentType=\\(contentType), bytes=0"
            )
        }

        guard let responseDictionary = parsePlistOrJSON(data) else {
            debugLog("[SideSign] Auth endpoint returned invalid response format: HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)")
            throw ServerError.invalidResponseFormat(
                rawPayload: "HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)"
            )
        }

        let dictionary = (responseDictionary["Response"] as? [String: any Sendable]) ?? responseDictionary
        guard let status = dictionary["Status"] as? [String: any Sendable] else {
            debugLog("[SideSign] Auth endpoint response missing Status: HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)")
            throw ServerError.missingKey(
                key: "Status",
                jsonPayload: "HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)"
            )
        }
'''
    text = replace_once(text, old_diagnostics, new_diagnostics, "make auth diagnostics credential-safe")

    old_network_catch = '''        } catch {
            debugLog("[SideSign] sendAuthenticationRequest network error: \\(error)")
            throw error
        }
'''
    new_network_catch = '''        } catch {
            let nsError = error as NSError
            debugLog("[SideSign] GSA phase=\\(phase) network error: \\(nsError.domain):\\(nsError.code)")
            throw NSError(
                domain: "SideSign.GSA.\\(phase)",
                code: -1000,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple GSA \\(phase) network request failed (\\(nsError.domain):\\(nsError.code)).",
                    NSUnderlyingErrorKey: nsError
                ]
            )
        }
'''
    text = replace_once(text, old_network_catch, new_network_catch, "surface GSA network phase")

    diagnostic_error_replacements = [
        (
            '''            throw ServerError.badServerResponse(
                reason: "Auth endpoint returned empty response (HTTP \\(statusCode))",
                jsonPayload: "contentType=\\(contentType), bytes=0"
            )''',
            '''            throw NSError(
                domain: "SideSign.GSA.\\(phase)",
                code: -1001,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple GSA \\(phase) returned an empty response (HTTP \\(statusCode), bytes=0)."
                ]
            )''',
            "surface empty GSA response",
        ),
        (
            '''            throw ServerError.invalidResponseFormat(
                rawPayload: "HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)"
            )''',
            '''            throw NSError(
                domain: "SideSign.GSA.\\(phase)",
                code: -1002,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple GSA \\(phase) returned a non-plist response (HTTP \\(statusCode), bytes=\\(data.count))."
                ]
            )''',
            "surface GSA response format",
        ),
        (
            '''            throw ServerError.missingKey(
                key: "Status",
                jsonPayload: "HTTP \\(statusCode), contentType=\\(contentType), bytes=\\(data.count)"
            )''',
            '''            throw NSError(
                domain: "SideSign.GSA.\\(phase)",
                code: -1003,
                userInfo: [
                    NSLocalizedDescriptionKey: "Apple GSA \\(phase) response omitted Status (HTTP \\(statusCode), bytes=\\(data.count))."
                ]
            )''',
            "surface missing GSA status",
        ),
    ]
    for old, new, label in diagnostic_error_replacements:
        text = replace_once(text, old, new, label)

    phase_error_replacements = [
        (
            '            throw ServerError.badServerResponse(reason: "Auth init response missing c/s/i/B parameters", jsonPayload: payload)',
            '            throw NSError(domain: "SideSign.GSA.init", code: -2001, userInfo: [NSLocalizedDescriptionKey: "Apple GSA init response was missing SRP fields (c/s/i/B)."])',
            "surface init SRP fields",
        ),
        (
            '            throw ServerError.missingKey(key: "spd", jsonPayload: payload)',
            '            throw NSError(domain: "SideSign.GSA.complete", code: -2002, userInfo: [NSLocalizedDescriptionKey: "Apple GSA complete response was missing SPD data."])',
            "surface missing SPD",
        ),
        (
            '            throw ServerError.missingKey(key: "M2", jsonPayload: payload)',
            '            throw NSError(domain: "SideSign.GSA.complete", code: -2003, userInfo: [NSLocalizedDescriptionKey: "Apple GSA complete response was missing the server proof M2."])',
            "surface missing M2",
        ),
        (
            '            throw ServerError.invalidResponseFormat(rawPayload: rawDecrypted)',
            '            throw NSError(domain: "SideSign.GSA.complete", code: -2004, userInfo: [NSLocalizedDescriptionKey: "Apple GSA SPD payload could not be decoded."])',
            "surface SPD format",
        ),
        (
            '            throw ServerError.missingKey(key: "adsid", jsonPayload: jsonStr)',
            '            throw NSError(domain: "SideSign.GSA.complete", code: -2005, userInfo: [NSLocalizedDescriptionKey: "Apple GSA SPD payload was missing the account identifier."])',
            "surface missing account id",
        ),
        (
            '            throw ServerError.missingKey(key: "GsIdmsToken", jsonPayload: jsonStr)',
            '            throw NSError(domain: "SideSign.GSA.complete", code: -2006, userInfo: [NSLocalizedDescriptionKey: "Apple GSA SPD payload was missing the IDMS token."])',
            "surface missing IDMS token",
        ),
        (
            '            throw ServerError.missingKey(key: "sk", jsonPayload: prettyJSONString(from: decryptedDictionary))',
            '            throw NSError(domain: "SideSign.GSA.apptokens", code: -2101, userInfo: [NSLocalizedDescriptionKey: "Apple GSA SPD payload was missing the session key."])',
            "surface missing session key",
        ),
        (
            '            throw ServerError.missingKey(key: "c", jsonPayload: prettyJSONString(from: decryptedDictionary))',
            '            throw NSError(domain: "SideSign.GSA.apptokens", code: -2102, userInfo: [NSLocalizedDescriptionKey: "Apple GSA SPD payload was missing the app-token challenge."])',
            "surface missing app-token challenge",
        ),
        (
            '            throw ServerError.missingKey(key: "et", jsonPayload: payload)',
            '            throw NSError(domain: "SideSign.GSA.apptokens", code: -2201, userInfo: [NSLocalizedDescriptionKey: "Apple GSA app-token response was missing encrypted token data."])',
            "surface missing encrypted token",
        ),
        (
            '            throw ServerError.invalidResponseFormat(rawPayload: rawStr)',
            '            throw NSError(domain: "SideSign.GSA.apptokens", code: -2202, userInfo: [NSLocalizedDescriptionKey: "Apple GSA app-token payload could not be decoded."])',
            "surface app-token format",
        ),
        (
            '            throw ServerError.missingKey(key: "t/\\(app)/token", jsonPayload: payload)',
            '            throw NSError(domain: "SideSign.GSA.apptokens", code: -2203, userInfo: [NSLocalizedDescriptionKey: "Apple GSA app-token payload was missing the token field."])',
            "surface missing app token",
        ),
    ]
    for old, new, label in phase_error_replacements:
        text = replace_once(text, old, new, label)

    old_token = '''    private func fetchAuthToken(app: String, parameters: [String: any Sendable], sessionKey: Data, anisetteData: AnisetteData) async throws -> FetchedAuthToken {
        let responseDictionary = try await sendAuthenticationRequest(parameters: parameters, anisetteData: anisetteData)
'''
    new_token = '''    private func fetchAuthToken(
        app: String,
        parameters: [String: any Sendable],
        sessionKey: Data,
        anisetteData: AnisetteData,
        xcodeVersion: String
    ) async throws -> FetchedAuthToken {
        let responseDictionary = try await sendAuthenticationRequest(
            parameters: parameters,
            anisetteData: anisetteData,
            xcodeVersion: xcodeVersion,
            phase: "apptokens"
        )
'''
    text = replace_once(text, old_token, new_token, "thread xcodeVersion through fetchAuthToken")


    old_error_mapping = '''        let errorCode = status["ec"] as? Int ?? 0
        if errorCode != 0 {
            let errorDesc = status["em"] as? String
            debugLog("[SideSign] Auth endpoint returned error code \(errorCode): \(errorDesc ?? "No error message")")
            switch errorCode {
            case GrandSlamAuthErrorCodes.incorrectCredentials:
                throw DeveloperPortalError.incorrectCredentials(cause: errorDesc)
            case GrandSlamAuthErrorCodes.appSpecificPasswordRequired,
                 GrandSlamAuthErrorCodes.appSpecificPasswordRequiredFallback:
                throw DeveloperPortalError.appSpecificPasswordRequired(cause: errorDesc)
            case GrandSlamAuthErrorCodes.incorrectVerificationCode:
                throw DeveloperPortalError.incorrectVerificationCode(cause: errorDesc)
            default:
                throw ServerError.underlyingError(code: errorCode, message: errorDesc ?? "Authentication failed")
            }
        }
'''
    new_error_mapping = '''        let errorCode = status["ec"] as? Int ?? 0
        if errorCode != 0 {
            let errorDesc = status["em"] as? String
            debugLog("[SideSign] GSA phase=\(phase) rejected request: HTTP \(statusCode), ec=\(errorCode), emPresent=\(errorDesc != nil)")
            switch errorCode {
            case GrandSlamAuthErrorCodes.incorrectCredentials:
                throw DeveloperPortalError.incorrectCredentials(cause: errorDesc)
            case GrandSlamAuthErrorCodes.appSpecificPasswordRequired,
                 GrandSlamAuthErrorCodes.appSpecificPasswordRequiredFallback:
                throw DeveloperPortalError.appSpecificPasswordRequired(cause: errorDesc)
            case GrandSlamAuthErrorCodes.incorrectVerificationCode:
                throw DeveloperPortalError.incorrectVerificationCode(cause: errorDesc)
            default:
                throw NSError(
                    domain: "SideSign.GSA.\(phase)",
                    code: errorCode,
                    userInfo: [
                        NSLocalizedDescriptionKey: "Apple GSA \(phase) rejected the request (HTTP \(statusCode), ec \(errorCode))."
                    ]
                )
            }
        }
'''
    text = replace_once(text, old_error_mapping, new_error_mapping, "surface credential-safe GSA phase/error code")

    after = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if before == after:
        raise RuntimeError("transform produced no change")

    TARGET.write_text(text, encoding="utf-8")
    print(f"patched {TARGET}")
    print(f"source_sha256={before}")
    print(f"patched_sha256={after}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"patch_sidesign_gsa.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
