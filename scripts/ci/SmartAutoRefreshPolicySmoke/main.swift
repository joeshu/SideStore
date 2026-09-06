import Foundation
func debugLog(_ message: String) {}
let now = Date(timeIntervalSince1970: 2_000_000_000)
func require(_ condition: @autoclosure () -> Bool, _ message: String) {
    guard condition() else { fputs("SmartAutoRefreshPolicy smoke test failed: \(message)\n", stderr); exit(1) }
}
require(SmartAutoRefreshPolicy.urgency(expirationDate: now.addingTimeInterval(4 * 86_400), now: now) == .routine, "routine threshold")
require(SmartAutoRefreshPolicy.urgency(expirationDate: now.addingTimeInterval(3 * 86_400), now: now) == .elevated, "elevated threshold")
require(SmartAutoRefreshPolicy.urgency(expirationDate: now.addingTimeInterval(2 * 86_400), now: now) == .urgent, "urgent threshold")
require(SmartAutoRefreshPolicy.urgency(expirationDate: now.addingTimeInterval(86_400), now: now) == .critical, "critical threshold")
require(SmartAutoRefreshPolicy.shouldAttempt(expirationDate: now.addingTimeInterval(6 * 86_400), state: nil, now: now), "new app eligibility")
let success = SmartAutoRefreshPolicy.State(lastAttempt: now, lastSuccess: now, consecutiveFailures: 0)
require(!SmartAutoRefreshPolicy.shouldAttempt(expirationDate: now.addingTimeInterval(6 * 86_400), state: success, now: now.addingTimeInterval(23 * 3_600)), "early routine attempt")
require(SmartAutoRefreshPolicy.shouldAttempt(expirationDate: now.addingTimeInterval(7 * 86_400), state: success, now: now.addingTimeInterval(24 * 3_600)), "24h routine attempt")
var failed: SmartAutoRefreshPolicy.State?
for _ in 0..<8 { failed = SmartAutoRefreshPolicy.stateAfterFailure(previous: failed, expirationDate: now.addingTimeInterval(12 * 3_600), now: now) }
require(failed?.consecutiveFailures == 8, "bounded failures")
require(failed?.nextEligibleAttempt == now.addingTimeInterval(30 * 60), "critical retry cap")
print("SmartAutoRefreshPolicy smoke tests passed")
