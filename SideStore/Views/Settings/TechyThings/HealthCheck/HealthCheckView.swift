//
//  HealthCheckView.swift
//  SideStore
//
//  Created by Magesh K on 11/07/26.
//  Copyright © 2026 SideStore. All rights reserved.
//

import SwiftUI
import Minimuxer
import Foundation

private func formattedHealthDuration(_ milliseconds: Int?) -> String? {
    guard let milliseconds else { return nil }
    if milliseconds < 1000 {
        return "\(milliseconds) ms"
    }
    return String(format: "%.2f s", Double(milliseconds) / 1000.0)
}

private func healthLocalized(_ key: String) -> String {
    NSLocalizedString(key, comment: "")
}

struct HealthCheckView: View {
    @StateObject private var viewModel = HealthCheckViewModel()

    private var minimuxerSatisfied: Bool? {
        guard let result = viewModel.minimuxerReadyResult else { return nil }
        switch result {
        case .success:
            return true
        case .failure:
            return false
        }
    }
    
    var body: some View {
        List {
            // Section 1: Connection Status Header
            Section {
                VStack(spacing: 12) {
                    if let result = viewModel.minimuxerReadyResult {
                        switch result {
                        case .success:
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 44))
                                .foregroundColor(.green)
                            Text("SideStore Ready")
                                .font(.title2)
                                .fontWeight(.bold)
                            Text(healthLocalized(viewModel.connectionMode == .localVPN
                                 ? "All requirements met. Local device pairing & VPN tunnel active."
                                 : "All requirements met. Local device pairing & Remote server connection active."
                            ))
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        case .failure(let err):
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: 44))
                                .foregroundColor(.orange)
                            Text("Action Required")
                                .font(.title2)
                                .fontWeight(.bold)
                            Text(err.localizedDescription)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                    } else {
                        ProgressView("Performing Diagnostic Check...")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
            }
            
            // Section 2: Core Dependencies
            Section(header: Text("Core Requirements")) {
                DependencyRow(
                    title: "Network Connectivity",
                    subtitle: viewModel.networkSatisfied == nil ? "Unknown" : (viewModel.isWifiSatisfied ? "Wi-Fi Active" : "No Connection"),
                    isSatisfied: viewModel.networkSatisfied
                )
                
                if viewModel.connectionMode == .localVPN {
                    DependencyRow(
                        title: "VPN Tunnel (utun)",
                        subtitle: viewModel.vpnSatisfied == nil ? "Unknown" : (viewModel.isUTunAvailable ? "Connected" : "Disconnected"),
                        isSatisfied: viewModel.vpnSatisfied
                    )
                    
                    if !viewModel.isRPPairing {
                        if #available(iOS 26.4, *) {
                            DependencyRow(
                                title: "IPSec/IKEv2 Tunnel",
                                subtitle: viewModel.ipsecSatisfied == nil ? "Unknown" : (viewModel.isIKEv2IPSecAvailable ? "Connected" : "Disconnected"),
                                isSatisfied: viewModel.ipsecSatisfied
                            )
                        }
                    }
                }
                
                DependencyRow(
                    title: "Device Reachability (Ping)",
                    subtitle: viewModel.pingSatisfied == nil ? "Unknown" : (viewModel.isPingSuccessful ? "Reachable" : "Unreachable"),
                    isSatisfied: viewModel.pingSatisfied,
                    latencyMilliseconds: viewModel.pingElapsedMilliseconds
                )
                
                DependencyRow(
                    title: "Pairing file",
                    subtitle: viewModel.isPairingFileVerified ? "Verified" : (viewModel.isPairingFileLoaded ? "Loaded (Connection down)" : "Unverified / Missing"),
                    isSatisfied: viewModel.pairingSatisfied,
                    latencyMilliseconds: viewModel.pairingElapsedMilliseconds
                )

                DependencyRow(
                    title: "Minimuxer readiness",
                    subtitle: "Full readiness probe",
                    isSatisfied: minimuxerSatisfied,
                    latencyMilliseconds: viewModel.minimuxerElapsedMilliseconds
                )
            }
            
            // Section 3: JIT Dependencies
            Section(header: Text("JIT Requirements")) {
                DependencyRow(
                    title: "Developer Disk Image (DDI)",
                    subtitle: viewModel.isDDIMounted ? "Mounted" : "Not Mounted (JIT unavailable)",
                    isSatisfied: viewModel.ddiSatisfied,
                    isOptional: true,
                    latencyMilliseconds: viewModel.ddiElapsedMilliseconds
                )
            }

            // P0-B: expose only the safe, persisted trace written by the auth boundary.
            Section(
                header: Text("Last Sign-In Trace"),
                footer: Text("Only stage timing, outcome, safe error domain/code, and non-secret 2FA mode are shown. Credentials, tokens, identifiers, and Anisette payloads are never included.")
            ) {
                if let trace = viewModel.lastAuthTrace, !trace.samples.isEmpty {
                    HStack {
                        Text("Observed total")
                        Spacer()
                        Text(formattedHealthDuration(trace.totalElapsedMilliseconds) ?? "N/A")
                            .foregroundColor(.secondary)
                            .monospacedDigit()
                    }

                    HStack {
                        Text("Last updated")
                        Spacer()
                        Text(trace.updatedAt, style: .relative)
                            .foregroundColor(.secondary)
                    }

                    ForEach(trace.samples) { sample in
                        AuthTraceRow(sample: sample)
                    }
                } else {
                    Text("No sign-in trace recorded yet.")
                        .foregroundColor(.secondary)
                }
            }
            
            // Section 4: Connection Configuration
            Section(header: Text("Connection Configuration")) {
                HStack {
                    Text("Connection Mode")
                    Spacer()
                    Text(healthLocalized(viewModel.connectionMode == .localVPN ? "Local VPN" : "Remote Server"))
                        .foregroundColor(.secondary)
                }
                
                if viewModel.connectionMode == .localVPN {
                    ConfigRow(label: "Tunnel Iface IP", value: viewModel.tunnelIfaceIp)
                    ConfigRow(label: "Tunnel Peer IP", value: viewModel.tunnelPeerIp)
                    ConfigRow(label: "Override Peer IP", value: viewModel.overrideTunnelPeerIp.isEmpty ? nil : viewModel.overrideTunnelPeerIp)
                    HStack {
                        Text("Override Status")
                        Spacer()
                        Text(healthLocalized(viewModel.overrideTunnelPeerEffective ? "Active" : "Inactive"))
                            .foregroundColor(viewModel.overrideTunnelPeerEffective ? .green : .secondary)
                    }
                    HStack {
                        Text("Active Protocol")
                        Spacer()
                        Text(healthLocalized(viewModel.activeProtocol))
                            .foregroundColor(.secondary)
                    }
                } else {
                    ConfigRow(label: "Remote Endpoint IP", value: viewModel.remoteServerIp.isEmpty ? nil : viewModel.remoteServerIp)
                    HStack {
                        Text("Active Protocol")
                        Spacer()
                        Text(healthLocalized(viewModel.activeProtocol))
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            // Section 5: All Active Interfaces
            Section(header: Text("Active Network Interfaces")) {
                if viewModel.availableInterfaces.isEmpty {
                    Text("No active interfaces scanned.")
                        .foregroundColor(.secondary)
                        .italic()
                } else {
                    let vpnInterfaces = viewModel.availableInterfaces.filter { $0.type.isVPN }
                    let localInterfaces = viewModel.availableInterfaces.filter { !$0.type.isVPN }
                    
                    if !vpnInterfaces.isEmpty {
                        ForEach(vpnInterfaces) { iface in
                            InterfaceRow(iface: iface)
                        }
                    }
                    
                    if !localInterfaces.isEmpty {
                        ForEach(localInterfaces) { iface in
                            InterfaceRow(iface: iface)
                        }
                    }
                }
            }
        }
        .navigationTitle("Health Check")
        #if !os(tvOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .task {
            await viewModel.observeMetrics()
        }
    }
}

struct DependencyRow: View {
    let title: String
    let subtitle: String
    let isSatisfied: Bool?
    var isOptional: Bool = false
    var latencyMilliseconds: Int? = nil
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(healthLocalized(title))
                    .font(.body)
                Text(healthLocalized(subtitle))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if let duration = formattedHealthDuration(latencyMilliseconds) {
                Text(duration)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .monospacedDigit()
            }
            if let satisfied = isSatisfied {
                if satisfied {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.title3)
                } else if isOptional {
                    Image(systemName: "minus.circle.fill")
                        .foregroundColor(.orange)
                        .font(.title3)
                } else {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.red)
                        .font(.title3)
                }
            } else {
                Image(systemName: "questionmark.circle.fill")
                    .foregroundColor(.gray)
                    .font(.title3)
            }
        }
    }
}

struct AuthTraceRow: View {
    let sample: HealthCheckAuthTraceSample

    private var outcomeColor: Color {
        switch sample.outcome {
        case "succeeded":
            return .green
        case "failed":
            return .red
        default:
            return .secondary
        }
    }

    private var outcomeIcon: String {
        switch sample.outcome {
        case "succeeded":
            return "checkmark.circle.fill"
        case "failed":
            return "xmark.circle.fill"
        default:
            return "info.circle.fill"
        }
    }

    private var detailText: String? {
        if let domain = sample.errorDomain, let code = sample.errorCode {
            return "\(domain) \(code)"
        }
        if let metadata = sample.metadata {
            switch metadata {
            case "trusted_device":
                return healthLocalized("Trusted device")
            case "sms":
                return "SMS"
            case "voice":
                return healthLocalized("Voice")
            default:
                return nil
            }
        }
        return nil
    }

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: outcomeIcon)
                .foregroundColor(outcomeColor)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 3) {
                Text(healthLocalized(sample.displayName))
                if let detailText {
                    Text(detailText)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .textSelection(.enabled)
                }
            }

            Spacer()

            if sample.outcome == "event" {
                Text("Event")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                Text(formattedHealthDuration(sample.elapsedMilliseconds) ?? "N/A")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .monospacedDigit()
            }
        }
        .padding(.vertical, 2)
    }
}

struct ConfigRow: View {
    let label: String
    let value: String?
    
    var body: some View {
        HStack {
            Text(healthLocalized(label))
            Spacer()
            Text(value ?? "N/A")
                .foregroundColor(.secondary)
        }
    }
}

struct InterfaceRow: View {
    let iface: LocalInterfaceInfo
    
    private var hasIPv4: Bool {
        !iface.subnet.isEmpty && !iface.ip.contains(":")
    }
    
    private var ipv4Host: String {
        hasIPv4 ? iface.ip : "N/A"
    }
    
    private var ipv4Mask: String {
        !iface.subnet.isEmpty ? iface.subnet : "N/A"
    }
    
    private var ipv6Address: String {
        if let v6 = iface.ipv6, !v6.isEmpty {
            return v6
        }
        if iface.ip.contains(":") {
            return iface.ip
        }
        return "N/A"
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text("Iface:")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(width: 36, alignment: .leading)
                
                Text(iface.name)
                    .fontWeight(.semibold)
                
                Text(iface.type.rawValue)
                    .font(.caption)
                    .fontWeight(.medium)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(iface.type.isVPN ? Color.blue.opacity(0.15) : Color.gray.opacity(0.15))
                    .foregroundColor(iface.type.isVPN ? .blue : .primary)
                    .cornerRadius(4)
                
                Spacer()
            }
            .padding(.bottom, 2)
            
            HStack(alignment: .top, spacing: 8) {
                Text("IPv4:")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(width: 36, alignment: .leading)
                
                Text(ipv4Host)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(hasIPv4 ? .primary : .secondary)
                
                if hasIPv4 {
                    Text("(\(ipv4Mask))")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            
            HStack(alignment: .top, spacing: 8) {
                Text("IPv6:")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(width: 36, alignment: .leading)
                
                Text(ipv6Address)
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundColor(ipv6Address != "N/A" ? .primary : .secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 4)
    }
}
