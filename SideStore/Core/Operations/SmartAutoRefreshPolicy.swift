import Foundation

struct SmartAutoRefreshPolicy: Sendable {
    enum Urgency: String, Codable, Sendable {
        case routine, elevated, urgent, critical

        var successfulCheckInterval: TimeInterval {
            switch self {
            case .routine: return 24 * 60 * 60
            case .elevated: return 12 * 60 * 60
            case .urgent: return 3 * 60 * 60
            case .critical: return 60 * 60
            }
        }

        var maximumRetryInterval: TimeInterval {
            switch self {
            case .routine: return 6 * 60 * 60
            case .elevated: return 3 * 60 * 60
            case .urgent: return 60 * 60
            case .critical: return 30 * 60
            }
        }
    }

    struct State: Codable, Equatable, Sendable {
        var lastAttempt: Date?
        var lastSuccess: Date?
        var consecutiveFailures: Int = 0
        var nextEligibleAttempt: Date?
    }

    static func urgency(expirationDate: Date, now: Date = Date()) -> Urgency {
        let remaining = expirationDate.timeIntervalSince(now)
        if remaining <= 24 * 60 * 60 { return .critical }
        if remaining <= 2 * 24 * 60 * 60 { return .urgent }
        if remaining <= 3 * 24 * 60 * 60 { return .elevated }
        return .routine
    }

    static func shouldAttempt(expirationDate: Date, state: State?, now: Date = Date()) -> Bool {
        let state = state ?? State()
        if let next = state.nextEligibleAttempt, next > now { return false }
        guard let lastSuccess = state.lastSuccess else { return true }
        return now.timeIntervalSince(lastSuccess) >= urgency(expirationDate: expirationDate, now: now).successfulCheckInterval
    }

    static func stateAfterSuccess(previous: State?, now: Date = Date()) -> State {
        State(lastAttempt: now, lastSuccess: now, consecutiveFailures: 0, nextEligibleAttempt: nil)
    }

    static func stateAfterFailure(previous: State?, expirationDate: Date, now: Date = Date()) -> State {
        var state = previous ?? State()
        let failures = min(state.consecutiveFailures + 1, 8)
        let limit = urgency(expirationDate: expirationDate, now: now).maximumRetryInterval
        let delay = min(15 * 60 * pow(2, Double(max(0, failures - 1))), limit)
        state.lastAttempt = now
        state.consecutiveFailures = failures
        state.nextEligibleAttempt = now.addingTimeInterval(delay)
        return state
    }
}

final class SmartAutoRefreshStateStore: @unchecked Sendable {
    static let shared = SmartAutoRefreshStateStore()
    private let defaults: UserDefaults
    private let key = "SmartAutoRefreshStateV1"
    private let lock = NSLock()

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    func state(for bundleIdentifier: String) -> SmartAutoRefreshPolicy.State? {
        lock.withLock { load()[bundleIdentifier] }
    }

    func recordSuccess(for bundleIdentifier: String, now: Date = Date()) {
        update(bundleIdentifier) { SmartAutoRefreshPolicy.stateAfterSuccess(previous: $0, now: now) }
    }

    func recordFailure(for bundleIdentifier: String, expirationDate: Date, now: Date = Date()) {
        update(bundleIdentifier) { SmartAutoRefreshPolicy.stateAfterFailure(previous: $0, expirationDate: expirationDate, now: now) }
    }

    func removeStaleEntries(keeping identifiers: Set<String>) {
        lock.withLock { save(load().filter { identifiers.contains($0.key) }) }
    }

    private func update(_ id: String, transform: (SmartAutoRefreshPolicy.State?) -> SmartAutoRefreshPolicy.State) {
        lock.withLock {
            var states = load()
            states[id] = transform(states[id])
            save(states)
        }
    }

    private func load() -> [String: SmartAutoRefreshPolicy.State] {
        guard let data = defaults.data(forKey: key) else { return [:] }
        do { return try JSONDecoder().decode([String: SmartAutoRefreshPolicy.State].self, from: data) }
        catch {
            debugLog("[SmartAutoRefresh] Discarding unreadable scheduler state")
            return [:]
        }
    }

    private func save(_ states: [String: SmartAutoRefreshPolicy.State]) {
        do { defaults.set(try JSONEncoder().encode(states), forKey: key) }
        catch { debugLog("[SmartAutoRefresh] Failed to persist scheduler state") }
    }
}
