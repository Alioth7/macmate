import Foundation
import SwiftUI

@MainActor
final class PythonBridgeService: ObservableObject {
    @Published var statusText: String = "Bridge: connecting"
    @Published var chatMessages: [ChatMessage] = [
        ChatMessage(role: "assistant", content: "你好，我是 MacMate。")
    ]
    @Published var calendarEvents: [CalendarEvent] = []
    @Published var calendarPermissionDenied: Bool = false
    @Published var plans: [PlanItem] = []
    @Published var logs: [DailyLogItem] = []
    @Published var quadrantItems: [QuadrantItem] = []
    @Published var productivityUsage: ProductivityUsageSummary = .empty
    @Published var productivityReminders: [ProductivityReminderItem] = []
    @Published var productivityStatus: String = ""
    @Published var latestTrace: [String] = []
    @Published var llmSettings: LLMSettingsData = .init()
    @Published var llmConfigStatus: String = ""
    @Published var llmTestMessage: String = ""
    @Published var ollamaStatusMessage: String = ""
    @Published var ollamaModels: [String] = []
    @Published var ollamaRunOutput: String = ""

    private var process: Process?
    private var stdinPipe: Pipe?
    private var stdoutPipe: Pipe?

    private var pendingReplies: [String: CheckedContinuation<BridgeEnvelope, Error>] = [:]
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    func startBridgeProcessIfNeeded() {
        guard process == nil else { return }

        let bridgePath = resolveBridgePath()
        let pythonExec = ProcessInfo.processInfo.environment["MACMATE_PYTHON"] ?? "python3"

        let proc = Process()
        // 使用 zsh -l (login shell) 启动，这样能自动加载你的 ~/.zshrc (包含 Conda 环境变量等)
        proc.executableURL = URL(fileURLWithPath: "/bin/zsh")
        proc.arguments = ["-l", "-c", "exec \(pythonExec) -u \"\(bridgePath)\""]
        proc.currentDirectoryURL = URL(fileURLWithPath: repositoryRoot())

        let inPipe = Pipe()
        let outPipe = Pipe()
        proc.standardInput = inPipe
        proc.standardOutput = outPipe
        proc.standardError = outPipe

        outPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard let self = self, !data.isEmpty else { return }
            Task { @MainActor in
                self.consumeOutputData(data)
            }
        }

        do {
            try proc.run()
            process = proc
            stdinPipe = inPipe
            stdoutPipe = outPipe
            statusText = "Bridge: online"

            proc.terminationHandler = { [weak self] process in
                Task { @MainActor in
                    guard let self = self else { return }
                    self.process = nil
                    self.stdinPipe = nil
                    self.stdoutPipe = nil
                    self.statusText = "Bridge exited (code: \(process.terminationStatus))"

                    let error = NSError(
                        domain: "bridge",
                        code: Int(process.terminationStatus),
                        userInfo: [NSLocalizedDescriptionKey: "Python bridge exited unexpectedly"]
                    )
                    for (_, continuation) in self.pendingReplies {
                        continuation.resume(throwing: error)
                    }
                    self.pendingReplies.removeAll()
                }
            }

            Task {
                _ = try? await request(action: "health", payload: [:])
                await self.loadLLMSettings()
            }
        } catch {
            statusText = "Bridge start failed: \(error.localizedDescription)"
        }
    }

    func loadLLMSettings() async {
        do {
            let envelope = try await request(action: "llm_config_get", payload: [:])
            guard let result = envelope.result?.objectValue,
                  let cfg = result["config"]?.objectValue else {
                llmConfigStatus = "读取 LLM 配置失败"
                return
            }

            llmSettings = LLMSettingsData.from(json: cfg)
            llmConfigStatus = "LLM 配置已加载"
        } catch {
            llmConfigStatus = "读取 LLM 配置失败: \(error.localizedDescription)"
        }
    }

    func saveLLMSettings() async {
        do {
            let envelope = try await request(action: "llm_config_set", payload: llmSettings.toPayload())
            guard let result = envelope.result?.objectValue else {
                llmConfigStatus = "保存失败"
                return
            }

            if let cfg = result["config"]?.objectValue {
                llmSettings = LLMSettingsData.from(json: cfg)
            }
            llmConfigStatus = "已保存 LLM 配置"
        } catch {
            llmConfigStatus = "保存失败: \(error.localizedDescription)"
        }
    }

    func testLLMConnection() async {
        do {
            let envelope = try await request(action: "llm_test", payload: [:])
            guard let result = envelope.result?.objectValue else {
                llmTestMessage = "测试失败：无返回"
                return
            }
            let ok = result["ok"]?.boolValue ?? false
            let msg = result["message"]?.stringValue ?? ""
            llmTestMessage = ok ? "测试成功: \(msg)" : "测试失败: \(msg)"
        } catch {
            llmTestMessage = "测试失败: \(error.localizedDescription)"
        }
    }

    func refreshOllamaStatus() async {
        do {
            let envelope = try await request(action: "ollama_status", payload: [:])
            guard let result = envelope.result?.objectValue else {
                ollamaStatusMessage = "无法读取 Ollama 状态"
                return
            }

            let installed = result["installed"]?.boolValue ?? false
            let running = result["running"]?.boolValue ?? false
            let host = result["host"]?.stringValue ?? llmSettings.ollamaHost
            let message = result["message"]?.stringValue ?? ""

            let models = result["models"]?.arrayValue?.compactMap { $0.stringValue } ?? []
            ollamaModels = models

            if !installed {
                ollamaStatusMessage = "未检测到 ollama 命令，请先安装 Ollama。"
            } else if running {
                ollamaStatusMessage = "Ollama 运行中 (\(host))，模型数: \(models.count)"
            } else {
                ollamaStatusMessage = "Ollama 未运行: \(message)"
            }
        } catch {
            ollamaStatusMessage = "读取 Ollama 状态失败: \(error.localizedDescription)"
        }
    }

    func startOllamaService() async {
        do {
            let envelope = try await request(action: "ollama_start", payload: [:])
            guard let result = envelope.result?.objectValue else {
                ollamaStatusMessage = "启动失败"
                return
            }
            let ok = result["ok"]?.boolValue ?? false
            let message = result["message"]?.stringValue ?? ""
            ollamaStatusMessage = ok ? "已启动: \(message)" : "启动失败: \(message)"
            await refreshOllamaStatus()
        } catch {
            ollamaStatusMessage = "启动失败: \(error.localizedDescription)"
        }
    }

    func listOllamaModels() async {
        do {
            let envelope = try await request(action: "ollama_list_models", payload: [:])
            guard let result = envelope.result?.objectValue else {
                ollamaStatusMessage = "获取模型列表失败"
                return
            }
            let ok = result["ok"]?.boolValue ?? false
            if ok {
                ollamaModels = result["models"]?.arrayValue?.compactMap { $0.stringValue } ?? []
                ollamaStatusMessage = "已获取模型列表，数量: \(ollamaModels.count)"
            } else {
                ollamaStatusMessage = "获取模型列表失败: \(result["message"]?.stringValue ?? "")"
            }
        } catch {
            ollamaStatusMessage = "获取模型列表失败: \(error.localizedDescription)"
        }
    }

    func pullOllamaModel(model: String) async {
        do {
            let envelope = try await request(action: "ollama_pull_model", payload: ["model": .string(model)])
            guard let result = envelope.result?.objectValue else {
                ollamaStatusMessage = "拉取失败"
                return
            }
            let ok = result["ok"]?.boolValue ?? false
            let message = result["message"]?.stringValue ?? ""
            ollamaStatusMessage = ok ? "拉取成功: \(message)" : "拉取失败: \(message)"
            if ok { await listOllamaModels() }
        } catch {
            ollamaStatusMessage = "拉取失败: \(error.localizedDescription)"
        }
    }

    func runOllamaPrompt(prompt: String) async {
        do {
            let envelope = try await request(action: "ollama_run", payload: [
                "model": .string(llmSettings.ollamaModel),
                "prompt": .string(prompt),
            ])
            guard let result = envelope.result?.objectValue else {
                ollamaRunOutput = "运行失败：无返回"
                return
            }
            let ok = result["ok"]?.boolValue ?? false
            if ok {
                ollamaRunOutput = result["response"]?.stringValue ?? ""
            } else {
                ollamaRunOutput = "运行失败: \(result["message"]?.stringValue ?? "")"
            }
        } catch {
            ollamaRunOutput = "运行失败: \(error.localizedDescription)"
        }
    }

    func sendChat(prompt: String) async {
        guard !prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        chatMessages.append(ChatMessage(role: "user", content: prompt))

        do {
            let envelope = try await request(action: "chat", payload: ["prompt": .string(prompt)])
            guard let result = envelope.result?.objectValue else {
                chatMessages.append(ChatMessage(role: "assistant", content: "后端返回为空。"))
                return
            }

            let answer = result["answer"]?.stringValue ?? "无回复"
            // latestTrace is now populated in real-time via stream events

            chatMessages.append(ChatMessage(role: "assistant", content: answer))
        } catch {
            chatMessages.append(ChatMessage(role: "assistant", content: "请求失败: \(error.localizedDescription)"))
        }
    }

    func clearChat() async {
        chatMessages = [ChatMessage(role: "assistant", content: "上下文已清空，我们可以开始新的对话了。")]
        latestTrace.removeAll()
        do {
            _ = try await request(action: "chat_clear", payload: [:])
        } catch {
            print("Clear chat failed on backend: \(error)")
        }
    }

    func loadCalendar() async {
        calendarPermissionDenied = false

        do {
            let events = try await NativeCalendarService.shared.fetchUpcomingEvents(days: 14)
            calendarEvents = events
            statusText = "Calendar: native EventKit"
            return
        } catch {
            if case NativeCalendarError.accessDenied = error {
                calendarPermissionDenied = true
                statusText = "Calendar native failed: access denied"
            } else {
                statusText = "Calendar native failed: \(error.localizedDescription)"
            }
        }

        do {
            let envelope = try await request(action: "calendar_detailed", payload: [:])
            guard let result = envelope.result?.objectValue else { return }
            let items = result["events"]?.arrayValue ?? []
            calendarEvents = items.compactMap { $0.objectValue }.map(CalendarEvent.from)
        } catch {
            statusText = "加载日历失败: \(error.localizedDescription)"
        }
    }

    func loadPlans() async {
        do {
            let envelope = try await request(action: "plans_list", payload: [:])
            guard let result = envelope.result?.objectValue else { return }
            let items = result["plans"]?.arrayValue ?? []
            plans = items.compactMap { $0.objectValue }.map(PlanItem.from)
        } catch {
            statusText = "读取计划失败: \(error.localizedDescription)"
        }
    }

    func addPlan(content: String, customPrompt: String = "", targetDate: String) async {
        do {
            _ = try await request(action: "plan_add", payload: [
                "content": .string(content),
                "custom_prompt": .string(customPrompt),
                "target_date": .string(targetDate)
            ])
            await loadPlans()
        } catch {
            statusText = "新增计划失败: \(error.localizedDescription)"
        }
    }

    func updatePlan(id: Int, content: String, customPrompt: String = "", targetDate: String) async {
        do {
            _ = try await request(action: "plan_update", payload: [
                "id": .int(id),
                "content": .string(content),
                "custom_prompt": .string(customPrompt),
                "target_date": .string(targetDate)
            ])
            await loadPlans()
        } catch {
            statusText = "更新计划失败: \(error.localizedDescription)"
        }
    }

    func deletePlan(id: Int) async {
        do {
            _ = try await request(action: "plan_delete", payload: [
                "id": .int(id)
            ])
            await loadPlans()
        } catch {
            statusText = "删除计划失败: \(error.localizedDescription)"
        }
    }

    func loadLogs() async {
        do {
            let envelope = try await request(action: "daily_logs", payload: [:])
            guard let result = envelope.result?.objectValue else { return }
            let items = result["logs"]?.arrayValue ?? []
            logs = items.compactMap { $0.objectValue }.map(DailyLogItem.from)
                .sorted { $0.date > $1.date }
        } catch {
            statusText = "读取日报失败: \(error.localizedDescription)"
        }
    }

    func saveDaily(summary: String, suggestions: String, date: String) async {
        do {
            _ = try await request(action: "daily_save", payload: [
                "date": .string(date),
                "summary": .string(summary),
                "suggestions": .string(suggestions)
            ])
            await loadLogs()
        } catch {
            statusText = "保存日报失败: \(error.localizedDescription)"
        }
    }

    func generateDailyDraft() async -> (summary: String, suggestion: String)? {
        statusText = "generating AI summary draft..."
        do {
            let res = try await request(action: "daily_ai_draft", payload: [:])
            if let result = res.result?.objectValue {
                let s = result["summary"]?.stringValue ?? ""
                let sugg = result["suggestion"]?.stringValue ?? ""
                statusText = "AI draft generated"
                return (s, sugg)
            }
        } catch {
            statusText = "Failed to generate AI draft: \(error.localizedDescription)"
        }
        return nil
    }

    func loadQuadrantAnalysis(period: String = "today") async {
        statusText = "running quadrant analysis..."
        do {
            let res = try await request(action: "quadrant_analysis", payload: ["period": .string(period)])
            if let result = res.result?.objectValue,
               let arr = result["data"]?.arrayValue {
                self.quadrantItems = arr.compactMap {
                    if let obj = $0.objectValue {
                        return QuadrantItem.from(json: obj)
                    }
                    return nil
                }
                statusText = "quadrant analysis done"
            }
        } catch {
            statusText = "Failed to load quadrant analysis."
        }
    }

    func loadProductivityReminders() async {
        productivityStatus = "分析中..."
        do {
            let envelope = try await request(action: "productivity_reminders", payload: [:])
            guard let result = envelope.result?.objectValue else {
                productivityStatus = "后端返回为空"
                return
            }

            if let usageObj = result["usage"]?.objectValue {
                productivityUsage = ProductivityUsageSummary.from(json: usageObj)
            } else {
                productivityUsage = .empty
            }

            let reminders = result["reminders"]?.arrayValue?.compactMap { value -> ProductivityReminderItem? in
                guard let obj = value.objectValue else { return nil }
                return ProductivityReminderItem.from(json: obj)
            } ?? []
            productivityReminders = reminders
            productivityStatus = "已更新提醒"
        } catch {
            productivityStatus = "加载失败: \(error.localizedDescription)"
        }
    }

    private func request(action: String, payload: [String: JSONValue]) async throws -> BridgeEnvelope {
        guard let proc = process, proc.isRunning else {
            throw NSError(domain: "bridge", code: 1, userInfo: [NSLocalizedDescriptionKey: "Bridge process is not running"])
        }

        guard let inHandle = stdinPipe?.fileHandleForWriting else {
            throw NSError(domain: "bridge", code: 1, userInfo: [NSLocalizedDescriptionKey: "Bridge not running"])
        }

        let id = UUID().uuidString
        let req = BridgeRequest(id: id, action: action, payload: payload)
        let data = try encoder.encode(req)

        return try await withCheckedThrowingContinuation { continuation in
            pendingReplies[id] = continuation

            var framed = Data()
            framed.append(data)
            framed.append("\n".data(using: .utf8)!)

            do {
                try inHandle.write(contentsOf: framed)
            } catch {
                pendingReplies.removeValue(forKey: id)
                continuation.resume(throwing: error)
            }
        }
    }

    private func consumeOutputData(_ data: Data) {
        guard let text = String(data: data, encoding: .utf8) else { return }
        let lines = text.split(separator: "\n", omittingEmptySubsequences: true)

        for line in lines {
            guard let jsonData = line.data(using: .utf8) else { continue }
            if let envelope = try? decoder.decode(BridgeEnvelope.self, from: jsonData) {
                if let id = envelope.id {
                    if let continuation = pendingReplies.removeValue(forKey: id) {
                        continuation.resume(returning: envelope)
                    }
                } else if let result = envelope.result?.objectValue, result["event"]?.stringValue == "trace" {
                    let stepType = result["type"]?.stringValue ?? "step"
                    let content = result["content"]?.stringValue ?? ""
                    let formatted = "[\(stepType)] \(content)"
                    // Keep latestTrace updated in real-time
                    self.latestTrace.append(formatted)
                }
            }
        }
    }

    private func repositoryRoot() -> String {
        let cwd = FileManager.default.currentDirectoryPath
        if cwd.hasSuffix("/macos-ui") {
            return URL(fileURLWithPath: cwd).deletingLastPathComponent().path
        }
        return cwd
    }

    private func resolveBridgePath() -> String {
        if let envPath = ProcessInfo.processInfo.environment["MACMATE_BRIDGE_PATH"], !envPath.isEmpty {
            return envPath
        }

        let root = repositoryRoot()
        return root + "/bridge_server.py"
    }
}
