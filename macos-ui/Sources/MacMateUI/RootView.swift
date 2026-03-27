import SwiftUI
import AppKit

private enum AppSection: String, CaseIterable, Identifiable {
    case chat, calendar, productivity, quadrant, scene, music, weather, plans, daily, llm

    var id: String { rawValue }

    var label: String {
        switch self {
        case .chat:         return L10n.s(.chat)
        case .calendar:     return L10n.s(.calendar)
        case .productivity: return L10n.s(.productivity)
        case .quadrant:     return L10n.s(.quadrant)
        case .scene:        return L10n.s(.scene)
        case .music:        return L10n.s(.music)
        case .weather:      return L10n.s(.weather)
        case .plans:        return L10n.s(.plans)
        case .daily:        return L10n.s(.daily)
        case .llm:          return L10n.s(.llmSettings)
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @Environment(\.colorScheme) private var colorScheme
    @State private var selection: AppSection? = .chat
    @AppStorage("showDebugStatus") private var showDebugStatus = true
    @AppStorage("appLanguage") private var appLanguage = "zh"

    var body: some View {
        NavigationSplitView {
            List {
                ForEach(AppSection.allCases) { item in
                    Button {
                        selection = item
                    } label: {
                        HStack(spacing: 10) {
                            Image(systemName: icon(for: item))
                                .frame(width: 20, alignment: .center)
                            Text(item.label)
                                .font(.custom("Avenir Next", size: 14))
                        }
                        .padding(.vertical, 6)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .listRowBackground(selection == item ? Color.accentColor.opacity(0.22) : Color.clear)
                }
            }
            .navigationTitle("MacMate")
            .safeAreaInset(edge: .bottom) {
                Picker("", selection: $appLanguage) {
                    ForEach(Lang.allCases, id: \.rawValue) { lang in
                        Text(lang.displayName).tag(lang.rawValue)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 12)
                .padding(.bottom, 8)
            }
        } detail: {
            ZStack {
                LinearGradient(
                    colors: backgroundGradient,
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()

                Group {
                    switch selection {
                    case .chat: ChatPanelView()
                    case .calendar: CalendarPanelView()
                    case .productivity: ProductivityPanelView()
                    case .quadrant: QuadrantPanelView()
                    case .scene: ScenePanelView()
                    case .music: MusicPanelView()
                    case .weather: WeatherPanelView()
                    case .plans: PlansPanelView()
                    case .daily: DailyPanelView()
                    case .llm: LLMSettingsPanelView()
                    case .none: ChatPanelView()
                    }
                }
                .padding(24)
            }
        }
        .overlay(alignment: .bottomTrailing) {
            if showDebugStatus {
                Text(bridge.statusText)
                    .font(.custom("Menlo", size: 11))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                    .padding(16)
                    .onTapGesture { showDebugStatus = false }
            }
        }
        .contextMenu {
            Toggle(L10n.s(.showDebugStatus), isOn: $showDebugStatus)
        }
        .onAppear {
            DispatchQueue.main.async {
                NSApp.activate(ignoringOtherApps: true)
                NSApp.keyWindow?.makeKeyAndOrderFront(nil)
            }
        }
    }

    private var backgroundGradient: [Color] {
        if colorScheme == .dark {
            return [
                Color(red: 0.10, green: 0.12, blue: 0.16),
                Color(red: 0.14, green: 0.12, blue: 0.10)
            ]
        }

        return [
            Color(red: 0.95, green: 0.98, blue: 1.0),
            Color(red: 1.0, green: 0.97, blue: 0.92)
        ]
    }

    private func icon(for section: AppSection) -> String {
        switch section {
        case .chat: return "message"
        case .calendar: return "calendar"
        case .productivity: return "gauge.with.dots.needle.67percent"
        case .quadrant: return "chart.xyaxis.line"
        case .scene: return "theatermask.and.paintbrush"
        case .music: return "music.note"
        case .weather: return "cloud.sun"
        case .plans: return "target"
        case .daily: return "note.text"
        case .llm: return "slider.horizontal.3"
        }
    }
}
