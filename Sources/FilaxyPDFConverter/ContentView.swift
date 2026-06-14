import SwiftUI
import UniformTypeIdentifiers

/// One premium container: a custom in-window title bar, a large ALWAYS-VISIBLE
/// menu bar (File dropdown + How-it-works + About on the left; Appearance and
/// Language as individual segmented controls on the right), the conversion
/// surface, and a brand footer. Native title bar hidden — Filaxy Files model.
struct ContentView: View {
    @EnvironmentObject var model: ConversionViewModel
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        VStack(spacing: 0) {
            TitleBarView()
            Divider().opacity(0.5)
            MenuBarView()
            Divider().opacity(0.4)
            ZStack {
                switch model.phase {
                case .idle:    DropZoneView()
                case .working: WorkingView()
                case .done(let r):   ResultView(result: r)
                case .failed(let m): FailureView(message: m)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .animation(.easeInOut(duration: 0.2), value: model.phase)
            Divider().opacity(0.4)
            FooterBar()
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .background(ConfigureWindow())
        .sheet(isPresented: $model.showAbout) { AboutView() }
        .sheet(isPresented: $model.showHowItWorks) { HowItWorksView() }
    }
}

// MARK: - Custom in-window title bar (logo · title · window controls)

private struct TitleBarView: View {
    @EnvironmentObject var settings: AppSettings
    var body: some View {
        ZStack {
            WindowDragArea()
            HStack(spacing: 0) {
                // Leading space for the native macOS traffic-light buttons.
                AppLogo(size: 20).padding(.leading, 78)
                Text(settings.t(.appTitle))
                    .font(.system(size: 12, weight: .semibold)).padding(.leading, 8)
                Text("1.0")
                    .font(.system(size: 10, weight: .medium)).foregroundStyle(.secondary)
                    .padding(.horizontal, 5).padding(.vertical, 1)
                    .background(RoundedRectangle(cornerRadius: 3).fill(Color.primary.opacity(0.06)))
                    .padding(.leading, 6)
                Spacer(minLength: 12)
            }
        }
        .frame(height: 38)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

// MARK: - Large always-visible menu bar

private struct MenuBarView: View {
    @EnvironmentObject var model: ConversionViewModel
    @EnvironmentObject var settings: AppSettings

    private var notDone: Bool { if case .done = model.phase { return false } else { return true } }

    var body: some View {
        HStack(spacing: 10) {
            BarMenu(title: settings.t(.menuFile), systemImage: "doc.fill") {
                Button(settings.t(.menuOpenPDF)) { model.pickPDF() }
                Button(settings.t(.menuConvert)) { model.convert() }
                    .disabled(model.droppedPDF == nil)
                Button(settings.t(.menuRevealOutput)) { model.revealOutput() }
                    .disabled(notDone)
            }
            BarButton(title: settings.t(.menuHelpHowItWorks), systemImage: "sparkles") {
                model.showHowItWorks = true
            }
            BarButton(title: settings.t(.settingsAbout), systemImage: "info.circle.fill") {
                model.showAbout = true
            }

            Spacer()

            // Appearance — individual segmented control with selected state
            SegmentedGroup(label: settings.t(.settingsAppearance)) {
                SegButton(symbol: "sun.max.fill", help: settings.t(.appearanceLight),
                          selected: settings.appearance == .light) { settings.appearance = .light }
                SegButton(symbol: "circle.lefthalf.filled", help: settings.t(.appearanceSystem),
                          selected: settings.appearance == .system) { settings.appearance = .system }
                SegButton(symbol: "moon.fill", help: settings.t(.appearanceDark),
                          selected: settings.appearance == .dark) { settings.appearance = .dark }
            }

            // Language — individual segmented control with selected state
            SegmentedGroup(label: settings.t(.settingsLanguage)) {
                SegButton(text: "🌐", help: settings.t(.langSystem),
                          selected: settings.language == .system) { settings.language = .system }
                SegButton(text: "🇪🇸", help: settings.t(.langSpanish),
                          selected: settings.language == .es) { settings.language = .es }
                SegButton(text: "🇺🇸", help: settings.t(.langEnglish),
                          selected: settings.language == .en) { settings.language = .en }
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 9)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

// MARK: - Beautiful bar components (hover + selected effects)

/// A dropdown styled like the big bar buttons, with a hover lift.
private struct BarMenu<Content: View>: View {
    let title: String
    let systemImage: String
    @ViewBuilder var content: () -> Content
    @State private var hovering = false

    var body: some View {
        Menu { content() } label: {
            HStack(spacing: 7) {
                Image(systemName: systemImage).font(.system(size: 13))
                Text(title).font(.system(size: 13, weight: .medium))
                Image(systemName: "chevron.down")
                    .font(.system(size: 8, weight: .bold)).foregroundStyle(.secondary)
            }
            .foregroundStyle(hovering ? Color.accentColor : Color.primary.opacity(0.85))
            .padding(.horizontal, 13).padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .fill(hovering ? Color.accentColor.opacity(0.12) : Color.primary.opacity(0.04))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .stroke(Color.accentColor.opacity(hovering ? 0.35 : 0), lineWidth: 1)
            )
            .scaleEffect(hovering ? 1.04 : 1.0)
            .contentShape(Rectangle())
        }
        .menuStyle(.borderlessButton)
        .menuIndicator(.hidden)
        .fixedSize()
        .animation(.easeOut(duration: 0.16), value: hovering)
        .onHover { hovering = $0 }
    }
}

/// A large action button with the same hover treatment as BarMenu.
private struct BarButton: View {
    let title: String
    let systemImage: String
    let action: () -> Void
    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 7) {
                Image(systemName: systemImage).font(.system(size: 13))
                Text(title).font(.system(size: 13, weight: .medium))
            }
            .foregroundStyle(hovering ? Color.accentColor : Color.primary.opacity(0.85))
            .padding(.horizontal, 13).padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .fill(hovering ? Color.accentColor.opacity(0.12) : Color.primary.opacity(0.04))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .stroke(Color.accentColor.opacity(hovering ? 0.35 : 0), lineWidth: 1)
            )
            .scaleEffect(hovering ? 1.04 : 1.0)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .fixedSize()
        .animation(.easeOut(duration: 0.16), value: hovering)
        .onHover { hovering = $0 }
    }
}

/// A pill that groups segmented buttons with a tiny caption label above.
private struct SegmentedGroup<Content: View>: View {
    let label: String
    @ViewBuilder var content: () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(.system(size: 8, weight: .bold)).tracking(0.6)
                .foregroundStyle(.tertiary)
                .padding(.leading, 4)
            HStack(spacing: 3) { content() }
                .padding(3)
                .background(
                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .fill(Color.primary.opacity(0.05))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .stroke(Color.primary.opacity(0.06), lineWidth: 1)
                )
        }
    }
}

/// One segment: shows an SF Symbol OR a text glyph (flag). Filled accent when
/// selected, subtle highlight on hover, with a springy animation.
private struct SegButton: View {
    var symbol: String? = nil
    var text: String? = nil
    let help: String
    let selected: Bool
    let action: () -> Void
    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            Group {
                if let symbol {
                    Image(systemName: symbol).font(.system(size: 14, weight: .semibold))
                } else if let text {
                    Text(text).font(.system(size: 16))
                }
            }
            .frame(width: 34, height: 28)
            .foregroundStyle(selected ? Color.white
                             : (hovering ? Color.accentColor : Color.primary.opacity(0.7)))
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(selected ? Color.accentColor
                          : (hovering ? Color.accentColor.opacity(0.14) : Color.clear))
                    .shadow(color: selected ? Color.accentColor.opacity(0.35) : .clear,
                            radius: selected ? 4 : 0, y: selected ? 1 : 0)
            )
            .scaleEffect(selected ? 1.0 : (hovering ? 1.08 : 1.0))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help(help)
        .animation(.spring(response: 0.28, dampingFraction: 0.7), value: selected)
        .animation(.easeOut(duration: 0.14), value: hovering)
        .onHover { hovering = $0 }
    }
}

// MARK: - Brand footer

private struct FooterBar: View {
    @EnvironmentObject var settings: AppSettings
    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "checkmark.seal").font(.system(size: 10)).foregroundStyle(.tint)
            Text(settings.t(.appSubtitle)).font(.caption2).foregroundStyle(.secondary)
            Spacer()
            Text(settings.t(.brand)).font(.caption2).foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 14).padding(.vertical, 6)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

// MARK: - Conversion surfaces

private struct DropZoneView: View {
    @EnvironmentObject var model: ConversionViewModel
    @EnvironmentObject var settings: AppSettings
    @State private var targeted = false

    var body: some View {
        VStack(spacing: 16) {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(style: StrokeStyle(lineWidth: 2, dash: [8]))
                .foregroundStyle(targeted ? Color.accentColor : Color.secondary.opacity(0.4))
                .frame(height: 220)
                .background(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(targeted ? Color.accentColor.opacity(0.07) : Color.clear)
                )
                .overlay {
                    VStack(spacing: 10) {
                        Image(systemName: targeted ? "arrow.down.doc.fill" : "arrow.down.doc")
                            .font(.system(size: 40, weight: .light))
                            .foregroundStyle(targeted ? Color.accentColor : Color.secondary)
                            .scaleEffect(targeted ? 1.15 : 1.0)
                            .offset(y: targeted ? -4 : 0)
                        Text(model.droppedPDF?.lastPathComponent ?? settings.t(.dropTitle))
                            .font(.title3)
                        Text(model.droppedPDF == nil ? settings.t(.dropHintChoose) : settings.t(.dropReady))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                .scaleEffect(targeted ? 1.015 : 1.0)
                .shadow(color: targeted ? Color.accentColor.opacity(0.22) : .clear, radius: 18, y: 6)
                .animation(.spring(response: 0.32, dampingFraction: 0.7), value: targeted)
                .contentShape(Rectangle())
                .onTapGesture { model.pickPDF() }
                .dropDestination(for: URL.self) { urls, _ in
                    guard let url = urls.first else { return false }
                    model.accept(url)
                    return true
                } isTargeted: { targeted = $0 }

            Button(action: model.convert) {
                Label(settings.t(.convertButton), systemImage: "wand.and.stars")
                    .frame(maxWidth: 260)
            }
            .controlSize(.large)
            .buttonStyle(.borderedProminent)
            .disabled(model.droppedPDF == nil)

            RecentsList()
        }
        .padding(28)
    }
}

/// Recently converted files — quick re-open in Word or reveal in Finder.
private struct RecentsList: View {
    @EnvironmentObject var settings: AppSettings
    var body: some View {
        let items = Array(settings.recents.filter { $0.exists }.prefix(5))
        if !items.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(settings.t(.recentsTitle))
                        .font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    Spacer()
                    Button(settings.t(.recentsClear)) { settings.clearRecents() }
                        .buttonStyle(.plain).font(.caption2).foregroundStyle(.tertiary)
                }
                ForEach(items) { RecentRow(item: $0) }
            }
            .frame(maxWidth: 460)
            .padding(.top, 8)
        }
    }
}

private struct RecentRow: View {
    @EnvironmentObject var model: ConversionViewModel
    let item: AppSettings.RecentItem
    @State private var hover = false
    var body: some View {
        HStack(spacing: 9) {
            Image(systemName: "doc.richtext.fill").foregroundStyle(.tint)
            VStack(alignment: .leading, spacing: 1) {
                Text(item.name).font(.caption).lineLimit(1).truncationMode(.middle)
                Text(item.date, style: .date).font(.caption2).foregroundStyle(.tertiary)
            }
            Spacer(minLength: 8)
            Button { model.reveal(item.output) } label: {
                Image(systemName: "folder")
            }.buttonStyle(.plain).foregroundStyle(.secondary)
            Button { model.openInWord(item.output) } label: {
                Image(systemName: "arrow.up.forward.app")
            }.buttonStyle(.plain).foregroundStyle(Color.accentColor)
        }
        .padding(.horizontal, 10).padding(.vertical, 7)
        .background(RoundedRectangle(cornerRadius: 8)
            .fill(Color.primary.opacity(hover ? 0.07 : 0.03)))
        .contentShape(Rectangle())
        .onHover { hover = $0 }
        .onTapGesture { model.openInWord(item.output) }
    }
}

private struct WorkingView: View {
    @EnvironmentObject var settings: AppSettings
    var body: some View {
        VStack(spacing: 14) {
            ProgressView().controlSize(.large)
            Text(settings.t(.working)).foregroundStyle(.secondary)
        }
    }
}

private struct FailureView: View {
    @EnvironmentObject var model: ConversionViewModel
    @EnvironmentObject var settings: AppSettings
    let message: String
    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.largeTitle).foregroundStyle(.orange)
            Text(message).multilineTextAlignment(.center).padding(.horizontal)
            Button(settings.t(.back)) { model.reset() }
        }.padding()
    }
}

// MARK: - In-window sheets (About / How it works)

struct AboutView: View {
    @EnvironmentObject var settings: AppSettings
    @Environment(\.dismiss) var dismiss
    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 14) {
                    AppLogo(size: 76)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                    Text(settings.t(.appTitle)).font(.title2.bold())
                    Text(settings.t(.aboutTagline))
                        .font(.callout).foregroundStyle(.secondary)
                    Text(settings.t(.aboutBody))
                        .font(.caption).multilineTextAlignment(.center).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)

                    #if !APP_STORE
                    // Donation — voluntary, optional. EXCLUDED from the App Store
                    // build (Apple rejects external/crypto donations).
                    Divider().padding(.vertical, 2)
                    VStack(spacing: 10) {
                        Label(settings.t(.donateHeading), systemImage: "heart.fill")
                            .font(.headline).foregroundStyle(.pink)
                        Text(settings.t(.donateBody))
                            .font(.caption).multilineTextAlignment(.center).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                        DonationWebView()
                            .frame(height: 230)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                            .overlay(RoundedRectangle(cornerRadius: 10)
                                .stroke(Color.primary.opacity(0.08), lineWidth: 1))

                        CryptoDonationView().padding(.top, 4)
                    }
                    #endif
                }
                .padding(.horizontal, 28).padding(.top, 28).padding(.bottom, 16)
            }
            Divider()
            Button(settings.t(.close)) { dismiss() }
                .keyboardShortcut(.defaultAction)
                .padding(.vertical, 12)
        }
        #if APP_STORE
        .frame(width: 420, height: 360)
        #else
        .frame(width: 420, height: 640)
        #endif
    }
}

struct HowItWorksView: View {
    @EnvironmentObject var settings: AppSettings
    @Environment(\.dismiss) var dismiss
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: "sparkles").foregroundStyle(.tint)
                Text(settings.t(.howItWorksTitle)).font(.title2.bold())
            }
            Text(settings.t(.howItWorksBody))
                .font(.callout).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                Button(settings.t(.close)) { dismiss() }.keyboardShortcut(.defaultAction)
            }
        }
        .padding(28).frame(width: 460)
    }
}
