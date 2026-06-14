import SwiftUI
import AppKit

/// The app's own icon, shown inside the UI (title bar, About) so the in-app
/// chrome matches the Dock/Finder icon. Loads the bundled PNG; falls back to the
/// running app icon, then to an SF Symbol if neither is available.
struct AppLogo: View {
    var size: CGFloat

    var body: some View {
        if let img = Self.image {
            Image(nsImage: img)
                .resizable()
                .interpolation(.high)
                .frame(width: size, height: size)
        } else {
            Image(systemName: "doc.on.doc.fill")
                .font(.system(size: size * 0.82))
                .foregroundStyle(.tint)
        }
    }

    static let image: NSImage? = {
        if let url = Bundle.main.url(forResource: "AppIconImage", withExtension: "png"),
           let img = NSImage(contentsOf: url) {
            return img
        }
        return NSApp.applicationIconImage
    }()
}
