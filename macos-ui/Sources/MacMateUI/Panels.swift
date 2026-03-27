import SwiftUI
import Charts

struct ChatPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @Environment(\.colorScheme) private var colorScheme
    @AppStorage("appLanguage") private var lang = "zh"
    @State private var inputText = ""
    @State private var isStepsExpanded = true
    @State private var isThinking = false
    @State private var toastMessage = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(L10n.s(.agentChat))
                    .font(.custom("Avenir Next Demi Bold", size: 28))

                if !toastMessage.isEmpty {
                    Text(toastMessage)
                        .font(.caption)
                        .foregroundColor(.green)
                        .transition(.opacity)
                }

                Spacer()
                Button(action: {
                    bridge.loadChatHistory()
                    showToast(L10n.s(.loaded))
                }) {
                    Image(systemName: "arrow.down.doc")
                }
                .buttonStyle(.plain)
                .help(L10n.s(.loadHistory))

                Button(action: {
                    bridge.saveChatHistory()
                    showToast(L10n.s(.saved))
                }) {
                    Image(systemName: "square.and.arrow.down")
                }
                .buttonStyle(.plain)
                .help(L10n.s(.saveHistory))

                Button(action: {
                    Task { await bridge.clearChat() }
                }) {
                    Image(systemName: "trash")
                        .foregroundColor(.red)
                }
                .buttonStyle(.plain)
                .help(L10n.s(.clearChat))
                .disabled(isThinking)
            }

            ScrollView(showsIndicators: true) {
                LazyVStack(alignment: .leading, spacing: 10) {
                    ForEach(bridge.chatMessages) { msg in
                        HStack {
                            if msg.role == "assistant" {
                                bubble(text: msg.content, tint: assistantBubbleColor)
                                Spacer(minLength: 20)
                            } else {
                                Spacer(minLength: 20)
                                bubble(text: msg.content, tint: userBubbleColor)
                            }
                        }
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                    }

                    // Quick-reply buttons for the last assistant message
                    if !isThinking, let lastMsg = bridge.chatMessages.last, lastMsg.role == "assistant" {
                        let options = Self.extractOptions(from: lastMsg.content)
                        if !options.isEmpty {
                            quickReplyButtons(options: options)
                        }
                    }

                    if isThinking {
                        HStack {
                            ProgressView().controlSize(.small)
                            Text(L10n.s(.agentThinking)).font(.caption).foregroundColor(.secondary)
                            Spacer()
                        }
                    }
                }
                .padding(.trailing, 8)
            }
            .background(Color.gray.opacity(0.05)) // 浅灰色背景方便辨认滚动区域
            .scrollIndicators(.visible)
            .animation(.easeOut(duration: 0.24), value: bridge.chatMessages.count)

            if !bridge.latestTrace.isEmpty {
                DisclosureGroup(L10n.s(.agentSteps), isExpanded: $isStepsExpanded) {
                    ScrollView(showsIndicators: true) {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(Array(bridge.latestTrace.enumerated()), id: \.offset) { index, line in
                                Text(line)
                                    .font(.custom("Menlo", size: 11))
                                    .textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                        .padding(.trailing, 8)
                    }
                    .background(Color.gray.opacity(0.08)) // 稍微深一点的浅灰色
                    .scrollIndicators(.visible)
                    .frame(maxHeight: 150)
                }
            }

            HStack(alignment: .bottom, spacing: 12) {
                ChatInputField(text: $inputText, isDisabled: isThinking) {
                    sendMessage()
                }

                Button(L10n.s(.send)) {
                    sendMessage()
                }
                .buttonStyle(.borderedProminent)
                .disabled(isThinking || inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
    }

    private func sendMessage() {
        let prompt = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !prompt.isEmpty else { return }
        inputText = ""
        bridge.latestTrace.removeAll()
        isThinking = true
        Task {
            await bridge.sendChat(prompt: prompt)
            isThinking = false
        }
    }

    private func showToast(_ message: String) {
        withAnimation { toastMessage = message }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            withAnimation { toastMessage = "" }
        }
    }


    private func bubble(text: String, tint: Color) -> some View {
        Group {
            if let attributed = try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)) {
                Text(attributed)
            } else {
                Text(text)
            }
        }
        .font(.custom("Avenir Next", size: 14))
        .textSelection(.enabled)
        .padding(12)
        .background(tint)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var assistantBubbleColor: Color {
        colorScheme == .dark
            ? Color(red: 0.16, green: 0.26, blue: 0.30)
            : Color(red: 0.86, green: 0.95, blue: 0.95)
    }

    private var userBubbleColor: Color {
        colorScheme == .dark
            ? Color(red: 0.34, green: 0.24, blue: 0.16)
            : Color(red: 1.0, green: 0.90, blue: 0.78)
    }

    // MARK: - Quick Reply Options

    /// Extract numbered/bulleted options from assistant text
    static func extractOptions(from text: String) -> [String] {
        let lines = text.components(separatedBy: .newlines)
        var options: [String] = []
        // Match patterns: "1. xxx", "1) xxx", "1、xxx", "- xxx", "• xxx"
        let pattern = #"^\s*(?:\d+[\.\)、]|[-•])\s*(.+)$"#
        let regex = try? NSRegularExpression(pattern: pattern)

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty else { continue }
            let range = NSRange(trimmed.startIndex..., in: trimmed)
            if let match = regex?.firstMatch(in: trimmed, range: range),
               let captureRange = Range(match.range(at: 1), in: trimmed) {
                let optionText = String(trimmed[captureRange]).trimmingCharacters(in: .whitespaces)
                // Skip overly long lines (likely explanatory, not an option)
                if optionText.count <= 60 && !optionText.isEmpty {
                    options.append(optionText)
                }
            }
        }
        // Only show buttons if there are 2~6 options (avoids false positives)
        return (options.count >= 2 && options.count <= 6) ? options : []
    }

    private func quickReplyButtons(options: [String]) -> some View {
        FlowLayout(spacing: 8) {
            ForEach(options, id: \.self) { option in
                Button {
                    inputText = option
                    sendMessage()
                } label: {
                    Text(option)
                        .font(.custom("Avenir Next", size: 13))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 7)
                        .background(Color.accentColor.opacity(0.12))
                        .foregroundColor(.accentColor)
                        .clipShape(Capsule())
                        .overlay(Capsule().stroke(Color.accentColor.opacity(0.3), lineWidth: 1))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.leading, 4)
        .transition(.opacity.combined(with: .move(edge: .bottom)))
    }
}

/// Simple flow layout for wrapping buttons
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrange(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrange(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y), proposal: .unspecified)
        }
    }

    private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, positions: [CGPoint]) {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        var maxX: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth && x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            positions.append(CGPoint(x: x, y: y))
            rowHeight = max(rowHeight, size.height)
            x += size.width + spacing
            maxX = max(maxX, x)
        }

        return (CGSize(width: maxX, height: y + rowHeight), positions)
    }
}

struct CalendarPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @AppStorage("appLanguage") private var lang = "zh"
    @State private var viewMode: Int = 1 // 0: Today, 1: Upcoming 7 Days

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(L10n.s(.calendar))
                    .font(.custom("Avenir Next Demi Bold", size: 28))
                
                Picker("", selection: $viewMode) {
                    Text(L10n.s(.dayView)).tag(0)
                    Text(L10n.s(.weekView)).tag(1)
                }
                .pickerStyle(.segmented)
                .frame(width: 320)
                .padding(.leading, 12)

                Spacer()
                Button(L10n.s(.refresh)) {
                    Task { await bridge.loadCalendar() }
                }
                .buttonStyle(.bordered)
            }

            if bridge.calendarPermissionDenied {
                HStack(spacing: 12) {
                    Text(L10n.s(.calendarDenied))
                        .foregroundStyle(.secondary)
                    Button(L10n.s(.openSettings)) {
                        NativeCalendarService.openCalendarPrivacySettings()
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            
            if viewMode == 1 {
                weekView
            } else {
                Table(filteredEvents) {
                    TableColumn("Task") { item in
                        Text(item.task)
                    }
                    TableColumn("Start") { item in
                        Text(item.start)
                            .font(.custom("Menlo", size: 12))
                    }
                    TableColumn("Finish") { item in
                        Text(item.finish)
                            .font(.custom("Menlo", size: 12))
                    }
                    TableColumn("Duration") { item in
                        Text(item.duration)
                    }
                }
            }
        }
        .onAppear {
            if bridge.calendarEvents.isEmpty {
                Task { await bridge.loadCalendar() }
            }
        }
    }
    
    private var weekView: some View {
        let (parsed, categories) = processEventsForWeek()
        let yValues = Array(stride(from: -24.0, through: -6.0, by: 2.0))
        
        return Chart(parsed) { event in
            BarMark(
                x: .value("Day", event.dayString),
                yStart: .value("Start", -event.startHour),
                yEnd: .value("End", -event.endHour)
            )
            .foregroundStyle(Color.accentColor.opacity(0.8))
            .cornerRadius(4)
            .annotation(position: .overlay, alignment: .top) {
                Text(event.raw.task)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 4)
                    .padding(.top, 4)
                    .minimumScaleFactor(0.8)
            }
        }
        .chartXScale(domain: categories)
        .chartYScale(domain: [-24.0, -6.0])
        .chartYAxis {
            AxisMarks(values: yValues) { value in
                AxisGridLine()
                AxisTick()
                if let val = value.as(Double.self) {
                    let hour = Int(-val)
                    AxisValueLabel {
                        Text("\(hour):00").font(.caption).padding(.trailing, 4)
                    }
                }
            }
        }
        .padding(.vertical, 10)
    }
    
    struct ParsedEvent: Identifiable {
        let id = UUID()
        let raw: CalendarEvent
        let dayString: String
        let dayDate: Date
        let startHour: Double
        let endHour: Double
    }
    
    private func processEventsForWeek() -> ([ParsedEvent], [String]) {
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd HH:mm"
        
        let dayF = DateFormatter()
        dayF.dateFormat = "MM-dd EEE"
        
        var list: [ParsedEvent] = []
        let calendar = Calendar.current
        let now = Date()
        let startOfToday = calendar.startOfDay(for: now)
        guard let sevenDaysLater = calendar.date(byAdding: .day, value: 7, to: startOfToday) else { return ([], []) }
        
        var categories: [String] = []
        for i in 0..<7 {
            if let d = calendar.date(byAdding: .day, value: i, to: startOfToday) {
                categories.append(dayF.string(from: d))
            }
        }
        
        for ev in bridge.calendarEvents {
            guard let dStart = df.date(from: ev.start),
                  let dEnd = df.date(from: ev.finish) else { continue }
            
            // Limit to next 7 days
            if dStart >= startOfToday && dStart < sevenDaysLater {
                let hStart = calendar.component(.hour, from: dStart)
                let mStart = calendar.component(.minute, from: dStart)
                let hEnd = calendar.component(.hour, from: dEnd)
                let mEnd = calendar.component(.minute, from: dEnd)
                
                let tStart = Double(hStart) + Double(mStart)/60.0
                let tEnd = Double(hEnd) + Double(mEnd)/60.0
                
                let dayStr = dayF.string(from: dStart)
                if !categories.contains(dayStr) { continue }
                
                // Clamp display
                let clampStart = max(6.0, min(24.0, tStart))
                let clampEnd = max(6.0, min(24.0, tEnd))
                
                if clampEnd > clampStart {
                    list.append(ParsedEvent(raw: ev, dayString: dayStr, dayDate: dStart, startHour: clampStart, endHour: clampEnd))
                }
            }
        }
        return (list.sorted { $0.dayDate < $1.dayDate }, categories)
    }

    private var filteredEvents: [CalendarEvent] {
        if viewMode == 1 { return bridge.calendarEvents }
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let todayStr = formatter.string(from: Date())
        
        return bridge.calendarEvents.filter { $0.start.contains(todayStr) }
    }
}

struct PlansPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @AppStorage("appLanguage") private var lang = "zh"
    @State private var planText = ""
    @State private var planPrompt = ""
    @State private var targetDate = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(L10n.s(.longTermPlans))
                .font(.custom("Avenir Next Demi Bold", size: 28))

            VStack(spacing: 8) {
                HStack {
                    TextField(L10n.s(.planContentHint), text: $planText)
                        .textFieldStyle(.roundedBorder)
                    TextField(L10n.s(.planDateHint), text: $targetDate)
                        .textFieldStyle(.roundedBorder)
                        .font(.custom("Menlo", size: 13))
                        .frame(width: 160)
                }
                HStack {
                    TextField(L10n.s(.planPromptHint), text: $planPrompt)
                        .textFieldStyle(.roundedBorder)

                    Button(L10n.s(.addPlan)) {
                        let content = planText.trimmingCharacters(in: .whitespacesAndNewlines)
                        let prompt = planPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !content.isEmpty else { return }
                        Task {
                            await bridge.addPlan(content: content, customPrompt: prompt, targetDate: targetDate)
                            planText = ""
                            planPrompt = ""
                            targetDate = ""
                        }
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            .padding(.bottom, 8)

            List(bridge.plans) { item in
                PlanRowView(item: item, bridge: bridge)
            }
            .scrollIndicators(.visible)
            .onAppear {
                if bridge.plans.isEmpty {
                    Task { await bridge.loadPlans() }
                }
            }
        }
    }
}

struct PlanRowView: View {
    let item: PlanItem
    @ObservedObject var bridge: PythonBridgeService

    @State private var isEditing = false
    @State private var editPlanText = ""
    @State private var editPlanPrompt = ""
    @State private var editTargetDate = ""
    @State private var isShowingDeleteConfirm = false

    var body: some View {
        if isEditing {
            VStack(alignment: .leading, spacing: 6) {
                TextField(L10n.s(.planContentHint), text: $editPlanText)
                    .textFieldStyle(.roundedBorder)
                HStack {
                    TextField(L10n.s(.planPromptHint), text: $editPlanPrompt)
                        .textFieldStyle(.roundedBorder)
                    TextField(L10n.s(.planDateHint), text: $editTargetDate)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 160)
                }
                HStack {
                    Button(L10n.s(.save)) {
                        Task {
                            await bridge.updatePlan(id: item.id, content: editPlanText, customPrompt: editPlanPrompt, targetDate: editTargetDate)
                            isEditing = false
                        }
                    }.buttonStyle(.borderedProminent)
                    Button(L10n.s(.cancel)) { isEditing = false }.buttonStyle(.bordered)
                }
            }.padding(.vertical, 4)
        } else {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(item.content)
                        .font(.custom("Avenir Next Demi Bold", size: 16))
                    Spacer()
                    Text(item.status)
                        .font(.caption)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.green.opacity(0.2))
                        .foregroundColor(.green)
                        .clipShape(Capsule())
                        
                    Button(action: {
                        editPlanText = item.content
                        editPlanPrompt = item.customPrompt
                        editTargetDate = item.targetDate
                        isEditing = true
                    }) {
                        Image(systemName: "pencil")
                            .foregroundColor(.blue)
                    }.buttonStyle(.plain).padding(.horizontal, 4)
                    
                    Button(action: {
                        isShowingDeleteConfirm = true
                    }) {
                        Image(systemName: "trash")
                            .foregroundColor(.red)
                    }.buttonStyle(.plain)
                }
                
                if !item.customPrompt.isEmpty {
                    Text("\(L10n.s(.guidingPrinciple)): \(item.customPrompt)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                
                Text("ID: #\(item.id) | Target: \(item.targetDate.isEmpty ? "None" : item.targetDate)")
                    .font(.custom("Menlo", size: 11))
                    .foregroundStyle(.tertiary)
            }
            .padding(.vertical, 4)
            .alert(isPresented: $isShowingDeleteConfirm) {
                Alert(
                    title: Text(L10n.s(.confirmDelete)),
                    message: Text(L10n.s(.confirmDeleteMsg)),
                    primaryButton: .destructive(Text(L10n.s(.delete))) {
                        Task { await bridge.deletePlan(id: item.id) }
                    },
                    secondaryButton: .cancel()
                )
            }
        }
    }
}

struct DailyPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @AppStorage("appLanguage") private var lang = "zh"
    @State private var date = Self.isoDateNow()
    @State private var summary = ""
    @State private var suggestions = ""
    @State private var isGenerating = false
    @State private var selectedLog: DailyLogItem? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(L10n.s(.dailySummary))
                .font(.custom("Avenir Next Demi Bold", size: 28))

            HStack {
                TextField(L10n.s(.dateHint), text: $date)
                    .textFieldStyle(.roundedBorder)
                    .font(.custom("Menlo", size: 13))
                Spacer()
                Button(L10n.s(.reload)) {
                    Task { await bridge.loadLogs() }
                }
            }
            
            HStack {
                Button(isGenerating ? L10n.s(.aiGenerating) : L10n.s(.aiGenerateDraft)) {
                    Task {
                        isGenerating = true
                        if let result = await bridge.generateDailyDraft() {
                            summary = result.summary
                            suggestions = result.suggestion
                        }
                        isGenerating = false
                    }
                }
                .buttonStyle(.bordered)
                .disabled(isGenerating)
                
                if isGenerating {
                    ProgressView().controlSize(.small)
                }
            }

            TextEditor(text: $summary)
                .scrollIndicators(.visible)
                .frame(height: 120)
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.secondary.opacity(0.2)))

            TextEditor(text: $suggestions)
                .scrollIndicators(.visible)
                .frame(height: 120)
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.secondary.opacity(0.2)))

            Button(L10n.s(.saveDailyLog)) {
                Task {
                    await bridge.saveDaily(summary: summary, suggestions: suggestions, date: date)
                    summary = ""
                    suggestions = ""
                }
            }
            .buttonStyle(.borderedProminent)

            Divider()

            List(bridge.logs) { item in
                Button(action: {
                    selectedLog = item
                }) {
                    HStack {
                        Text(item.date)
                            .font(.custom("Menlo", size: 14).bold())
                        Spacer()
                        Text(item.summary.replacingOccurrences(of: "\n", with: " "))
                            .font(.custom("Avenir Next", size: 13))
                            .lineLimit(1)
                            .truncationMode(.tail)
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(.vertical, 4)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
            .scrollIndicators(.visible)
            .sheet(item: $selectedLog) { logItem in
                VStack(alignment: .leading, spacing: 16) {
                    Text("\(L10n.s(.detailTitle)) (\(logItem.date))")
                        .font(.custom("Avenir Next Demi Bold", size: 20))
                    
                    ScrollView(showsIndicators: true) {
                        VStack(alignment: .leading, spacing: 16) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(L10n.s(.summaryLabel)).font(.headline)
                                Text(logItem.summary)
                                    .font(.body)
                                    .textSelection(.enabled)
                            }
                            
                            Divider()
                            
                            VStack(alignment: .leading, spacing: 8) {
                                Text(L10n.s(.suggestionLabel)).font(.headline)
                                Text(logItem.suggestions)
                                    .font(.body)
                                    .textSelection(.enabled)
                            }
                        }
                        .padding(.trailing, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .scrollIndicators(.visible)
                    
                    HStack {
                        Spacer()
                        Button(L10n.s(.close)) {
                            selectedLog = nil
                        }
                        .keyboardShortcut(.defaultAction)
                        .buttonStyle(.borderedProminent)
                    }
                }
                .padding(20)
                .frame(minWidth: 450, minHeight: 350)
            }
            .onAppear {
                if bridge.logs.isEmpty {
                    Task { await bridge.loadLogs() }
                }
            }
        }
    }

    static func isoDateNow() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: Date())
    }
}

struct LLMSettingsPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @AppStorage("appLanguage") private var lang = "zh"
    @State private var pullModelName = ""
    @State private var runPrompt = "Say hello from local Ollama"

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(L10n.s(.llmConfiguration))
                .font(.custom("Avenir Next Demi Bold", size: 28))

            Picker("Mode", selection: $bridge.llmSettings.mode) {
                Text(L10n.s(.useAPI)).tag("api")
                Text(L10n.s(.useOllama)).tag("ollama")
            }
            .pickerStyle(.segmented)

            if bridge.llmSettings.mode == "api" {
                Group {
                    TextField(L10n.s(.apiUrlHint), text: $bridge.llmSettings.apiURL)
                        .textFieldStyle(.roundedBorder)
                    Text(L10n.s(.apiUrlTip))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    SecureField("API Key", text: $bridge.llmSettings.apiKey)
                        .textFieldStyle(.roundedBorder)
                    TextField("Model", text: $bridge.llmSettings.apiModel)
                        .textFieldStyle(.roundedBorder)
                }
            } else {
                Group {
                    TextField("Ollama Host", text: $bridge.llmSettings.ollamaHost)
                        .textFieldStyle(.roundedBorder)
                    TextField("Ollama Model", text: $bridge.llmSettings.ollamaModel)
                        .textFieldStyle(.roundedBorder)
                }

                HStack(spacing: 10) {
                    Button(L10n.s(.startOllama)) {
                        Task { await bridge.startOllamaService() }
                    }
                    .buttonStyle(.borderedProminent)

                    Button(L10n.s(.checkStatus)) {
                        Task { await bridge.refreshOllamaStatus() }
                    }
                    .buttonStyle(.bordered)

                    Button(L10n.s(.listModels)) {
                        Task { await bridge.listOllamaModels() }
                    }
                    .buttonStyle(.bordered)
                }

                Text(bridge.ollamaStatusMessage)
                    .foregroundStyle(.secondary)

                HStack(spacing: 8) {
                    TextField("Model to pull (e.g. qwen2.5:7b)", text: $pullModelName)
                        .textFieldStyle(.roundedBorder)
                    Button("Pull") {
                        let model = pullModelName.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !model.isEmpty else { return }
                        Task { await bridge.pullOllamaModel(model: model) }
                    }
                    .buttonStyle(.bordered)
                }

                if !bridge.ollamaModels.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(L10n.s(.installedModels))
                            .font(.custom("Avenir Next Demi Bold", size: 16))
                        ScrollView(showsIndicators: true) {
                            LazyVStack(alignment: .leading, spacing: 4) {
                                ForEach(bridge.ollamaModels, id: \.self) { model in
                                    Button(model) {
                                        bridge.llmSettings.ollamaModel = model
                                    }
                                    .buttonStyle(.plain)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                }
                            }
                            .padding(.trailing, 4)
                        }
                        .scrollIndicators(.visible)
                        .frame(maxHeight: 120)
                    }
                }

                TextEditor(text: $runPrompt)
                    .scrollIndicators(.visible)
                    .frame(height: 80)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.secondary.opacity(0.2)))

                Button(L10n.s(.runModel)) {
                    let prompt = runPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !prompt.isEmpty else { return }
                    Task { await bridge.runOllamaPrompt(prompt: prompt) }
                }
                .buttonStyle(.bordered)

                if !bridge.ollamaRunOutput.isEmpty {
                    Text(bridge.ollamaRunOutput)
                        .font(.custom("Menlo", size: 12))
                        .textSelection(.enabled)
                        .padding(10)
                        .background(Color.secondary.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
            }

            HStack(spacing: 12) {
                Button(L10n.s(.save)) {
                    Task { await bridge.saveLLMSettings() }
                }
                .buttonStyle(.borderedProminent)

                Button(L10n.s(.testConnection)) {
                    Task { await bridge.testLLMConnection() }
                }
                .buttonStyle(.bordered)

                Button(L10n.s(.reload)) {
                    Task { await bridge.loadLLMSettings() }
                }
                .buttonStyle(.bordered)
            }

            if !bridge.llmConfigStatus.isEmpty {
                Text(bridge.llmConfigStatus)
                    .foregroundStyle(.secondary)
            }

            if !bridge.llmTestMessage.isEmpty {
                Text(bridge.llmTestMessage)
                    .font(.custom("Menlo", size: 12))
                    .textSelection(.enabled)
                    .padding(10)
                    .background(Color.secondary.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }

            Divider()

            // Shell Security Mode
            Text(L10n.s(.shellSecurityMode))
                .font(.custom("Avenir Next Demi Bold", size: 18))

            Picker("Security Mode", selection: $bridge.shellSecurityMode) {
                Text(L10n.s(.strictLabel)).tag("strict")
                Text(L10n.s(.agentLabel)).tag("agent")
                Text(L10n.s(.selfSupervisedLabel)).tag("self_supervised")
            }
            .pickerStyle(.radioGroup)

            Group {
                switch bridge.shellSecurityMode {
                case "strict":
                    Text(L10n.s(.strictDesc))
                case "agent":
                    Text(L10n.s(.agentDesc))
                case "self_supervised":
                    Text(L10n.s(.selfSupervisedDesc))
                default:
                    EmptyView()
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)

            Button(L10n.s(.apply)) {
                Task { await bridge.setShellSecurityMode(bridge.shellSecurityMode) }
            }
            .buttonStyle(.bordered)

            Spacer()
        }
        .onAppear {
            Task {
                await bridge.loadLLMSettings()
                await bridge.refreshOllamaStatus()
            }
        }
    }
}

struct ProductivityPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @AppStorage("appLanguage") private var lang = "zh"

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(L10n.s(.productivity))
                    .font(.custom("Avenir Next Demi Bold", size: 28))
                Spacer()
                Button(L10n.s(.refresh)) {
                    Task { await bridge.loadProductivityReminders() }
                }
                .buttonStyle(.borderedProminent)
            }

            HStack(spacing: 10) {
                metricCard(title: L10n.s(.tracked), value: String(format: "%.1fh", bridge.productivityUsage.totalTrackedHours))
                metricCard(title: L10n.s(.focus), value: String(format: "%.1fh", bridge.productivityUsage.focusHours))
                metricCard(title: L10n.s(.distract), value: String(format: "%.1fh", bridge.productivityUsage.distractionHours))
                metricCard(title: L10n.s(.switches), value: "\(bridge.productivityUsage.contextSwitches)")
                metricCard(title: L10n.s(.distractPct), value: String(format: "%.0f%%", bridge.productivityUsage.distractionRatio * 100.0))
            }

            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(L10n.s(.topApps))
                        .font(.custom("Avenir Next Demi Bold", size: 17))

                    if bridge.productivityUsage.topApps.isEmpty {
                        Text(L10n.s(.noData))
                            .foregroundStyle(.secondary)
                    } else {
                        ScrollView(showsIndicators: true) {
                            VStack(alignment: .leading, spacing: 8) {
                                ForEach(bridge.productivityUsage.topApps) { item in
                                    HStack {
                                        Text(item.app)
                                        Spacer()
                                        Text(String(format: "%.1fh", item.hours))
                                            .font(.custom("Menlo", size: 12))
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                            .padding(.trailing, 6)
                        }
                        .scrollIndicators(.visible)
                        .frame(maxHeight: 180)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                VStack(alignment: .leading, spacing: 8) {
                    Text(L10n.s(.backgroundHotspots))
                        .font(.custom("Avenir Next Demi Bold", size: 17))

                    if bridge.productivityUsage.backgroundHotspots.isEmpty {
                        Text(L10n.s(.noData))
                            .foregroundStyle(.secondary)
                    } else {
                        ScrollView(showsIndicators: true) {
                            VStack(alignment: .leading, spacing: 8) {
                                ForEach(bridge.productivityUsage.backgroundHotspots) { item in
                                    HStack {
                                        Text(item.name)
                                        Spacer()
                                        Text(String(format: "%.1fh", item.weightedHours))
                                            .font(.custom("Menlo", size: 12))
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                            .padding(.trailing, 6)
                        }
                        .scrollIndicators(.visible)
                        .frame(maxHeight: 180)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            Divider()

            Text(L10n.s(.reminders))
                .font(.custom("Avenir Next Demi Bold", size: 19))

            if bridge.productivityReminders.isEmpty {
                Text(L10n.s(.noReminders))
                    .foregroundStyle(.secondary)
            } else {
                ScrollView(showsIndicators: true) {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(bridge.productivityReminders) { reminder in
                            VStack(alignment: .leading, spacing: 6) {
                                HStack {
                                    Text(reminder.type)
                                        .font(.custom("Menlo", size: 11))
                                        .foregroundStyle(.secondary)
                                    Spacer()
                                    Text(reminder.severity.uppercased())
                                        .font(.custom("Menlo", size: 11))
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 3)
                                        .background(Color.accentColor.opacity(0.18))
                                        .clipShape(Capsule())
                                }
                                Text(reminder.message)
                                    .font(.custom("Avenir Next", size: 14))
                                Text("\(L10n.s(.suggestion)): \(reminder.action)")
                                    .font(.custom("Avenir Next", size: 13))
                                    .foregroundStyle(.secondary)
                            }
                            .padding(10)
                            .background(Color.secondary.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        }
                    }
                    .padding(.trailing, 8)
                }
                .scrollIndicators(.visible)
            }

            if !bridge.productivityStatus.isEmpty {
                Text(bridge.productivityStatus)
                    .font(.custom("Menlo", size: 11))
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .onAppear {
            if bridge.productivityReminders.isEmpty {
                Task { await bridge.loadProductivityReminders() }
            }
        }
    }

    private func metricCard(title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.custom("Avenir Next", size: 12))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.custom("Avenir Next Demi Bold", size: 18))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Color.secondary.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}
