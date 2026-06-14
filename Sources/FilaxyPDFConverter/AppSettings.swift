import SwiftUI
import AppKit

/// Premium app preferences — language, appearance and last-used save folder —
/// persisted via @AppStorage and observed app-wide so changing them updates the
/// whole UI live (no relaunch). One shared instance is also injected into the
/// SwiftUI environment so every view re-renders on change.
@MainActor
final class AppSettings: ObservableObject {
    static let shared = AppSettings()

    // MARK: Language
    enum Language: String, CaseIterable, Identifiable {
        case system, es, en
        var id: String { rawValue }
    }

    @AppStorage("app.language") private var languageRaw = Language.system.rawValue
    var language: Language {
        get { Language(rawValue: languageRaw) ?? .system }
        set { languageRaw = newValue.rawValue; objectWillChange.send() }
    }

    /// The concrete language to render in ("es"/"en"), resolving `.system` from
    /// the user's preferred locale.
    var lang: String {
        switch language {
        case .es: return "es"
        case .en: return "en"
        case .system:
            let pref = (Locale.preferredLanguages.first ?? "en").lowercased()
            return pref.hasPrefix("es") ? "es" : "en"
        }
    }

    // MARK: Appearance
    enum Appearance: String, CaseIterable, Identifiable {
        case system, light, dark
        var id: String { rawValue }
    }

    @AppStorage("app.appearance") private var appearanceRaw = Appearance.system.rawValue
    var appearance: Appearance {
        get { Appearance(rawValue: appearanceRaw) ?? .system }
        set { appearanceRaw = newValue.rawValue; applyAppearance(); objectWillChange.send() }
    }

    var colorScheme: ColorScheme? {
        switch appearance {
        case .system: return nil
        case .light:  return .light
        case .dark:   return .dark
        }
    }

    /// Apply to the whole NSApplication so menus, panels and the title bar follow
    /// the chosen theme — not only the SwiftUI content.
    func applyAppearance() {
        switch appearance {
        case .system: NSApp.appearance = nil
        case .light:  NSApp.appearance = NSAppearance(named: .aqua)
        case .dark:   NSApp.appearance = NSAppearance(named: .darkAqua)
        }
    }

    // MARK: Save location (the panel remembers where you last saved)
    @AppStorage("app.lastSaveFolder") var lastSaveFolder = ""

    // MARK: Recent conversions
    @AppStorage("app.recents") private var recentsRaw = "[]"
    var recents: [RecentItem] {
        get { (try? JSONDecoder().decode([RecentItem].self, from: Data(recentsRaw.utf8))) ?? [] }
        set {
            if let data = try? JSONEncoder().encode(newValue),
               let s = String(data: data, encoding: .utf8) { recentsRaw = s }
            objectWillChange.send()
        }
    }
    func addRecent(input: String, output: String, passed: Bool, at date: Date) {
        var list = recents.filter { $0.output != output }
        list.insert(RecentItem(input: input, output: output, date: date, passed: passed), at: 0)
        recents = Array(list.prefix(8))
    }
    func clearRecents() { recents = [] }

    private init() {}

    /// One past conversion, persisted for the Recents list.
    struct RecentItem: Codable, Identifiable, Equatable {
        var id = UUID()
        let input: String
        let output: String
        let date: Date
        let passed: Bool
        var name: String { (output as NSString).lastPathComponent }
        var exists: Bool { FileManager.default.fileExists(atPath: output) }
    }

    // MARK: Localization
    /// Translate a key into the active language. A runtime table (not .strings)
    /// so language switches apply live without a bundle reload.
    func t(_ key: L10n) -> String { key.value(lang) }
}
