import Foundation

/// Decoded form of the JSON contract emitted by the bundled engine
/// (`engine/cli.py`). This is the single boundary between the native Swift
/// shell and the conversion+verification engine.
struct ConversionResult: Codable, Identifiable, Equatable {
    var id = UUID()

    let input: String
    let output: String
    let pages: Int
    let elapsedS: Double
    let hasTextLayer: Bool
    let scannedPages: [Int]
    let warnings: [String]
    let passed: Bool          // overall: data AND layout both held up
    let fidelity: Fidelity    // data fidelity (text / numbers / images)
    let layout: Layout        // structural fidelity (tables / positions)

    enum CodingKeys: String, CodingKey {
        case input, output, pages, warnings, passed, fidelity, layout
        case elapsedS = "elapsed_s"
        case hasTextLayer = "has_text_layer"
        case scannedPages = "scanned_pages"
    }

    struct Fidelity: Codable, Equatable {
        let textScore: Double
        let images: Images
        let tablesOutput: Int
        let missingTokens: [String]
        let sensitiveIssues: [String]
        let passed: Bool

        enum CodingKeys: String, CodingKey {
            case images, passed
            case textScore = "text_score"
            case tablesOutput = "tables_output"
            case missingTokens = "missing_tokens"
            case sensitiveIssues = "sensitive_issues"
        }

        struct Images: Codable, Equatable {
            let source: Int
            let output: Int
            let match: Bool
        }
    }

    /// Structural fidelity: did the layout (tables, positioned blocks) survive?
    struct Layout: Codable, Equatable {
        let srcTables: Int
        let outTables: Int
        let issues: [String]
        let score: Double
        let passed: Bool
        let overlayPath: String?

        enum CodingKeys: String, CodingKey {
            case issues, score, passed
            case srcTables = "src_tables"
            case outTables = "out_tables"
            case overlayPath = "overlay_path"
        }
    }

    /// Headline verdict for the UI — honest only when BOTH checks pass.
    var verdict: Verdict { passed ? .pass : .review }

    enum Verdict { case pass, review }
}
