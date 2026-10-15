import Foundation
import Vision
import AppKit
let path = CommandLine.arguments[1]
let image = NSImage(contentsOfFile: path)!
var rect = CGRect(origin: .zero, size: image.size)
let cg = image.cgImage(forProposedRect: &rect, context: nil, hints: nil)!
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.recognitionLanguages = ["ru-RU", "en-US"]
req.usesLanguageCorrection = false
try VNImageRequestHandler(cgImage: cg).perform([req])
let rows: [[String: Any]] = (req.results ?? []).compactMap { o in
  guard let candidate = o.topCandidates(1).first else { return nil }
  let b = o.boundingBox
  return ["text": candidate.string, "confidence": candidate.confidence,
          "x": b.minX * CGFloat(cg.width), "y": (1-b.maxY) * CGFloat(cg.height),
          "width": b.width * CGFloat(cg.width), "height": b.height * CGFloat(cg.height)]
}
let data = try JSONSerialization.data(withJSONObject: ["width": cg.width, "height": cg.height, "items": rows])
print(String(data: data, encoding: .utf8)!)
