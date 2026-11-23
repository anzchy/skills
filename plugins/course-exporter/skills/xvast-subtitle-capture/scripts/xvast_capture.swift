// xvast-capture: drive the Xvast player through macOS Accessibility and record
// raw window frames with `screencapture -l <windowID>` for the
// xvast-subtitle-capture skill (Claude Code edition).
//
// Subcommands (all print one JSON object to stdout; errors go to stderr, exit 1):
//   status                         video, position, duration, rate, playing, window
//   play | pause                   press the player's Play / Pause button
//   seek --to <H:MM:SS|s> | --by <±s> [--max-steps 30]
//                                  step the progress bar in 10 s AX steps (±5 s precision)
//   park-cursor                    move the pointer to the empty tab strip (safe zone)
//   screenshot --out <file>        one raw full-window image (layout evidence)
//   capture --video-id ... --output-root <abs .raw> --batch-dir <name> ...
//
// Build: scripts/xvast-capture compiles this file on first use (swiftc -O).

import AppKit
import ApplicationServices
import Foundation
import ImageIO

let bundleID = "com.haihaisoft.xvast"

// MARK: - Output helpers

struct CLIError: Error { let message: String }

func fail(_ message: String) -> Never {
  FileHandle.standardError.write(("xvast-capture: " + message + "\n").data(using: .utf8)!)
  exit(1)
}

func printJSON(_ object: Any) {
  let data = try! JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
  FileHandle.standardOutput.write(data)
  FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}

func nowMs() -> Int64 { Int64((Date().timeIntervalSince1970 * 1000).rounded()) }

// MARK: - Accessibility

func attr(_ e: AXUIElement, _ name: String) -> AnyObject? {
  var value: AnyObject?
  return AXUIElementCopyAttributeValue(e, name as CFString, &value) == .success ? value : nil
}

func str(_ e: AXUIElement, _ name: String) -> String { (attr(e, name) as? String) ?? "" }

func children(_ e: AXUIElement) -> [AXUIElement] { (attr(e, "AXChildren") as? [AXUIElement]) ?? [] }

func find(_ e: AXUIElement, depth: Int = 0, _ pred: (AXUIElement) -> Bool) -> AXUIElement? {
  if pred(e) { return e }
  if depth > 45 { return nil }
  for c in children(e) { if let hit = find(c, depth: depth + 1, pred) { return hit } }
  return nil
}

func findAll(_ e: AXUIElement, depth: Int = 0, into out: inout [AXUIElement], _ pred: (AXUIElement) -> Bool) {
  if pred(e) { out.append(e) }
  if depth > 45 { return }
  for c in children(e) { findAll(c, depth: depth + 1, into: &out, pred) }
}

func point(_ e: AXUIElement, _ name: String) -> CGPoint? {
  guard let v = attr(e, name) else { return nil }
  var p = CGPoint.zero
  return AXValueGetValue(v as! AXValue, .cgPoint, &p) ? p : nil
}

func size(_ e: AXUIElement, _ name: String) -> CGSize? {
  guard let v = attr(e, name) else { return nil }
  var s = CGSize.zero
  return AXValueGetValue(v as! AXValue, .cgSize, &s) ? s : nil
}

/// Parses "H:MM:SS", "M:SS", "-H:MM:SS" or plain seconds into milliseconds.
func parseClockMs(_ text: String) -> Int? {
  var t = text.trimmingCharacters(in: .whitespaces)
  if t.hasPrefix("-") { t.removeFirst() }
  let parts = t.split(separator: ":").map { Int($0) }
  if parts.isEmpty || parts.contains(where: { $0 == nil }) { return nil }
  return parts.reduce(0) { $0 * 60 + $1! } * 1000
}

func clock(_ ms: Int) -> String {
  let s = ms / 1000
  return String(format: "%d:%02d:%02d", s / 3600, (s / 60) % 60, s % 60)
}

final class Player {
  let pid: pid_t
  let app: AXUIElement
  let bar: AXUIElement
  let container: AXUIElement

  init() throws {
    guard AXIsProcessTrusted() else {
      throw CLIError(message: "Accessibility permission missing for the calling terminal (System Settings → Privacy & Security → Accessibility)")
    }
    guard let running = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).first else {
      throw CLIError(message: "Xvast (\(bundleID)) is not running")
    }
    pid = running.processIdentifier
    app = AXUIElementCreateApplication(pid)
    // Chromium only exposes web content to AX clients that ask for it.
    AXUIElementSetAttributeValue(app, "AXManualAccessibility" as CFString, kCFBooleanTrue)
    var found: AXUIElement?
    for attempt in 0..<10 {
      found = find(app) { str($0, "AXRole") == "AXSlider" && str($0, "AXDescription") == "progress bar" }
      if found != nil { break }
      if attempt == 1 { AXUIElementSetAttributeValue(app, "AXEnhancedUserInterface" as CFString, kCFBooleanTrue) }
      Thread.sleep(forTimeInterval: 0.5)
    }
    guard let progress = found else {
      throw CLIError(message: "Xvast player progress bar not found; open chrome://playlist and select the video")
    }
    bar = progress
    var node: AXUIElement = progress
    var player: AXUIElement? = nil
    for _ in 0..<12 {
      guard let parent = attr(node, "AXParent") else { break }
      node = parent as! AXUIElement
      if str(node, "AXDescription") == "video player" { player = node; break }
    }
    container = player ?? progress
  }

  var positionMs: Int? { parseClockMs(str(bar, "AXValueDescription")) }

  var remainingMs: Int? {
    var texts: [AXUIElement] = []
    findAll(container, into: &texts) { str($0, "AXRole") == "AXStaticText" && str($0, "AXValue").hasPrefix("-") }
    return texts.lazy.compactMap { parseClockMs(str($0, "AXValue")) }.first
  }

  var playbackRate: Double? {
    let item = find(container) { str($0, "AXTitle").contains("Playback Rate") }
    guard let title = item.map({ str($0, "AXTitle") }),
          let range = title.range(of: #"[\d.]+(?=x)"#, options: .regularExpression) else { return nil }
    return Double(title[range])
  }

  func button(_ name: String) -> AXUIElement? {
    // Xvast prefixes button titles with icon glyphs, e.g. "\u{F04B} Play".
    find(container) {
      str($0, "AXRole") == "AXButton"
        && str($0, "AXTitle").trimmingCharacters(in: .whitespaces).hasSuffix(name)
        && !str($0, "AXTitle").hasSuffix("% " + name)
    }
  }

  var isPlaying: Bool { button("Pause") != nil }

  var videoID: String? {
    // The playlist row is a static text ending in a media extension.
    var texts: [AXUIElement] = []
    findAll(app, into: &texts) {
      str($0, "AXRole") == "AXStaticText"
        && str($0, "AXValue").range(of: #"\.(mp4|mkv|mov|m4v|webm|avi|flv)$"#, options: [.regularExpression, .caseInsensitive]) != nil
    }
    return texts.first.map { str($0, "AXValue") }
  }

  func pageContains(_ text: String) -> Bool {
    find(app) { str($0, "AXValue") == text || str($0, "AXTitle") == text } != nil
  }

  var window: AXUIElement? { attr(bar, "AXWindow").map { $0 as! AXUIElement } }

  func press(_ name: String) throws {
    guard let b = button(name) else { throw CLIError(message: "\(name) button not found") }
    let r = AXUIElementPerformAction(b, kAXPressAction as CFString)
    if r != .success { throw CLIError(message: "pressing \(name) failed: AXError \(r.rawValue)") }
  }

  /// Xvast ignores AXValue writes on the progress bar; AXIncrement / AXDecrement move it
  /// by a fixed step (10 s observed). Xvast once exited during a rapid burst of steps, so
  /// send one step at a time, wait, and re-read the position before the next one.
  /// Returns the number of actions performed.
  func seek(toMs target: Int, maxSteps: Int) throws -> Int {
    guard let pos0 = positionMs, let rem = remainingMs else { throw CLIError(message: "cannot read position/remaining time") }
    let duration = pos0 + rem
    guard target >= 0, target <= duration else {
      throw CLIError(message: "seek target \(clock(target)) outside 0…\(clock(duration))")
    }
    let stepMs = 10_000
    let needed = Int((Double(abs(target - pos0)) / Double(stepMs)).rounded())
    guard needed <= maxSteps else {
      throw CLIError(message: "seek needs ~\(needed) steps of 10 s (limit \(maxSteps)); drag the progress bar by hand for long jumps, or pass --max-steps")
    }
    var actions = 0
    var pos = pos0
    while abs(target - pos) * 2 > stepMs {
      if actions >= maxSteps + 3 { throw CLIError(message: "seek did not converge on \(clock(target)); now at \(clock(pos))") }
      let action = (target > pos ? "AXIncrement" : "AXDecrement") as CFString
      let r = AXUIElementPerformAction(bar, action)
      if r != .success { throw CLIError(message: "\(action) failed: AXError \(r.rawValue)") }
      actions += 1
      Thread.sleep(forTimeInterval: 0.25)
      guard let now = positionMs else { throw CLIError(message: "lost the progress bar while seeking (is Xvast still running?)") }
      if now == pos { throw CLIError(message: "\(action) did not move the progress bar (stuck at \(clock(pos)))") }
      pos = now
    }
    return actions
  }
}

// MARK: - Window lookup & capture

struct WindowInfo { let id: Int; let bounds: CGRect; let title: String }

func xvastWindow(_ player: Player) throws -> WindowInfo {
  guard let w = player.window, let origin = point(w, "AXPosition"), let sz = size(w, "AXSize") else {
    throw CLIError(message: "cannot read the AX window that hosts the player")
  }
  let axRect = CGRect(origin: origin, size: sz)
  let list = (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]) ?? []
  for info in list {
    guard (info[kCGWindowOwnerPID as String] as? Int32) == player.pid,
          (info[kCGWindowLayer as String] as? Int) == 0,
          let bd = info[kCGWindowBounds as String] as? NSDictionary,
          let rect = CGRect(dictionaryRepresentation: bd),
          abs(rect.minX - axRect.minX) < 2, abs(rect.minY - axRect.minY) < 2,
          abs(rect.width - axRect.width) < 2, abs(rect.height - axRect.height) < 2,
          let id = info[kCGWindowNumber as String] as? Int else { continue }
    return WindowInfo(id: id, bounds: rect, title: (info[kCGWindowName as String] as? String) ?? str(w, "AXTitle"))
  }
  throw CLIError(message: "no on-screen CG window matches the player window (minimised or on another Space?)")
}

func boundsJSON(_ r: CGRect) -> [String: Int] {
  ["x": Int(r.minX), "y": Int(r.minY), "width": Int(r.width), "height": Int(r.height)]
}

struct ImageFacts { let format: String; let width: Int; let height: Int; let bytes: Int }

func inspectImage(_ path: String) throws -> ImageFacts {
  let url = URL(fileURLWithPath: path)
  let data = try Data(contentsOf: url)
  let format: String
  if data.starts(with: [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) { format = "png" }
  else if data.starts(with: [0xFF, 0xD8, 0xFF]) { format = "jpg" }
  else { throw CLIError(message: "unexpected image signature in \(path)") }
  guard let src = CGImageSourceCreateWithData(data as CFData, nil),
        let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [CFString: Any],
        let w = props[kCGImagePropertyPixelWidth] as? Int,
        let h = props[kCGImagePropertyPixelHeight] as? Int else {
    throw CLIError(message: "cannot read image dimensions of \(path)")
  }
  return ImageFacts(format: format, width: w, height: h, bytes: data.count)
}

/// Captures one window image into a hidden temp file, then renames; refuses to overwrite.
/// screencapture occasionally exits 15 transiently, so retry a few times.
/// Returns the image facts and the number of attempts used.
func captureWindow(_ windowID: Int, to finalPath: String, format: String) throws -> (ImageFacts, Int) {
  let fm = FileManager.default
  if fm.fileExists(atPath: finalPath) { throw CLIError(message: "refusing to overwrite \(finalPath)") }
  let dir = (finalPath as NSString).deletingLastPathComponent
  let base = (finalPath as NSString).lastPathComponent
  let part = (dir as NSString).appendingPathComponent("_\(base).part.\(format)")
  var lastError = ""
  for attempt in 1...4 {
    try? fm.removeItem(atPath: part)
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    // -x silent, -o no window shadow, -t format, -l window id
    p.arguments = ["-x", "-o", "-t", format, "-l", String(windowID), part]
    let errPipe = Pipe()
    p.standardError = errPipe
    try p.run()
    p.waitUntilExit()
    if p.terminationStatus == 0, fm.fileExists(atPath: part) {
      let facts = try inspectImage(part)
      let expectedExt = (finalPath as NSString).pathExtension.lowercased()
      if expectedExt != facts.format { throw CLIError(message: "captured \(facts.format) but target extension is .\(expectedExt)") }
      try fm.moveItem(atPath: part, toPath: finalPath)
      return (facts, attempt)
    }
    let err = String(data: errPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
    lastError = "exit \(p.terminationStatus) \(err.trimmingCharacters(in: .whitespacesAndNewlines))"
    Thread.sleep(forTimeInterval: 0.05)
  }
  try? fm.removeItem(atPath: part)
  throw CLIError(message: "screencapture failed after 4 attempts: \(lastError)")
}

func parkCursor(_ win: WindowInfo) -> CGPoint {
  // Empty part of the tab strip: right of the "+" button, left of the tab-search chevron.
  let target = CGPoint(x: win.bounds.minX + win.bounds.width * 0.78, y: win.bounds.minY + 22)
  CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: target, mouseButton: .left)?
    .post(tap: .cghidEventTap)
  return target
}

// MARK: - Argument parsing

struct Args {
  var values: [String: String] = [:]
  var flags: Set<String> = []
  init(_ argv: ArraySlice<String>, flagNames: Set<String>) {
    var it = argv.makeIterator()
    while let a = it.next() {
      guard a.hasPrefix("--") else { fail("unexpected argument \(a)") }
      let key = String(a.dropFirst(2))
      if flagNames.contains(key) { flags.insert(key) }
      else if let v = it.next() { values[key] = v }
      else { fail("missing value for \(a)") }
    }
  }
  func require(_ k: String) -> String { values[k] ?? { fail("--\(k) is required") }() }
  func int(_ k: String, default d: Int?) -> Int? {
    guard let v = values[k] else { return d }
    return Int(v) ?? { fail("--\(k) must be an integer") }()
  }
}

func statusJSON(_ player: Player) -> [String: Any] {
  let pos = player.positionMs, rem = player.remainingMs
  var out: [String: Any] = [
    "video_id": player.videoID ?? NSNull(),
    "position_ms": pos ?? NSNull(),
    "position": pos.map(clock) ?? NSNull(),
    "duration_ms": (pos != nil && rem != nil) ? pos! + rem! : NSNull(),
    "playback_rate": player.playbackRate ?? NSNull(),
    "playing": player.isPlaying,
  ]
  if let win = try? xvastWindow(player) {
    out["window_id"] = win.id
    out["window_title"] = win.title
    out["window_bounds_pt"] = boundsJSON(win.bounds)
  }
  return out
}

// MARK: - capture

func runCapture(_ args: Args) throws {
  let videoID = args.require("video-id")
  let outputRoot = args.require("output-root")
  let batchDir = args.require("batch-dir")
  let layoutProfile = args.values["layout-profile"] ?? "layout-001"
  let frameCount = args.int("frame-count", default: 20)!
  let intervalMs = args.int("interval-ms", default: 500)!
  let shortestSubtitleMs = args.int("shortest-subtitle-ms", default: nil)
  let format = args.values["format"] ?? "jpg"
  let rateFallback = Double(args.values["playback-rate-fallback"] ?? "1") ?? 1

  guard batchDir.range(of: #"^[A-Za-z0-9_-]+$"#, options: .regularExpression) != nil else {
    throw CLIError(message: "--batch-dir must be a simple name without slashes")
  }
  guard outputRoot.hasPrefix("/"), (outputRoot as NSString).lastPathComponent == ".raw" else {
    throw CLIError(message: "--output-root must be the absolute .raw directory of the video project")
  }
  guard (1...120).contains(frameCount) else { throw CLIError(message: "--frame-count must be 1…120; run short batches") }
  guard intervalMs >= 150 else { throw CLIError(message: "--interval-ms must be ≥150 (screencapture needs ~100 ms per frame)") }
  guard ["jpg", "png"].contains(format) else { throw CLIError(message: "--format must be jpg or png") }

  let outputDir = (outputRoot as NSString).appendingPathComponent(batchDir)
  let fm = FileManager.default
  if let existing = try? fm.contentsOfDirectory(atPath: outputDir), !existing.isEmpty {
    throw CLIError(message: "refusing to overwrite existing batch: \(outputDir)")
  }
  try fm.createDirectory(atPath: outputDir, withIntermediateDirectories: true)

  let player = try Player()
  if !player.isPlaying && args.flags.contains("resume-if-paused") {
    try player.press("Play")
    Thread.sleep(forTimeInterval: 0.2)
  }
  guard player.isPlaying else { throw CLIError(message: "Xvast is not playing; start playback before capture (or pass --resume-if-paused)") }
  guard player.pageContains(videoID) else { throw CLIError(message: "the expected video is not shown in the Xvast playlist: \(videoID)") }
  let win = try xvastWindow(player)

  let playbackRate = player.playbackRate ?? rateFallback
  let videoStartMs = player.positionMs
  var frames: [[String: Any]] = []
  var wallStart: Int64? = nil
  var wallEnd: Int64? = nil
  var videoEndMs: Int? = nil
  var stillPlayingAtEnd = true
  var dims: [Int]? = nil
  var captureError: String? = nil

  func finishBatch() {
    stillPlayingAtEnd = player.isPlaying
    videoEndMs = player.positionMs
    if args.flags.contains("pause-after-capture"), player.isPlaying { try? player.press("Pause") }
    wallEnd = nowMs()
  }

  for index in 1...frameCount {
    let before = nowMs()
    if wallStart == nil { wallStart = before }
    let name = String(format: "frame-%06d.%@", index, format)
    let facts: ImageFacts
    let attempts: Int
    do {
      (facts, attempts) = try captureWindow(win.id, to: (outputDir as NSString).appendingPathComponent(name), format: format)
    } catch let e as CLIError {
      captureError = "frame \(index): \(e.message)"
      finishBatch()
      break
    }
    let after = nowMs()
    let axPos = player.positionMs
    if dims == nil { dims = [facts.width, facts.height] }
    if index == frameCount { finishBatch() }
    frames.append([
      "index": index,
      "file": name,
      "wall_before_ms": before,
      "wall_after_ms": after,
      "ax_position_ms": axPos ?? NSNull(),
      "capture_attempts": attempts,
      "size_bytes": facts.bytes,
      "format": facts.format,
      "dimensions_px": [facts.width, facts.height],
    ])
    if index < frameCount {
      let remaining = Double(before + Int64(intervalMs) - nowMs()) / 1000
      if remaining > 0 { Thread.sleep(forTimeInterval: remaining) }
    }
  }

  let starts = frames.map { $0["wall_before_ms"] as! Int64 }
  let gaps = zip(starts.dropFirst(), starts).map { Int($0 - $1) }.sorted()
  let medianGap: Any = gaps.isEmpty ? NSNull() : (gaps.count % 2 == 1 ? Double(gaps[gaps.count / 2]) : Double(gaps[gaps.count / 2 - 1] + gaps[gaps.count / 2]) / 2)
  let maxGap: Int? = gaps.last
  let expected: Double? = (wallStart != nil && wallEnd != nil) ? Double(wallEnd! - wallStart!) * playbackRate : nil
  let actual: Int? = (videoStartMs != nil && videoEndMs != nil) ? videoEndMs! - videoStartMs! : nil
  let tolerance: Double? = expected.map { max(3000, $0 * 0.05) }
  var progressConsistent: Any = NSNull()
  if frames.count >= 2, let e = expected, let a = actual, let t = tolerance { progressConsistent = abs(e - Double(a)) <= t }
  var gapCheck: Any = NSNull()
  if let s = shortestSubtitleMs, let m = maxGap { gapCheck = m < s }

  var invalidReasons: [String] = []
  if (progressConsistent as? Bool) == false { invalidReasons.append("progress_inconsistent") }
  if (gapCheck as? Bool) == false { invalidReasons.append("max_gap_exceeds_shortest_subtitle") }
  if !stillPlayingAtEnd { invalidReasons.append("playback_stopped_during_batch") }
  if let err = captureError { invalidReasons.append("capture_failed: \(err)") }

  let manifest: [String: Any] = [
    "video_id": videoID,
    "batch": batchDir,
    "capture_backend": "xvast-capture (AX + screencapture -l)",
    "window_id": win.id,
    "window_bounds_pt": boundsJSON(win.bounds),
    "playback_rate": playbackRate,
    "video_start_ms": videoStartMs ?? NSNull(),
    "video_end_ms": videoEndMs ?? NSNull(),
    "wall_start_ms": wallStart ?? NSNull(),
    "wall_end_ms": wallEnd ?? NSNull(),
    "expected_progress_ms": expected ?? NSNull(),
    "actual_progress_ms": actual ?? NSNull(),
    "progress_tolerance_ms": tolerance ?? NSNull(),
    "progress_consistent": progressConsistent,
    "frame_count": frames.count,
    "median_frame_gap_ms": medianGap,
    "max_frame_gap_ms": maxGap ?? NSNull(),
    "shortest_subtitle_ms": shortestSubtitleMs ?? NSNull(),
    "shortest_subtitle_gap_check": gapCheck,
    "capture_paused_for_review": args.flags.contains("pause-after-capture"),
    "layout_profile": layoutProfile,
    "status": invalidReasons.isEmpty ? "pending_manual_review" : "invalid",
    "invalid_reasons": invalidReasons,
    "viewport_review": [
      "window_dimensions": dims ?? NSNull(),
      "player_bounds": NSNull(),
      "video_content_bounds": NSNull(),
      "four_edges_visible": NSNull(),
      "player_top_visible": NSNull(),
      "player_bottom_visible": NSNull(),
      "player_left_visible": NSNull(),
      "player_right_visible": NSNull(),
      "controls_visible": NSNull(),
      "source_slide_complete": NSNull(),
      "scroll_state": "pending_manual_review",
      "evidence": frames.map { $0["file"]! },
    ] as [String: Any],
    "frames": frames,
  ]
  let manifestPath = (outputDir as NSString).appendingPathComponent("frames.json")
  let data = try JSONSerialization.data(withJSONObject: manifest, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
  try data.write(to: URL(fileURLWithPath: manifestPath + ".part"))
  try fm.moveItem(atPath: manifestPath + ".part", toPath: manifestPath)

  // A batch that produced no frames only holds a failure log. Move it aside so the batch name can be reused.
  var finalDir = outputDir
  var finalManifestPath = manifestPath
  if captureError != nil && frames.isEmpty {
    let failedRoot = (outputRoot as NSString).appendingPathComponent("_failed")
    let stamp = String(Int(Date().timeIntervalSince1970))
    finalDir = (failedRoot as NSString).appendingPathComponent("\(batchDir)-\(stamp)")
    try fm.createDirectory(atPath: failedRoot, withIntermediateDirectories: true)
    try fm.moveItem(atPath: outputDir, toPath: finalDir)
    finalManifestPath = (finalDir as NSString).appendingPathComponent("frames.json")
  }

  var summary = manifest
  summary.removeValue(forKey: "frames")
  summary.removeValue(forKey: "viewport_review")
  summary["output_dir"] = finalDir
  summary["manifest_path"] = finalManifestPath
  printJSON(summary)
  if let err = captureError { throw CLIError(message: "batch marked invalid — \(err)") }
}

// MARK: - main

let argv = CommandLine.arguments
guard argv.count >= 2 else {
  fail("usage: xvast-capture <status|play|pause|seek|park-cursor|screenshot|capture> [options]")
}
let command = argv[1]
let args = Args(argv.dropFirst(2), flagNames: ["resume-if-paused", "pause-after-capture"])

do {
  switch command {
  case "status":
    printJSON(statusJSON(try Player()))
  case "play", "pause":
    let player = try Player()
    let wantPlaying = command == "play"
    if player.isPlaying != wantPlaying { try player.press(wantPlaying ? "Play" : "Pause") }
    Thread.sleep(forTimeInterval: 0.3)
    printJSON(statusJSON(player))
  case "seek":
    let player = try Player()
    let target: Int
    if let by = args.values["by"] {
      guard let seconds = Int(by), let pos = player.positionMs else { throw CLIError(message: "--by must be signed integer seconds") }
      target = max(0, pos + seconds * 1000)
    } else {
      guard let t = parseClockMs(args.require("to")) else { throw CLIError(message: "--to must be H:MM:SS or seconds") }
      target = t
    }
    let actions = try player.seek(toMs: target, maxSteps: args.int("max-steps", default: 30)!)
    Thread.sleep(forTimeInterval: 0.3)
    var out = statusJSON(player)
    out["requested_ms"] = target
    out["seek_actions"] = actions
    printJSON(out)
  case "park-cursor":
    let player = try Player()
    let p = parkCursor(try xvastWindow(player))
    printJSON(["cursor_pt": ["x": Int(p.x), "y": Int(p.y)]])
  case "screenshot":
    let out = args.require("out")
    guard out.hasPrefix("/") else { throw CLIError(message: "--out must be an absolute path") }
    let player = try Player()
    let win = try xvastWindow(player)
    let ext = (out as NSString).pathExtension.lowercased()
    guard ["jpg", "png"].contains(ext) else { throw CLIError(message: "--out must end in .jpg or .png") }
    try FileManager.default.createDirectory(atPath: (out as NSString).deletingLastPathComponent, withIntermediateDirectories: true)
    let (facts, _) = try captureWindow(win.id, to: out, format: ext)
    var status = statusJSON(player)
    status["file"] = out
    status["dimensions_px"] = [facts.width, facts.height]
    status["size_bytes"] = facts.bytes
    printJSON(status)
  case "capture":
    try runCapture(args)
  default:
    fail("unknown command \(command)")
  }
} catch let e as CLIError {
  fail(e.message)
} catch {
  fail("\(error)")
}
