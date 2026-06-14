import SwiftUI

/// The fidelity report — the product's signature. After converting we don't
/// just hand back a file; we show *how faithful* it is to the original.
struct ResultView: View {
    @EnvironmentObject var model: ConversionViewModel
    @EnvironmentObject var settings: AppSettings
    let result: ConversionResult

    @State private var showConfetti = false

    var body: some View {
        VStack(spacing: 16) {
            FidelityRing(score: result.fidelity.textScore, passed: result.verdict == .pass)
                .padding(.top, 4)
            verdictBadge
            ScrollView {
                VStack(spacing: 12) {
                    metric(settings.t(.metricTextPresent),
                           result.fidelity.textScore >= 99.5 ? settings.t(.metricTextComplete)
                               : "\(Int(result.fidelity.textScore.rounded()))%",
                           ok: result.fidelity.textScore >= 98)
                    metric(settings.t(.metricSensitive),
                           result.fidelity.sensitiveIssues.isEmpty ? settings.t(.metricSensitiveOK)
                               : "\(result.fidelity.sensitiveIssues.count) \(settings.t(.metricSensitiveReview))",
                           ok: result.fidelity.sensitiveIssues.isEmpty)
                    metric(settings.t(.metricFonts),
                           result.layout.passed ? settings.t(.metricFontsOK) : settings.t(.metricFontsReview),
                           ok: result.layout.passed)
                    metric(settings.t(.metricGraphics),
                           result.fidelity.images.match ? settings.t(.metricGraphicsOK) : settings.t(.metricGraphicsReview),
                           ok: result.fidelity.images.match)

                    ForEach(result.fidelity.sensitiveIssues, id: \.self) { issue in
                        issueRow(issue)
                    }
                    ForEach(result.layout.issues, id: \.self) { issue in
                        issueRow(issue)
                    }
                    overlayPreview
                    ForEach(result.warnings, id: \.self) { w in
                        issueRow(w, icon: "info.circle")
                    }
                }
                .padding(.horizontal, 24)
            }
            HStack {
                Button(settings.t(.convertAnother)) { model.reset() }
                Button {
                    model.revealOutput()
                } label: {
                    Label(settings.t(.showInFinder), systemImage: "folder")
                }
                Button {
                    model.openOutputInWord()
                } label: {
                    Label(settings.t(.openInWord), systemImage: "arrow.up.forward.app")
                }.buttonStyle(.borderedProminent)
            }
            Text("\(result.pages) \(settings.t(.pagesElapsed)) · \(String(format: "%.2f", result.elapsedS))s")
                .font(.caption2).foregroundStyle(.tertiary)
        }
        .padding(.vertical, 20)
        .overlay(alignment: .top) {
            if showConfetti && result.verdict == .pass {
                ConfettiView().frame(height: 360).allowsHitTesting(false)
            }
        }
        .onAppear {
            showConfetti = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) { showConfetti = false }
        }
    }

    private var verdictBadge: some View {
        let pass = result.verdict == .pass
        return Label(pass ? settings.t(.verdictPass) : settings.t(.verdictReview),
                     systemImage: pass ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
            .font(.title3.weight(.semibold))
            .foregroundStyle(pass ? .green : .orange)
    }

    private func metric(_ title: String, _ value: String, ok: Bool) -> some View {
        HStack {
            Image(systemName: ok ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundStyle(ok ? .green : .orange)
            Text(title)
            Spacer()
            Text(value).foregroundStyle(.secondary).monospacedDigit()
        }
        .padding(12)
        .background(Color.secondary.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
    }

    /// When the layout check flags a problem, show the annotated render so the
    /// user can see exactly which region drifted.
    @ViewBuilder private var overlayPreview: some View {
        if !result.layout.passed,
           let path = result.layout.overlayPath,
           let img = NSImage(contentsOfFile: path) {
            VStack(alignment: .leading, spacing: 6) {
                Text(settings.t(.zonesToReview))
                    .font(.caption).foregroundStyle(.secondary)
                Image(nsImage: img)
                    .resizable().scaledToFit()
                    .frame(maxHeight: 320)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color.secondary.opacity(0.2)))
            }
            .padding(.top, 4)
        }
    }

    private func issueRow(_ text: String, icon: String = "exclamationmark.triangle") -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon).foregroundStyle(.orange)
            Text(text).font(.caption).foregroundStyle(.secondary)
            Spacer(minLength: 0)
        }
        .padding(10)
        .background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
    }
}
