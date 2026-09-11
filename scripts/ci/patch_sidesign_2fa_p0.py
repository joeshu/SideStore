#!/usr/bin/env python3
from pathlib import Path

TARGET = Path("Dependencies/SideSign/Sources/DeveloperPortal/Authentication.swift")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")

    anchor = '''    private func sendPhonePut(mode requestedMode: String,
'''
    helper = '''    private func fetchTrustedPhoneNumbers(dsid: String,
                                                idmsToken: String,
                                                anisetteData: AnisetteData,
                                                xcodeVersion: String) async throws -> [TrustedPhoneNumber]
    {
        var request = makeTwoFactorRequest(
            url: URL(string: "https://gsa.apple.com/auth")!,
            dsid: dsid,
            idmsToken: idmsToken,
            anisetteData: anisetteData,
            xcodeVersion: xcodeVersion
        )
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let (data, response) = try await session.data(for: request)
        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.safeStatusCode ?? 0
        let contentType = httpResponse?.value(forHTTPHeaderField: "Content-Type") ?? "unknown"

        guard statusCode == HTTPStatusCodes.ok,
              let responseDict = parsePlistOrJSON(data)
        else {
            debugLog("[SideSign] trusted-phone discovery failed: HTTP \\(statusCode), content-type=\\(contentType), bytes=\\(data.count)")
            throw NSError(
                domain: "SideSign.GSA.trustedPhones",
                code: statusCode == 0 ? -3001 : statusCode,
                userInfo: [NSLocalizedDescriptionKey: "Apple trusted-phone discovery failed (HTTP \\(statusCode), content-type=\\(contentType), bytes=\\(data.count))."]
            )
        }

        let numbers = parseTrustedPhoneNumbers(from: responseDict)
        guard !numbers.isEmpty else {
            debugLog("[SideSign] trusted-phone discovery returned no trustedPhoneNumbers: HTTP \\(statusCode), content-type=\\(contentType), bytes=\\(data.count)")
            throw NSError(
                domain: "SideSign.GSA.trustedPhones",
                code: -3002,
                userInfo: [NSLocalizedDescriptionKey: "Apple trusted-phone discovery returned no trusted phone numbers."]
            )
        }

        debugLog("[SideSign] trusted-phone discovery succeeded: count=\\(numbers.count)")
        return numbers
    }

    private func sendPhonePut(mode requestedMode: String,
'''
    text = replace_once(text, anchor, helper, "insert trusted-phone discovery")

    old_request_start = '''    {
        var currentMode = initialRequestedMode
        var (phoneID, activeMode, phoneNumbers, statusCode) = try await sendPhonePut(
            mode: currentMode,
            phoneID: initialPhoneID,
            knownPhoneNumbers: knownPhoneNumbers,
'''
    new_request_start = '''    {
        var currentMode = initialRequestedMode
        let discoveredPhoneNumbers = try await fetchTrustedPhoneNumbers(
            dsid: dsid,
            idmsToken: idmsToken,
            anisetteData: anisetteData,
            xcodeVersion: xcodeVersion
        )
        let selectedPhoneID: String
        if let initialPhoneID,
           discoveredPhoneNumbers.contains(where: { $0.id == initialPhoneID }) {
            selectedPhoneID = initialPhoneID
        } else if let first = discoveredPhoneNumbers.first {
            selectedPhoneID = first.id
        } else {
            throw NSError(
                domain: "SideSign.GSA.trustedPhones",
                code: -3003,
                userInfo: [NSLocalizedDescriptionKey: "Apple did not return a selectable trusted phone number."]
            )
        }

        var (phoneID, activeMode, phoneNumbers, statusCode) = try await sendPhonePut(
            mode: currentMode,
            phoneID: selectedPhoneID,
            knownPhoneNumbers: discoveredPhoneNumbers,
'''
    text = replace_once(text, old_request_start, new_request_start, "require discovered phone id")

    old_id = '''        let phoneNumberID = Int(requestedPhoneID ?? "1") ?? 1
        request.httpBody = try JSONSerialization.data(withJSONObject: [
'''
    new_id = '''        guard let requestedPhoneID,
              let phoneNumberID = Int(requestedPhoneID)
        else {
            throw NSError(
                domain: "SideSign.GSA.sms",
                code: -3101,
                userInfo: [NSLocalizedDescriptionKey: "SMS verification requires a trusted phone ID returned by Apple."]
            )
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: [
'''
    text = replace_once(text, old_id, new_id, "remove phone id 1 request fallback")

    old_result = '''        let phoneID = (phoneDict?["id"] as? CustomStringConvertible)?.description ?? requestedPhoneID ?? parsedNumbers.first?.id ?? "1"
'''
    new_result = '''        guard let phoneID = (phoneDict?["id"] as? CustomStringConvertible)?.description ?? requestedPhoneID ?? parsedNumbers.first?.id else {
            throw NSError(
                domain: "SideSign.GSA.sms",
                code: -3102,
                userInfo: [NSLocalizedDescriptionKey: "Apple SMS response did not identify a trusted phone number."]
            )
        }
'''
    text = replace_once(text, old_result, new_result, "remove phone id 1 response fallback")

    TARGET.write_text(text, encoding="utf-8")
    print("P0-1 trusted-phone discovery applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
