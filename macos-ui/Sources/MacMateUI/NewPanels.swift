import SwiftUI
import Charts

// MARK: - Scene Profile Panel

struct ScenePanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @AppStorage("appLanguage") private var lang = "zh"
    @State private var statusMessage = ""
    @State private var isActivating = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(L10n.s(.sceneProfiles))
                .font(.custom("Avenir Next Demi Bold", size: 28))

            Text(L10n.s(.sceneSubtitle))
                .foregroundStyle(.secondary)

            HStack(spacing: 20) {
                sceneCard(
                    title: L10n.s(.focusMode),
                    subtitle: L10n.s(.focusSub),
                    icon: "brain.head.profile",
                    gradient: [.blue, .indigo],
                    action: { await activateScene("focus") }
                )
                sceneCard(
                    title: L10n.s(.relaxMode),
                    subtitle: L10n.s(.relaxSub),
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
        statusMessage = L10n.s(.switching)
        do {
            let envelope = try await bridge.rawRequest(action: "scene_activate", payload: ["profile": .string(profile)])
            statusMessage = envelope.result?.objectValue?["result"]?.stringValue ?? "Done"
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
        }
        isActivating = false
    }
}

// MARK: - Music Panel

struct MusicPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @AppStorage("appLanguage") private var lang = "zh"
    @State private var selectedApp = "apple_music"
    @State private var genre = ""
    @State private var statusMessage = ""
    @State private var nowPlaying = ""

    private var apps: [(String, String)] {
        [("apple_music", "Apple Music"), ("netease", L10n.current == .zh ? "网易云音乐" : "NetEase Music")]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Music")
                .font(.custom("Avenir Next Demi Bold", size: 28))

            Picker(L10n.s(.playerLabel), selection: $selectedApp) {
                ForEach(apps, id: \.0) { app in
                    Text(app.1).tag(app.0)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 300)

            HStack(spacing: 12) {
                TextField(L10n.s(.playlistHint), text: $genre)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 250)

                Button("▶ \(L10n.s(.play))") {
                    Task { await musicAction("play", extra: ["genre": .string(genre)]) }
                }
                .buttonStyle(.borderedProminent)

                Button("⏸ \(L10n.s(.pause))") {
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
                Text(L10n.s(.volume))
                ForEach([25, 50, 75, 100], id: \.self) { level in
                    Button("\(level)%") {
                        Task { await musicAction("volume", extra: ["level": .string(String(level))]) }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }

                Spacer()

                Button(L10n.s(.nowPlaying)) {
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

// MARK: - Weather Panel (Enhanced)

struct WeatherPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @AppStorage("appLanguage") private var lang = "zh"
    @State private var city = ""
    @State private var currentWeather: [String: String] = [:]
    @State private var hourlyData: [[String: String]] = []
    @State private var forecastData: [[String: String]] = []
    @State private var isLoading = false
    @State private var errorMessage = ""

    var body: some View {
        ScrollView(showsIndicators: true) {
            VStack(alignment: .leading, spacing: 16) {
                Text(L10n.s(.weather))
                    .font(.custom("Avenir Next Demi Bold", size: 28))

                // City input
                HStack(spacing: 12) {
                    TextField(L10n.s(.cityHint), text: $city)
                        .textFieldStyle(.roundedBorder)
                        .frame(maxWidth: 250)
                        .onSubmit { Task { await fetchWeather() } }

                    Button(L10n.s(.queryWeather)) {
                        Task { await fetchWeather() }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isLoading)

                    if isLoading {
                        ProgressView().controlSize(.small)
                    }
                }

                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .font(.caption)
                }

                // Current weather card
                if !currentWeather.isEmpty {
                    currentWeatherCard
                }

                // Hourly chart
                if !hourlyData.isEmpty {
                    Text(L10n.current == .zh ? "今日逐时天气" : "Today's Hourly Weather")
                        .font(.custom("Avenir Next Demi Bold", size: 18))

                    hourlyChart
                        .frame(height: 200)

                    // Hourly detail table
                    hourlyTable
                }

                // 3-day forecast
                if !forecastData.isEmpty {
                    Text(L10n.current == .zh ? "未来天气" : "Forecast")
                        .font(.custom("Avenir Next Demi Bold", size: 18))

                    HStack(spacing: 12) {
                        ForEach(forecastData, id: \.["date"]) { day in
                            forecastCard(day)
                        }
                    }
                }
            }
            .padding(.trailing, 8)
        }
        .scrollIndicators(.visible)
        .onAppear {
            if currentWeather.isEmpty {
                Task { await fetchWeather() }
            }
        }
    }

    // MARK: - Current Weather Card
    private var currentWeatherCard: some View {
        VStack(spacing: 16) {
            HStack(alignment: .top, spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(currentWeather["city"] ?? "")
                        .font(.custom("Avenir Next Demi Bold", size: 22))
                    Text(currentWeather["description"] ?? "")
                        .font(.custom("Avenir Next", size: 16))
                        .foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(currentWeather["temp_c"] ?? "?")°C")
                        .font(.system(size: 42, weight: .light))
                    Text("\(L10n.s(.feelsLike)) \(currentWeather["feels_like_c"] ?? "?")°C")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            HStack(spacing: 24) {
                weatherStat(icon: "humidity", label: L10n.s(.humidity), value: "\(currentWeather["humidity"] ?? "?")%")
                weatherStat(icon: "wind", label: L10n.s(.windSpeed), value: "\(currentWeather["wind_speed_kmh"] ?? "?") km/h")
                weatherStat(icon: "safari", label: L10n.s(.windDir), value: currentWeather["wind_dir"] ?? "?")
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

    // MARK: - Hourly Chart
    private var hourlyChart: some View {
        Chart(hourlyData.indices, id: \.self) { idx in
            let item = hourlyData[idx]
            let hour = item["hour"] ?? ""
            let temp = Double(item["temp_c"] ?? "0") ?? 0

            LineMark(
                x: .value("Hour", hour),
                y: .value("°C", temp)
            )
            .foregroundStyle(Color.orange)
            .interpolationMethod(.catmullRom)

            PointMark(
                x: .value("Hour", hour),
                y: .value("°C", temp)
            )
            .foregroundStyle(Color.orange)
            .annotation(position: .top) {
                Text("\(Int(temp))°")
                    .font(.system(size: 9))
                    .foregroundColor(.secondary)
            }

            let rain = Double(item["chance_of_rain"] ?? "0") ?? 0
            if rain > 0 {
                BarMark(
                    x: .value("Hour", hour),
                    y: .value("Rain %", rain * 0.3)  // scale down
                )
                .foregroundStyle(Color.blue.opacity(0.25))
            }
        }
        .chartYAxisLabel("°C")
        .padding(8)
        .background(Color.secondary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    // MARK: - Hourly Table
    private var hourlyTable: some View {
        ScrollView(.horizontal, showsIndicators: true) {
            HStack(spacing: 0) {
                ForEach(hourlyData.indices, id: \.self) { idx in
                    let item = hourlyData[idx]
                    VStack(spacing: 6) {
                        Text(item["hour"] ?? "")
                            .font(.custom("Menlo", size: 11))
                        Text("\(item["temp_c"] ?? "?")°")
                            .font(.custom("Avenir Next Demi Bold", size: 14))
                        Text(item["description"] ?? "")
                            .font(.system(size: 9))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                        HStack(spacing: 2) {
                            Image(systemName: "drop")
                                .font(.system(size: 8))
                                .foregroundColor(.blue)
                            Text("\(item["chance_of_rain"] ?? "0")%")
                                .font(.system(size: 9))
                                .foregroundColor(.blue)
                        }
                    }
                    .frame(width: 56)
                    .padding(.vertical, 8)
                    if idx < hourlyData.count - 1 {
                        Divider()
                    }
                }
            }
        }
        .padding(8)
        .background(Color.secondary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    // MARK: - Forecast Card
    private func forecastCard(_ day: [String: String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(day["date"] ?? "")
                .font(.custom("Menlo", size: 12).bold())

            HStack(spacing: 4) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 10))
                    .foregroundColor(.red)
                Text("\(day["max_c"] ?? "?")°")
                    .font(.custom("Avenir Next Demi Bold", size: 16))

                Image(systemName: "arrow.down")
                    .font(.system(size: 10))
                    .foregroundColor(.blue)
                Text("\(day["min_c"] ?? "?")°")
                    .font(.custom("Avenir Next", size: 16))
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 8) {
                Label(day["sunrise"] ?? "", systemImage: "sunrise")
                    .font(.caption2)
                Label(day["sunset"] ?? "", systemImage: "sunset")
                    .font(.caption2)
            }
            .foregroundStyle(.secondary)

            Text("UV \(day["uv_index"] ?? "?")")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color.secondary.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    // MARK: - Helpers
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
        currentWeather = [:]
        hourlyData = []
        forecastData = []

        do {
            let envelope = try await bridge.rawRequest(action: "weather", payload: ["city": .string(city)])
            if let weatherObj = envelope.result?.objectValue?["weather"]?.objectValue {
                // Check for error
                if let err = weatherObj["error"]?.stringValue {
                    errorMessage = err
                    isLoading = false
                    return
                }

                // Current conditions
                var current: [String: String] = [:]
                for key in ["city", "temp_c", "feels_like_c", "humidity", "description", "wind_speed_kmh", "wind_dir", "observation_time"] {
                    current[key] = weatherObj[key]?.stringValue ?? ""
                }
                currentWeather = current

                // Hourly
                if let hourlyArr = weatherObj["hourly"]?.arrayValue {
                    hourlyData = hourlyArr.compactMap { item -> [String: String]? in
                        guard let obj = item.objectValue else { return nil }
                        var row: [String: String] = [:]
                        for key in ["hour", "temp_c", "feels_like_c", "description", "humidity", "chance_of_rain", "wind_kmh"] {
                            row[key] = obj[key]?.stringValue ?? ""
                        }
                        return row
                    }
                }

                // Forecast
                if let forecastArr = weatherObj["forecast"]?.arrayValue {
                    forecastData = forecastArr.compactMap { item -> [String: String]? in
                        guard let obj = item.objectValue else { return nil }
                        var row: [String: String] = [:]
                        for key in ["date", "max_c", "min_c", "avg_c", "sunrise", "sunset", "uv_index"] {
                            row[key] = obj[key]?.stringValue ?? ""
                        }
                        return row
                    }
                }
            } else {
                errorMessage = L10n.current == .zh ? "后端无返回数据" : "No data returned"
            }
        } catch {
            errorMessage = "\(L10n.current == .zh ? "请求失败" : "Request failed"): \(error.localizedDescription)"
        }
        isLoading = false
    }
}
