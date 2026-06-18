import SwiftUI
import UniformTypeIdentifiers
import PDFKit

@MainActor
final class ConversionViewModel: ObservableObject {
    enum Phase: Equatable {
        case idle
        case working
        case done(ConversionResult)
        case failed(String)
        case batchWorking(done: Int, total: Int)
        case batchDone([BatchResult])
    }

    struct BatchResult: Identifiable, Equatable {
        let id = UUID()
        let name: String
        let output: String
        let passed: Bool
        let error: String?
    }

    @Published var phase: Phase = .idle
    @Published var droppedPDF: URL?
    @Published var droppedPDFs: [URL] = []   // when >1 source is queued (batch)
    @Published var showAbout = false
    @Published var showHowItWorks = false

    private let engine = ConversionEngine()
    private let settings = AppSettings.shared

    func accept(_ url: URL) {
        guard url.pathExtension.lowercased() == "pdf" else {
            phase = .failed(settings.t(.mustBePDF))
            return
        }
        droppedPDFs = []
        droppedPDF = url
        phase = .idle
    }

    /// Drop target may hand us several files. One PDF → single flow; many → batch.
    func acceptMany(_ urls: [URL]) {
        let pdfs = urls.filter { $0.pathExtension.lowercased() == "pdf" }
        guard !pdfs.isEmpty else { phase = .failed(settings.t(.mustBePDF)); return }
        if pdfs.count == 1 { accept(pdfs[0]) }
        else { droppedPDF = nil; droppedPDFs = pdfs; phase = .idle }
    }

    /// Pick a FOLDER and queue every PDF inside it for batch conversion.
    func pickFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.prompt = settings.t(.savePanelPrompt)
        guard panel.runModal() == .OK, let dir = panel.url else { return }
        let pdfs = ((try? FileManager.default.contentsOfDirectory(
            at: dir, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension.lowercased() == "pdf" }
            .sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
        guard !pdfs.isEmpty else { phase = .failed(settings.t(.batchNoPDFs)); return }
        droppedPDF = nil; droppedPDFs = pdfs
        convertBatch()
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
        if droppedPDFs.count > 1 { convertBatch(); return }
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

    /// Convert every queued PDF into ONE chosen folder, auto-named <source>.docx,
    /// with live progress and a per-file summary at the end.
    func convertBatch() {
        let pdfs = droppedPDFs
        guard !pdfs.isEmpty else { return }
        guard let folder = askDestinationFolder() else { return }    // user cancelled

        phase = .batchWorking(done: 0, total: pdfs.count)
        Task.detached(priority: .userInitiated) { [engine] in
            var results: [BatchResult] = []
            for (i, pdf) in pdfs.enumerated() {
                let dest = folder.appendingPathComponent(
                    pdf.deletingPathExtension().lastPathComponent + ".docx")
                do {
                    let r = try engine.convert(pdf: pdf, to: dest)
                    results.append(BatchResult(name: pdf.lastPathComponent,
                                               output: dest.path, passed: r.passed, error: nil))
                    await MainActor.run {
                        self.settings.addRecent(input: pdf.path, output: dest.path,
                                                passed: r.passed, at: Date())
                    }
                } catch {
                    results.append(BatchResult(name: pdf.lastPathComponent,
                                               output: "", passed: false,
                                               error: error.localizedDescription))
                }
                let done = i + 1
                await MainActor.run { self.phase = .batchWorking(done: done, total: pdfs.count) }
            }
            let final = results
            await MainActor.run { self.phase = .batchDone(final) }
        }
    }

    private func askDestinationFolder() -> URL? {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        panel.title = settings.t(.savePanelTitle)
        panel.message = settings.t(.batchFolderMessage)
        panel.prompt = settings.t(.savePanelPrompt)
        panel.directoryURL = Self.downloadsFolder   // default ALWAYS to Downloads
        guard panel.runModal() == .OK, let url = panel.url else { return nil }
        return url
    }

    private func askSaveLocation(for pdf: URL) -> URL? {
        let panel = NSSavePanel()
        panel.title = settings.t(.savePanelTitle)
        panel.message = settings.t(.savePanelMessage)
        panel.prompt = settings.t(.savePanelPrompt)
        panel.nameFieldStringValue = pdf.deletingPathExtension().lastPathComponent + ".docx"
        panel.allowedContentTypes = [UTType(filenameExtension: "docx") ?? .data]
        panel.canCreateDirectories = true
        panel.directoryURL = Self.downloadsFolder   // default ALWAYS to Downloads
        guard panel.runModal() == .OK, let url = panel.url else { return nil }
        return url
    }

    /// The user's Downloads folder — the default save location for every export.
    static var downloadsFolder: URL? {
        FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
    }

    func reset() {
        droppedPDF = nil
        droppedPDFs = []
        phase = .idle
    }

    /// Reveal in Finder the folder a batch wrote to (from its first valid result).
    func revealBatchFolder(_ results: [BatchResult]) {
        if let first = results.first(where: { !$0.output.isEmpty }) { reveal(first.output) }
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

    // MARK: - Compare with original (side by side)
    private var compareWindow: NSWindow?

    /// Put the SOURCE PDF on the left half of the screen (in our own window, which
    /// we can position) and open the converted .docx in Word on the right — so the
    /// user can eyeball the conversion against the original, the way you verify it.
    func compareWithOriginal() {
        guard case let .done(result) = phase else { return }
        showOriginalPDF(URL(fileURLWithPath: result.input))
        openInWord(result.output)
    }

    private func showOriginalPDF(_ url: URL) {
        guard let doc = PDFDocument(url: url) else { reveal(url.path); return }
        guard let screen = NSScreen.main else { return }
        let vf = screen.visibleFrame
        let left = NSRect(x: vf.minX, y: vf.minY, width: floor(vf.width / 2), height: vf.height)

        let pdfView = PDFView(frame: left)
        pdfView.document = doc
        pdfView.autoScales = true
        pdfView.displayMode = .singlePageContinuous

        let win = compareWindow ?? NSWindow(
            contentRect: left,
            styleMask: [.titled, .closable, .resizable, .miniaturizable],
            backing: .buffered, defer: false)
        win.title = url.lastPathComponent + " — " + settings.t(.appTitle)
        win.contentView = pdfView
        win.setFrame(left, display: true)
        win.isReleasedWhenClosed = false
        win.makeKeyAndOrderFront(nil)
        compareWindow = win
    }
}
