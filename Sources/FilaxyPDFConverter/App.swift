import SwiftUI
import AppKit

/// Ensures the app launches as a real, activated foreground app, and applies the
/// saved appearance before the first frame so there's no theme flash.
final class AppDelegate: NSObject, NSApplicationDelegate {
    /// Called when the app is opened with a PDF (Finder "Open With" or our Quick
    /// Action). Buffered until ContentView wires the handler, so a launch-by-file
    /// isn't lost.
    var openHandler: ((URL) -> Void)? { didSet { drainPending() } }
    private var pendingPDF: URL?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        AppSettings.shared.applyAppearance()
        #if !APP_STORE
        // Auto-configure the Finder Quick Action (no manual setup). Excluded from
        // the App Store build: a sandboxed MAS app can't write to ~/Library/Services.
        DispatchQueue.global(qos: .utility).async {
            QuickActionInstaller.installIfNeeded()
        }
        #endif
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func application(_ application: NSApplication, open urls: [URL]) {
        guard let pdf = urls.first(where: { $0.pathExtension.lowercased() == "pdf" }) else { return }
        NSApp.activate(ignoringOtherApps: true)
        if let h = openHandler { h(pdf) } else { pendingPDF = pdf }
    }
    private func drainPending() {
        guard let h = openHandler, let pdf = pendingPDF else { return }
        pendingPDF = nil
        h(pdf)
    }
}

/// Entry point for Filaxy PDF Converter.
///
/// A Filaxy Labs product. The app is a single premium container: the native
/// title bar is hidden and the app draws its own in-window chrome (title bar +
/// integrated menu + window controls), with Settings / Help / About as
/// in-window sheets. The macOS menu bar only carries keyboard shortcuts.
@main
struct FilaxyPDFConverterApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = ConversionViewModel()
    @StateObject private var settings = AppSettings.shared

    var body: some Scene {
        Window(settings.t(.appTitle), id: "main") {
            ContentView()
                .environmentObject(model)
                .environmentObject(settings)
                .frame(minWidth: 720, minHeight: 560)
                .preferredColorScheme(settings.colorScheme)
                .onAppear {
                    // When opened with a PDF (Finder/Quick Action), load it and
                    // convert immediately.
                    appDelegate.openHandler = { url in
                        model.accept(url)
                        model.convert()
                    }
                }
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentMinSize)
        .commands { shortcutCommands }
    }

    /// Keyboard shortcuts only — the visible menu is the in-window one. These let
    /// power users hit ⌘O / ⌘R / ⌘, without the chrome depending on the macOS bar.
    @CommandsBuilder private var shortcutCommands: some Commands {
        CommandGroup(replacing: .appInfo) {
            Button(settings.t(.menuAboutApp)) { model.showAbout = true }
        }
        CommandGroup(replacing: .appSettings) {}
        CommandGroup(replacing: .newItem) {
            Button(settings.t(.menuOpenPDF)) { model.pickPDF() }
                .keyboardShortcut("o", modifiers: .command)
        }
        CommandGroup(after: .newItem) {
            Button(settings.t(.menuConvert)) { model.convert() }
                .keyboardShortcut("r", modifiers: .command)
                .disabled(model.droppedPDF == nil)
            Button(settings.t(.menuRevealOutput)) { model.revealOutput() }
                .keyboardShortcut("r", modifiers: [.command, .shift])
                .disabled({ if case .done = model.phase { return false } else { return true } }())
        }
        CommandGroup(replacing: .help) {
            Button(settings.t(.menuHelpHowItWorks)) { model.showHowItWorks = true }
        }
    }
}
