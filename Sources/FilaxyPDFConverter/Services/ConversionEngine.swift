import Foundation

/// Bridges the native app to the offline conversion+verification engine.
///
/// In a shipped build the engine is a frozen binary inside the .app bundle
/// (`Contents/Resources/engine/filaxy-engine`). In a dev checkout it is the
/// Python package under `<repo>/engine` run via the project venv. We resolve
/// whichever is present.
enum ConversionEngineError: LocalizedError {
    case engineNotFound
    case failed(String)
    case badOutput(String)

    var errorDescription: String? {
        switch self {
        case .engineNotFound:
            return "No se encontró el motor de conversión."
        case .failed(let m): return "La conversión falló: \(m)"
        case .badOutput(let m): return "Respuesta inesperada del motor: \(m)"
        }
    }
}

struct ConversionEngine {

    /// Convert `pdf` → `docx` and return the verified fidelity result.
    func convert(pdf: URL, to docx: URL) throws -> ConversionResult {
        let engine = try Self.resolveEngine()
        let proc = Process()
        proc.executableURL = engine.launchPath
        proc.arguments = engine.arguments(input: pdf.path, output: docx.path)
        proc.currentDirectoryURL = engine.workingDirectory

        let out = Pipe(), err = Pipe()
        proc.standardOutput = out
        proc.standardError = err
        try proc.run()
        proc.waitUntilExit()

        let data = out.fileHandleForReading.readDataToEndOfFile()
        guard !data.isEmpty else {
            let e = String(decoding: err.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            throw ConversionEngineError.failed(e.isEmpty ? "sin salida" : e)
        }
        do {
            return try JSONDecoder().decode(ConversionResult.self, from: data)
        } catch {
            throw ConversionEngineError.badOutput(String(decoding: data, as: UTF8.self))
        }
    }

    // MARK: - Engine resolution

    private struct Engine {
        let launchPath: URL
        let workingDirectory: URL
        let isFrozen: Bool
        func arguments(input: String, output: String) -> [String] {
            isFrozen
                ? [input, output, "--json"]
                : ["-m", "engine.cli", input, output, "--json"]
        }
    }

    /// Find the engine. First look for the frozen binary next to the running
    /// executable (shipped app); otherwise ascend the filesystem **recursively**
    /// from this source file's location until we find a checkout that contains
    /// `engine/cli.py`, and run it through the project venv.
    private static func resolveEngine() throws -> Engine {
        let fm = FileManager.default

        // 1. Shipped: Contents/Resources/engine/filaxy-engine
        let exeDir = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/engine")
        let frozen = exeDir.appendingPathComponent("filaxy-engine")
        if fm.isExecutableFile(atPath: frozen.path) {
            return Engine(launchPath: frozen, workingDirectory: exeDir, isFrozen: true)
        }

        // 2. Dev: ascend recursively to find the repo root holding engine/cli.py
        let start = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()  // Services/
        guard let repo = ascendForRepoRoot(from: start, fm: fm) else {
            throw ConversionEngineError.engineNotFound
        }
        let venvPython = repo.appendingPathComponent(".venv/bin/python3")
        let python = fm.isExecutableFile(atPath: venvPython.path)
            ? venvPython
            : URL(fileURLWithPath: "/usr/bin/python3")
        return Engine(launchPath: python, workingDirectory: repo, isFrozen: false)
    }

    /// Recursively walk up the directory tree looking for a folder that
    /// contains `engine/cli.py`. Base cases: found it → return; reached the
    /// filesystem root (parent == self) → return nil. Bounded by the natural
    /// depth of an absolute path, so no stack-depth concern.
    private static func ascendForRepoRoot(from dir: URL, fm: FileManager) -> URL? {
        let marker = dir.appendingPathComponent("engine/cli.py")
        if fm.fileExists(atPath: marker.path) { return dir }
        let parent = dir.deletingLastPathComponent()
        if parent.path == dir.path { return nil }   // hit "/"
        return ascendForRepoRoot(from: parent, fm: fm)
    }
}
