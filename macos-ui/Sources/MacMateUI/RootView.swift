import SwiftUI
import AppKit

private enum AppSection: String, CaseIterable, Identifiable {
    case chat = "Chat"
    case calendar = "Calendar"
    case productivity = "Productivity"
    case quadrant = "Quadrant"
    case scene = "Scene"
    case music = "Music"
    case weather = "Weather"
    case plans = "Plans"
    case daily = "Daily"
    case llm = "LLM Settings"

    var id: String { rawValue }
}

struct RootView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @Environment(\.colorScheme) private var colorScheme
    @State private var selection: AppSection? = .chat
    @AppStorage("showDebugStatus") private var showDebugStatus = true

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
                            Text(item.rawValue)
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
            Toggle("Show Debug Status", isOn: $showDebugStatus)
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
