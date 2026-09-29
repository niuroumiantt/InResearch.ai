import AppKit
import Foundation
import Vision

struct OCRResult: Encodable {
    let text: String
    let blank: Bool
    let unreadable: Bool
    let model: String
}

func fail(_ code: String) -> Never {
    let data = try? JSONSerialization.data(withJSONObject: ["error": code])
    if let data = data { FileHandle.standardOutput.write(data); print("") }
    exit(1)
}

let arguments = CommandLine.arguments
guard arguments.count == 3, let pass = Int(arguments[2]), (0...1).contains(pass) else {
    fail("arguments_invalid")
}

let imageURL = URL(fileURLWithPath: arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = pass == 1
request.recognitionLanguages = ["en-US", "zh-Hans"]
request.minimumTextHeight = 0.004

do {
    try VNImageRequestHandler(url: imageURL).perform([request])
} catch {
    fail("vision_request_failed")
}

let observations = (request.results ?? []).sorted {
    let verticalDelta = $0.boundingBox.midY - $1.boundingBox.midY
    return abs(verticalDelta) > 0.006 ? verticalDelta > 0 : $0.boundingBox.minX < $1.boundingBox.minX
}
let lines = observations.compactMap { $0.topCandidates(1).first?.string }
let result = OCRResult(
    text: lines.joined(separator: "\n"),
    blank: false,
    unreadable: lines.isEmpty,
    model: "Apple Vision VNRecognizeTextRequest revision \(request.revision) / \(ProcessInfo.processInfo.operatingSystemVersionString)"
)
do {
    let data = try JSONEncoder().encode(result)
    FileHandle.standardOutput.write(data)
    print("")
} catch {
    fail("result_encoding_failed")
}
