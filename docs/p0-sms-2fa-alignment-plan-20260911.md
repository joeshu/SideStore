# P0 SMS 2FA alignment plan

Target baseline: iLoader 2.3.3 -> isideload 0.3.17 pinned commit `f6a4d5dba717d72fc2af63eaba26b27ba44116be`.

This change set must land together before the next device test:

1. Trusted phone discovery
   - GET `https://gsa.apple.com/auth` with the same 2FA headers as iLoader.
   - Parse `trustedPhoneNumbers` and use a real Apple phone ID.
   - Do not silently fall back to phone ID `1` when discovery fails.

2. Fresh Anisette for each 2FA transition
   - Re-fetch Anisette before trusted-phone discovery, SMS send/resend, and SMS verification.
   - Re-fetch Anisette before the post-2FA re-authentication pass.

3. Full HTTP 412 active-challenge validation
   - Require `type == verification`, `authenticationType == hsa2`, matching selected phone ID, selected ID present in `trustedPhoneNumbers`, six-digit security code, and all cooldown/lockout flags false.

4. Complete `serviceErrors` handling
   - Parse JSON `serviceErrors[]` before generic status handling.
   - Map `-28248` to unavailable SMS delivery.
   - Map `-22979` / `-22981` to an existing-code challenge without triggering another send.
   - Map `-21669` to incorrect verification code and keep the verification UI active.

Acceptance gate:
- SideSign smoke workflow passes.
- Combined LiveContainer+SideStore IPA builds and package verification passes.
- Device test confirms SMS delivery and successful code verification.
- PR remains draft until device test succeeds.
