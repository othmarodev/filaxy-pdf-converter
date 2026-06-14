import SwiftUI
import AppKit
import CoreImage

/// USDT (TRON / TRC20) donation address. Public by design — it's a receiving
/// address meant to be shared. The QR is generated locally from this string,
/// so the address shown and the QR always encode the SAME value.
let usdtTRC20Address = "TBzBitnntNvsnuP5XBwi3FhjDpVf5487sx"

/// Crypto donation option: locally-generated QR + copyable address + a clear
/// network warning (sending on the wrong chain loses the funds).
struct CryptoDonationView: View {
    @EnvironmentObject var settings: AppSettings
    @State private var copied = false

    var body: some View {
        VStack(spacing: 10) {
            Label(settings.t(.cryptoHeading), systemImage: "bitcoinsign.circle.fill")
                .font(.headline).foregroundStyle(.green)

            if let qr = Self.qr(usdtTRC20Address) {
                Image(nsImage: qr)
                    .interpolation(.none).resizable()
                    .frame(width: 132, height: 132)
                    .padding(8)
                    .background(Color.white)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.primary.opacity(0.12)))
            }

            HStack(spacing: 8) {
                Text(usdtTRC20Address)
                    .font(.system(size: 11, design: .monospaced))
                    .textSelection(.enabled)
                    .lineLimit(1).truncationMode(.middle)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 10).padding(.vertical, 7)
                    .background(RoundedRectangle(cornerRadius: 7).fill(Color.primary.opacity(0.05)))
                Button(action: copy) {
                    Label(copied ? settings.t(.copied) : settings.t(.copyAddress),
                          systemImage: copied ? "checkmark" : "doc.on.doc")
                        .font(.caption)
                }
                .buttonStyle(.bordered)
                .tint(copied ? .green : .accentColor)
            }

            Text(settings.t(.cryptoWarning))
                .font(.caption2).foregroundStyle(.orange)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func copy() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(usdtTRC20Address, forType: .string)
        withAnimation { copied = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.8) {
            withAnimation { copied = false }
        }
    }

    /// Generate a crisp QR for `string` using CoreImage — no network needed.
    static func qr(_ string: String) -> NSImage? {
        guard let data = string.data(using: .ascii),
              let filter = CIFilter(name: "CIQRCodeGenerator") else { return nil }
        filter.setValue(data, forKey: "inputMessage")
        filter.setValue("M", forKey: "inputCorrectionLevel")
        guard let output = filter.outputImage?
                .transformed(by: CGAffineTransform(scaleX: 12, y: 12)) else { return nil }
        let rep = NSCIImageRep(ciImage: output)
        let img = NSImage(size: rep.size)
        img.addRepresentation(rep)
        return img
    }
}
