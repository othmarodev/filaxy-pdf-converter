import SwiftUI
import AppKit

/// In-window window chrome — the app draws its OWN title bar and traffic-light
/// controls inside the container (native title bar hidden), so everything lives
/// in one premium surface. Mirrors the Filaxy Files pattern.

/// Grabs the hosting NSWindow once it exists so we can hide the native title
/// bar / traffic lights and let our custom chrome take over.
struct WindowAccessor: NSViewRepresentable {
    let onResolve: (NSWindow) -> Void
    func makeNSView(context: Context) -> NSView {
        let v = NSView()
        DispatchQueue.main.async {
            if let w = v.window { onResolve(w) }
        }
        return v
    }
    func updateNSView(_ nsView: NSView, context: Context) {}
}

/// Hides the native title bar + traffic lights and makes the content fill to the
/// top edge. Apply once via `.background(ConfigureWindow())`.
struct ConfigureWindow: View {
    var body: some View {
        WindowAccessor { window in
            // Keep the native macOS traffic-light buttons (close/minimize/zoom)
            // visible on the top-left — the standard, expected window controls.
            window.titlebarAppearsTransparent = true
            window.titleVisibility = .hidden
            window.styleMask.insert(.fullSizeContentView)
            window.isMovableByWindowBackground = false
        }
    }
}

// MARK: - Drag area (lets the custom title bar move the window)

private final class DraggableNSView: NSView {
    override var mouseDownCanMoveWindow: Bool { true }
}
struct WindowDragArea: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView { DraggableNSView() }
    func updateNSView(_ nsView: NSView, context: Context) {}
}

