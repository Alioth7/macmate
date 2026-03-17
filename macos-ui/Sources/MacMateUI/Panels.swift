import SwiftUI
import Charts

struct ChatPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @Environment(\.colorScheme) private var colorScheme
    @State private var inputText = ""
    @State private var isStepsExpanded = true
    @State private var isThinking = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Agent Chat")
                    .font(.custom("Avenir Next Demi Bold", size: 28))
                Spacer()
                Button(action: {
                    Task { await bridge.clearChat() }
                }) {
                    Image(systemName: "trash")
                        .foregroundColor(.red)
                }
                .buttonStyle(.plain)
                .help("清空当前对话上下文")
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
                    if isThinking {
                        HStack {
                            ProgressView().controlSize(.small)
                            Text("Agent 正在思考并执行工具...").font(.caption).foregroundColor(.secondary)
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
                DisclosureGroup("Agent Steps (思考与执行过程)", isExpanded: $isStepsExpanded) {
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

            HStack(spacing: 12) {
                TextField("输入任务，比如：帮我安排周五下午代码评审", text: $inputText)
                    .textFieldStyle(.roundedBorder)
                    .font(.custom("Avenir Next", size: 15))
                    .disabled(isThinking)

                Button("Send") {
                    let prompt = inputText
                    inputText = ""
                    bridge.latestTrace.removeAll() // clean up old trace
                    isThinking = true
                    Task { 
                        await bridge.sendChat(prompt: prompt) 
                        isThinking = false
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isThinking || inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
    }

    private func bubble(text: String, tint: Color) -> some View {
        Text(text)
            .font(.custom("Avenir Next", size: 14))
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
}

struct CalendarPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @State private var viewMode: Int = 1 // 0: Today, 1: Upcoming 7 Days

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Calendar")
                    .font(.custom("Avenir Next Demi Bold", size: 28))
                
                Picker("", selection: $viewMode) {
                    Text("Day View (Today)").tag(0)
                    Text("Week View (7 Days Gantt)").tag(1)
                }
                .pickerStyle(.segmented)
                .frame(width: 320)
                .padding(.leading, 12)

                Spacer()
                Button("Refresh") {
                    Task { await bridge.loadCalendar() }
                }
                .buttonStyle(.bordered)
            }

            if bridge.calendarPermissionDenied {
                HStack(spacing: 12) {
                    Text("日历权限被拒绝，请在系统设置中允许 MacMate 访问日历。")
                        .foregroundStyle(.secondary)
                    Button("Open Settings") {
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
    @State private var planText = ""
    @State private var planPrompt = ""
    @State private var targetDate = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Long-term Plans")
                .font(.custom("Avenir Next Demi Bold", size: 28))

            VStack(spacing: 8) {
                HStack {
                    TextField("目标内容（例如：学习 Python 进阶）", text: $planText)
                        .textFieldStyle(.roundedBorder)
                    TextField("目标日期 YYYY-MM-DD", text: $targetDate)
                        .textFieldStyle(.roundedBorder)
                        .font(.custom("Menlo", size: 13))
                        .frame(width: 160)
                }
                HStack {
                    TextField("指导原则 / Prompt（如：时刻提醒我要保持代码简洁）", text: $planPrompt)
                        .textFieldStyle(.roundedBorder)

                    Button("Add Plan") {
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
                TextField("目标内容", text: $editPlanText)
                    .textFieldStyle(.roundedBorder)
                HStack {
                    TextField("指导原则", text: $editPlanPrompt)
                        .textFieldStyle(.roundedBorder)
                    TextField("目标日期 YYYY-MM-DD", text: $editTargetDate)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 160)
                }
                HStack {
                    Button("Save") {
                        Task {
                            await bridge.updatePlan(id: item.id, content: editPlanText, customPrompt: editPlanPrompt, targetDate: editTargetDate)
                            isEditing = false
                        }
                    }.buttonStyle(.borderedProminent)
                    Button("Cancel") { isEditing = false }.buttonStyle(.bordered)
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
                    Text("💡 指导原则: \(item.customPrompt)")
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
                    title: Text("确认删除?"),
                    message: Text("确实要删除此长期规划吗？"),
                    primaryButton: .destructive(Text("删除")) {
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
    @State private var date = Self.isoDateNow()
    @State private var summary = ""
    @State private var suggestions = ""
    @State private var isGenerating = false
    @State private var selectedLog: DailyLogItem? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Daily Summary")
                .font(.custom("Avenir Next Demi Bold", size: 28))

            HStack {
                TextField("日期 YYYY-MM-DD", text: $date)
                    .textFieldStyle(.roundedBorder)
                    .font(.custom("Menlo", size: 13))
                Spacer()
                Button("Reload") {
                    Task { await bridge.loadLogs() }
                }
            }
            
            HStack {
                Button(isGenerating ? "🤖 AI Generating..." : "🤖 AI Generate Draft") {
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

            Button("Save Daily Log") {
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
                    Text("日报详情 (\(logItem.date))")
                        .font(.custom("Avenir Next Demi Bold", size: 20))
                    
                    ScrollView(showsIndicators: true) {
                        VStack(alignment: .leading, spacing: 16) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("💡 总结").font(.headline)
                                Text(logItem.summary)
                                    .font(.body)
                                    .textSelection(.enabled)
                            }
                            
                            Divider()
                            
                            VStack(alignment: .leading, spacing: 8) {
                                Text("🎯 建议").font(.headline)
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
                        Button("Close") {
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
    @State private var pullModelName = ""
    @State private var runPrompt = "Say hello from local Ollama"

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("LLM Configuration")
                .font(.custom("Avenir Next Demi Bold", size: 28))

            Picker("Mode", selection: $bridge.llmSettings.mode) {
                Text("Use API").tag("api")
                Text("Use Ollama (Local)").tag("ollama")
            }
            .pickerStyle(.segmented)

            if bridge.llmSettings.mode == "api" {
                Group {
                    TextField("API URL (OpenAI-compatible /chat/completions)", text: $bridge.llmSettings.apiURL)
                        .textFieldStyle(.roundedBorder)
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
                    Button("Start Ollama") {
                        Task { await bridge.startOllamaService() }
                    }
                    .buttonStyle(.borderedProminent)

                    Button("Check Status") {
                        Task { await bridge.refreshOllamaStatus() }
                    }
                    .buttonStyle(.bordered)

                    Button("List Models") {
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
                        Text("Installed Models")
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

                Button("Run Current Model") {
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
                Button("Save") {
                    Task { await bridge.saveLLMSettings() }
                }
                .buttonStyle(.borderedProminent)

                Button("Test Connection") {
                    Task { await bridge.testLLMConnection() }
                }
                .buttonStyle(.bordered)

                Button("Reload") {
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
