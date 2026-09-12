# P0 SMS 2FA alignment checklist

Target baseline: iLoader 2.3.3 -> isideload 0.3.17 pinned commit `f6a4d5dba717d72fc2af63eaba26b27ba44116be`.

All four P0 items must land in one device-test build. PR #16 stays Draft until real-device login succeeds.

## Implementation checklist

- [ ] P0-1 Trusted phone discovery
  - GET `https://gsa.apple.com/auth` with the iLoader-compatible 2FA headers.
  - Parse `trustedPhoneNumbers`.
  - Select only a phone ID returned by Apple.
  - Remove silent fallback to phone ID `1`.
  - Add credential-safe diagnostics for HTTP status/content type/count only.

- [ ] P0-2 Fresh Anisette for every 2FA transition
  - Re-fetch Anisette before trusted-phone discovery.
  - Re-fetch Anisette before SMS send/resend.
  - Re-fetch Anisette before SMS verification.
  - Re-fetch Anisette before the post-2FA re-authentication pass.
  - Do not cache or log OTP/machine secrets.

- [ ] P0-3 Full HTTP 412 active-challenge validation
  - Require `mode == sms`.
  - Require `type == verification`.
  - Require `authenticationType == hsa2`.
  - Require selected `trustedPhoneNumber.id` to equal the requested ID.
  - Require the requested ID to be present in `trustedPhoneNumbers`.
  - Require `securityCode.length == 6`.
  - Require `tooManyCodesSent == false`.
  - Require `tooManyCodesValidated == false`.
  - Require `securityCodeLocked == false`.
  - Require `securityCodeCooldown == false`.

- [ ] P0-4 Complete `serviceErrors[]` handling
  - Parse `serviceErrors[]` before generic HTTP/status handling.
  - `-28248`: SMS unavailable for selected number; return to method selection.
  - `-22979` / `-22981`: keep active SMS challenge and allow the previous code to be entered without sending again.
  - `-21669`: incorrect verification code; keep verification UI active.
  - Preserve safe title/message for the UI without logging credentials, tokens, raw GSA bodies, SRP secrets or Anisette secrets.

## Build and validation checklist

- [ ] Deterministic SideSign transform succeeds against pinned `Dependencies/SideSign@0ea22b202ebb5de28615ecec51b276c57aa3ec92`.
- [ ] `swift build --package-path Dependencies/SideSign` passes.
- [ ] SideStore P0 smoke workflow passes.
- [ ] Combined LiveContainer+SideStore IPA builds.
- [ ] Combined IPA package/embedded SideStore verification passes.
- [ ] Device footer confirms the new LiveContainer commit.
- [ ] Real device receives SMS.
- [ ] Correct SMS code verifies successfully.
- [ ] Post-2FA re-login succeeds and account loads.
- [ ] Only after all device gates pass: mark PR #16 ready and merge.

## Status log

- 2026-09-11: Checklist converted from plan to executable gate list; PR #16 confirmed Draft.
