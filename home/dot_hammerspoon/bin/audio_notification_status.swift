import CoreAudio
import Foundation

func property<T>(_ id: AudioObjectID, _ selector: AudioObjectPropertySelector, _ initial: T) -> T? {
    var address = AudioObjectPropertyAddress(mSelector: selector, mScope: kAudioObjectPropertyScopeGlobal, mElement: 0)
    var bytes = UInt32(MemoryLayout<T>.size)
    var value = initial
    let status = withUnsafeMutableBytes(of: &value) {
        AudioObjectGetPropertyData(id, &address, 0, nil, &bytes, $0.baseAddress!)
    }
    return status == noErr ? value : nil
}
let system = AudioObjectID(kAudioObjectSystemObject)
let output = property(system, kAudioHardwarePropertyDefaultSystemOutputDevice, AudioObjectID(0))
var address = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices, mScope: kAudioObjectPropertyScopeGlobal, mElement: 0)
var size: UInt32 = 0
guard AudioObjectGetPropertyDataSize(system, &address, 0, nil, &size) == noErr else { exit(1) }
var ids = [AudioObjectID](repeating: 0, count: Int(size) / MemoryLayout<AudioObjectID>.size)
guard !ids.isEmpty, AudioObjectGetPropertyData(system, &address, 0, nil, &size, &ids) == noErr else { exit(1) }
func name(_ id: AudioObjectID) -> String {
    ((property(id, kAudioObjectPropertyName, nil as CFString?) ?? nil) as String?) ?? String(id)
}
var devices: [[String: Any]] = []
for id in ids {
    guard property(id, kAudioDevicePropertyTransportType, UInt32(0)) == kAudioDeviceTransportTypeAggregate,
          let composition = property(id, kAudioAggregateDevicePropertyComposition, nil as CFDictionary?) ?? nil,
          (composition as NSDictionary)[kAudioAggregateDeviceIsStackedKey] as? Bool == true else { continue }
    var membersAddress = AudioObjectPropertyAddress(mSelector: kAudioAggregateDevicePropertyActiveSubDeviceList,
                                                    mScope: kAudioObjectPropertyScopeGlobal, mElement: 0)
    var memberSize: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(id, &membersAddress, 0, nil, &memberSize) == noErr else { continue }
    var members = [AudioObjectID](repeating: 0, count: Int(memberSize) / MemoryLayout<AudioObjectID>.size)
    if !members.isEmpty {
        guard AudioObjectGetPropertyData(id, &membersAddress, 0, nil, &memberSize, &members) == noErr else { continue }
    }
    let names = members.map(name)
    devices.append(["name": name(id), "selected": output == id, "members": names])
}
let result: [String: Any] = ["devices": devices, "outputKnown": output != nil]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result))
