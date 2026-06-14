import SwiftUI

/// A one-shot confetti burst — colored pieces fall and fade. Plays on appear.
/// Non-interactive (never blocks clicks).
struct ConfettiView: View {
    private struct Piece: Identifiable {
        let id = UUID()
        let x = CGFloat.random(in: 0.0...1.0)
        let delay = Double.random(in: 0.0...0.35)
        let duration = Double.random(in: 1.4...2.6)
        let w = CGFloat.random(in: 6...12)
        let h = CGFloat.random(in: 8...16)
        let drift = CGFloat.random(in: -60...60)
        let spin = Double.random(in: 180...720)
        let color = [Color.blue, .green, .pink, .orange, .purple, .yellow, .red]
            .randomElement()!
    }
    private let pieces = (0..<90).map { _ in Piece() }
    @State private var go = false

    var body: some View {
        GeometryReader { geo in
            ZStack {
                ForEach(pieces) { p in
                    RoundedRectangle(cornerRadius: 2)
                        .fill(p.color)
                        .frame(width: p.w, height: p.h)
                        .rotationEffect(.degrees(go ? p.spin : 0))
                        .position(
                            x: p.x * geo.size.width + (go ? p.drift : 0),
                            y: go ? geo.size.height + 30 : -30
                        )
                        .opacity(go ? 0 : 1)
                        .animation(.easeIn(duration: p.duration).delay(p.delay), value: go)
                }
            }
        }
        .allowsHitTesting(false)
        .onAppear { go = true }
    }
}

/// An animated circular fidelity gauge. The ring sweeps from 0 to `score`% on
/// appear; the centre shows the verdict seal and the percentage.
struct FidelityRing: View {
    let score: Double      // 0…100
    let passed: Bool
    @State private var progress: CGFloat = 0
    @State private var shownScore: Double = 0

    private var tint: Color { passed ? .green : .orange }

    var body: some View {
        ZStack {
            Circle().stroke(Color.primary.opacity(0.08), lineWidth: 12)
            Circle()
                .trim(from: 0, to: progress)
                .stroke(tint.gradient,
                        style: StrokeStyle(lineWidth: 12, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .shadow(color: tint.opacity(0.35), radius: 5)
            VStack(spacing: 1) {
                Image(systemName: passed ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundStyle(tint)
                Text("\(Int(shownScore.rounded()))%")
                    .font(.system(size: 24, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(.primary)
            }
        }
        .frame(width: 124, height: 124)
        .onAppear {
            withAnimation(.easeOut(duration: 1.1)) { progress = CGFloat(score / 100) }
            // count the number up alongside the ring sweep
            let steps = 30
            for i in 0...steps {
                let t = Double(i) / Double(steps)
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.1 * t) {
                    shownScore = score * t
                }
            }
        }
    }
}
