//
//  MinimuxerCompatibility.swift
//  SideStore
//
//  Compatibility shims for the current minimuxer pairing API.
//

import Foundation
import Minimuxer
import MinimuxerCommon
import DeviceGatewayAPI

extension DeviceGatewayAPI {
    /// Compatibility accessor for SideStore call sites that still use the former API name.
    var isRPPairing: Bool {
        pairingFileType == .rppairing
    }
}

extension MinimuxerAPI {
    /// Compatibility accessor for SideStore call sites that still use the former API name.
    var isrppairing: Bool {
        pairingFileType == .rppairing
    }
}

extension PairedDeviceRecord {
    /// Legacy wireless-pairing result field.
    ///
    /// For Lockdown pairing this is the hardware UDID embedded in the pairing record.
    /// For Remote Pairing this is only the pairing-record identifier; callers that need
    /// the Apple hardware UDID must query it live through `fetchUDID()` after RSD is up.
    var udid: String {
        switch pairingFile.mode {
        case .lockdown:
            return pairingFile.plist["UDID"] as? String ?? ""
        case .rppairing:
            return pairingFile.plist["identifier"] as? String ?? ""
        case .unknown:
            return ""
        }
    }
}
