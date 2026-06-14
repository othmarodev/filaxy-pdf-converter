import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class ConversionViewModel: ObservableObject {
    enum Phase: Equatable {
        case idle
        case working
        case done(ConversionResult)
        case failed(String)
    }

    @Published var phase: Phase = .idle
    @Published var droppedPDF: URL?
    @Published var showAbout = false
    @Published var showHowItWorks = false

    private let engine = ConversionEngine()
    private let settings = AppSettings.shared

    func accept(_ url: URL) {
        guard url.pathExtension.lowercased() == "pdf" else {
            phase = .failed(settings.t(.mustBePDF))
            return
        }
        droppedPDF = url
        phase = .idle
    }

    /// Open-panel entry point used by the drop zone tap and the File ▸ Open menu.
    func pickPDF() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.pdf]
        panel.allowsMultipleSelection = false
        panel.prompt = settings.t(.savePanelPrompt)
        if panel.runModal() == .OK, let url = panel.url { accept(url) }
    }

    /// Ask the user WHERE to save (per their preference), then convert. The save
    /// panel remembers the last folder used.
    func convert() {
        guard let pdf = droppedPDF else { return }
        guard let dest = askSaveLocation(for: pdf) else { return }   // user cancelled

        phase = .working
        Task.detached(priority: .userInitiated) { [engine] in
            do {
                let result = try engine.convert(pdf: pdf, to: dest)
                await MainActor.run {
                    self.settings.addRecent(input: pdf.path, output: dest.path,
                                            passed: result.passed, at: Date())
                    self.phase = .done(result)
                }
            } catch {
                await MainActor.run { self.phase = .failed(error.localizedDescription) }
            }
        }
    }

    private func askSaveLocation(for pdf: URL) -> URL? {
        let panel = NSSavePanel()
        panel.title = settings.t(.savePanelTitle)
        panel.message = settings.t(.savePanelMessage)
        panel.prompt = settings.t(.savePanelPrompt)
        panel.nameFieldStringValue = pdf.deletingPathExtension().lastPathComponent + ".docx"
        panel.allowedContentTypes = [UTType(filenameExtension: "docx") ?? .data]
        panel.canCreateDirectories = true
        if !settings.lastSaveFolder.isEmpty {
            let dir = URL(fileURLWithPath: settings.lastSaveFolder)
            if FileManager.default.fileExists(atPath: dir.path) { panel.directoryURL = dir }
        }
        guard panel.runModal() == .OK, let url = panel.url else { return nil }
        settings.lastSaveFolder = url.deletingLastPathComponent().path
        return url
    }

    func reset() {
        droppedPDF = nil
        phase = .idle
    }

    func revealOutput() {
        if case let .done(result) = phase { reveal(result.output) }
    }

    func openOutputInWord() {
        if case let .done(result) = phase { openInWord(result.output) }
    }

    /// Open a .docx in Microsoft Word if installed, else the system default.
    func openInWord(_ path: String) {
        let url = URL(fileURLWithPath: path)
        let ws = NSWorkspace.shared
        if let word = ws.urlForApplication(withBundleIdentifier: "com.microsoft.Word") {
            ws.open([url], withApplicationAt: word, configuration: NSWorkspace.OpenConfiguration())
        } else {
            ws.open(url)
        }
    }

    func reveal(_ path: String) {
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
    }
}
