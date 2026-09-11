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

    text = replace_once(
        text,
        '        let initResponse = try await sendAuthenticationRequest(parameters: initParameters, anisetteData: anisetteData)',
        '''        let initResponse = try await sendAuthenticationRequest(
            parameters: initParameters,
            anisetteData: anisetteData,
            xcodeVersion: xcodeVersion
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
            closeConnection: true
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
        if let xcodeVersion = xcodeVersion {
            request.setValue(xcodeVersion, forHTTPHeaderField: "X-Xcode-Version")
        }
        request.setValue(Constants.authApp, forHTTPHeaderField: "X-Apple-App-Info")

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
        closeConnection: Bool = false
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
        if let xcodeVersion = xcodeVersion {
            request.setValue(xcodeVersion, forHTTPHeaderField: "X-Xcode-Version")
        }
        if closeConnection {
            request.setValue("close", forHTTPHeaderField: "Connection")
        }
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
            xcodeVersion: xcodeVersion
        )
'''
    text = replace_once(text, old_token, new_token, "thread xcodeVersion through fetchAuthToken")

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
