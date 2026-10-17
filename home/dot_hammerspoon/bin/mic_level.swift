import AVFoundation
import Darwin
import Foundation

func microphoneAccessGranted() -> Bool {
    switch AVCaptureDevice.authorizationStatus(for: .audio) {
    case .authorized: return true
    case .notDetermined:
        let semaphore = DispatchSemaphore(value: 0)
        var granted = false
        AVCaptureDevice.requestAccess(for: .audio) { allowed in
            granted = allowed; semaphore.signal()
        }
        semaphore.wait()
        return granted
    default: return false
    }
}

guard microphoneAccessGranted() else {
    fputs("ERROR Mikrofonzugriff nicht erlaubt\n", stderr); exit(3)
}
let engine = AVAudioEngine()
let input = engine.inputNode
let format = input.inputFormat(forBus: 0)
guard format.channelCount > 0 else {
    fputs("ERROR Kein Eingangskanal verfügbar\n", stderr); exit(4)
}
input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
    guard let channels = buffer.floatChannelData else { return }
    let channelsCount = Int(buffer.format.channelCount)
    let frames = Int(buffer.frameLength)
    guard channelsCount > 0 && frames > 0 else { return }
    var sum: Float = 0
    for channel in 0..<channelsCount {
        for frame in 0..<frames {
            let sample = channels[channel][frame]
            sum += sample * sample
        }
    }
    print(String(format: "%.5f", sqrt(sum / Float(channelsCount * frames))))
    fflush(stdout)
}
do {
    try engine.start()
    RunLoop.current.run(until: Date().addingTimeInterval(4))
    engine.stop()
    input.removeTap(onBus: 0)
} catch {
    fputs("ERROR Mikrofontest konnte nicht gestartet werden\n", stderr); exit(5)
}
