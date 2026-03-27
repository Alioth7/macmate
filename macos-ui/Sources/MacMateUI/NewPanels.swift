import SwiftUI

// MARK: - Scene Profile Panel

struct ScenePanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @State private var statusMessage = ""
    @State private var isActivating = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Scene Profiles")
                .font(.custom("Avenir Next Demi Bold", size: 28))

            Text("一键切换工作/休闲模式，自动管理应用和勿扰状态")
                .foregroundStyle(.secondary)

            HStack(spacing: 20) {
                sceneCard(
                    title: "专注模式",
                    subtitle: "开启勿扰 · 关闭社交 · 启动 Terminal",
                    icon: "brain.head.profile",
                    gradient: [.blue, .indigo],
                    action: { await activateScene("focus") }
                )
                sceneCard(
                    title: "休闲模式",
                    subtitle: "关闭办公App · 关闭勿扰",
                    icon: "cup.and.saucer",
                    gradient: [.orange, .pink],
                    action: { await activateScene("relax") }
                )
            }

            if !statusMessage.isEmpty {
                Text(statusMessage)
                    .font(.custom("Menlo", size: 12))
                    .textSelection(.enabled)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.secondary.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }

            Spacer()
        }
    }

    private func sceneCard(
        title: String,
        subtitle: String,
        icon: String,
        gradient: [Color],
        action: @escaping () async -> Void
    ) -> some View {
        Button {
            Task { await action() }
        } label: {
            VStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 36))
                    .foregroundColor(.white)
                Text(title)
                    .font(.custom("Avenir Next Demi Bold", size: 18))
                    .foregroundColor(.white)
                Text(subtitle)
                    .font(.custom("Avenir Next", size: 12))
                    .foregroundColor(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity)
            .padding(24)
            .background(
                LinearGradient(colors: gradient, startPoint: .topLeading, endPoint: .bottomTrailing)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .shadow(color: gradient.first?.opacity(0.3) ?? .clear, radius: 8, y: 4)
        }
        .buttonStyle(.plain)
        .disabled(isActivating)
    }

    private func activateScene(_ profile: String) async {
        isActivating = true
        statusMessage = "切换中..."
        do {
            let envelope = try await bridge.rawRequest(action: "scene_activate", payload: ["profile": .string(profile)])
            statusMessage = envelope.result?.objectValue?["result"]?.stringValue ?? "完成"
        } catch {
            statusMessage = "失败: \(error.localizedDescription)"
        }
        isActivating = false
    }
}

// MARK: - Music Panel

struct MusicPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @State private var selectedApp = "apple_music"
    @State private var genre = ""
    @State private var statusMessage = ""
    @State private var nowPlaying = ""

    private let apps = [("apple_music", "Apple Music"), ("netease", "网易云音乐")]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Music")
                .font(.custom("Avenir Next Demi Bold", size: 28))

            Picker("Player", selection: $selectedApp) {
                ForEach(apps, id: \.0) { app in
                    Text(app.1).tag(app.0)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 300)

            HStack(spacing: 12) {
                TextField("歌单关键词 (仅 Apple Music)", text: $genre)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 250)

                Button("▶ Play") {
                    Task { await musicAction("play", extra: ["genre": .string(genre)]) }
                }
                .buttonStyle(.borderedProminent)

                Button("⏸ Pause") {
                    Task { await musicAction("pause") }
                }
                .buttonStyle(.bordered)

                Button("⏭") {
                    Task { await musicAction("next") }
                }
                .buttonStyle(.bordered)

                Button("⏮") {
                    Task { await musicAction("previous") }
                }
                .buttonStyle(.bordered)
            }

            HStack(spacing: 12) {
                Text("Volume:")
                ForEach([25, 50, 75, 100], id: \.self) { level in
                    Button("\(level)%") {
                        Task { await musicAction("volume", extra: ["level": .string(String(level))]) }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }

                Spacer()

                Button("🎵 Now Playing") {
                    Task { await musicAction("now_playing") }
                }
                .buttonStyle(.bordered)
            }

            if !nowPlaying.isEmpty {
                HStack {
                    Image(systemName: "music.note")
                        .foregroundColor(.accentColor)
                    Text(nowPlaying)
                        .font(.custom("Avenir Next", size: 14))
                }
                .padding(12)
                .background(Color.accentColor.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }

            if !statusMessage.isEmpty {
                Text(statusMessage)
                    .font(.custom("Menlo", size: 12))
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
    }

    private func musicAction(_ action: String, extra: [String: JSONValue] = [:]) async {
        var payload: [String: JSONValue] = [
            "action": .string(action),
            "app": .string(selectedApp),
        ]
        for (k, v) in extra { payload[k] = v }

        do {
            let envelope = try await bridge.rawRequest(action: "music_control", payload: payload)
            let result = envelope.result?.objectValue?["result"]?.stringValue ?? ""
            if action == "now_playing" {
                nowPlaying = result
            } else {
                statusMessage = result
            }
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
        }
    }
}

// MARK: - Weather Panel

struct WeatherPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @State private var city = ""
    @State private var weatherData: [String: String] = [:]
    @State private var isLoading = false
    @State private var errorMessage = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Weather")
                .font(.custom("Avenir Next Demi Bold", size: 28))

            HStack(spacing: 12) {
                TextField("城市 (留空自动定位)", text: $city)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 250)

                Button("查询天气") {
                    Task { await fetchWeather() }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isLoading)

                if isLoading {
                    ProgressView().controlSize(.small)
                }
            }

            if !weatherData.isEmpty {
                weatherCard
            }

            if !errorMessage.isEmpty {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.caption)
            }

            Spacer()
        }
    }

    private var weatherCard: some View {
        VStack(spacing: 16) {
            HStack(alignment: .top, spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(weatherData["city"] ?? "")
                        .font(.custom("Avenir Next Demi Bold", size: 22))

                    Text(weatherData["description"] ?? "")
                        .font(.custom("Avenir Next", size: 16))
                        .foregroundStyle(.secondary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(weatherData["temp_c"] ?? "?")°C")
                        .font(.system(size: 42, weight: .light))

                    Text("体感 \(weatherData["feels_like_c"] ?? "?")°C")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            HStack(spacing: 24) {
                weatherStat(icon: "humidity", label: "湿度", value: "\(weatherData["humidity"] ?? "?")%")
                weatherStat(icon: "wind", label: "风速", value: "\(weatherData["wind_speed_kmh"] ?? "?") km/h")
                weatherStat(icon: "safari", label: "风向", value: weatherData["wind_dir"] ?? "?")
            }
        }
        .padding(20)
        .background(
            LinearGradient(
                colors: [Color.cyan.opacity(0.15), Color.blue.opacity(0.08)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func weatherStat(icon: String, label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .foregroundColor(.accentColor)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.custom("Menlo", size: 13))
        }
    }

    private func fetchWeather() async {
        isLoading = true
        errorMessage = ""
        weatherData = [:]

        do {
            let envelope = try await bridge.rawRequest(action: "weather", payload: ["city": .string(city)])
            if let resultStr = envelope.result?.objectValue?["result"]?.stringValue,
               let data = resultStr.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                if let err = json["error"] as? String {
                    errorMessage = err
                } else {
                    for (k, v) in json {
                        weatherData[k] = "\(v)"
                    }
                }
            }
        } catch {
            errorMessage = "请求失败: \(error.localizedDescription)"
        }
        isLoading = false
    }
}
