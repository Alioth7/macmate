import SwiftUI

/// Centralized localization for MacMate UI.
/// Language preference is stored via @AppStorage("appLanguage").
enum Lang: String, CaseIterable {
    case zh = "zh"
    case en = "en"

    var displayName: String {
        switch self {
        case .zh: return "中文"
        case .en: return "English"
        }
    }
}

/// Usage: `L10n.s(.chatTitle)`  returns the localized string for current language.
enum L10n {
    // Read the stored preference; default to Chinese.
    static var current: Lang {
        Lang(rawValue: UserDefaults.standard.string(forKey: "appLanguage") ?? "zh") ?? .zh
    }

    enum Key {
        // -- Sidebar --
        case chat, calendar, productivity, quadrant, scene, music, weather, plans, daily, llmSettings

        // -- Chat --
        case agentChat, loadHistory, saveHistory, clearChat, send
        case agentThinking, agentSteps, chatPlaceholder
        case loaded, saved

        // -- Calendar --
        case dayView, weekView, refresh
        case calendarDenied, openSettings

        // -- Plans --
        case longTermPlans, addPlan, save, cancel, edit
        case planContentHint, planDateHint, planPromptHint
        case confirmDelete, confirmDeleteMsg, delete

        // -- Daily --
        case dailySummary, reload, aiGenerateDraft, aiGenerating
        case saveDailyLog, dateHint
        case detailTitle, summaryLabel, suggestionLabel, close

        // -- LLM --
        case llmConfiguration, useAPI, useOllama
        case apiUrlHint, apiUrlTip, testConnection, installedModels
        case startOllama, checkStatus, listModels, pullModel, runModel
        case shellSecurityMode, apply
        case strictLabel, agentLabel, selfSupervisedLabel
        case strictDesc, agentDesc, selfSupervisedDesc

        // -- Productivity --
        case tracked, focus, distract, switches, distractPct
        case topApps, backgroundHotspots, reminders
        case noData, noReminders, suggestion

        // -- Scene --
        case sceneProfiles, sceneSubtitle
        case focusMode, focusSub, relaxMode, relaxSub, switching

        // -- Music --
        case playerLabel, playlistHint, play, pause, volume, nowPlaying

        // -- Weather --
        case cityHint, queryWeather, humidity, windSpeed, windDir, feelsLike

        // -- Quadrant --
        case eisenhowerMatrix, analyze7Days, analyzeToday, showDetailList
        case noQuadrantData, quadrantHint

        // -- Misc --
        case guidingPrinciple, showDebugStatus
    }

    static func s(_ key: Key) -> String {
        let zh: String
        let en: String

        switch key {
        // Sidebar
        case .chat:          zh = "对话";           en = "Chat"
        case .calendar:      zh = "日历";           en = "Calendar"
        case .productivity:  zh = "生产力";         en = "Productivity"
        case .quadrant:      zh = "四象限";         en = "Quadrant"
        case .scene:         zh = "场景";           en = "Scene"
        case .music:         zh = "音乐";           en = "Music"
        case .weather:       zh = "天气";           en = "Weather"
        case .plans:         zh = "规划";           en = "Plans"
        case .daily:         zh = "日报";           en = "Daily"
        case .llmSettings:   zh = "LLM 设置";      en = "LLM Settings"

        // Chat
        case .agentChat:     zh = "Agent 对话";     en = "Agent Chat"
        case .loadHistory:   zh = "加载最近聊天记录"; en = "Load chat history"
        case .saveHistory:   zh = "保存聊天记录";    en = "Save chat history"
        case .clearChat:     zh = "清空当前对话上下文"; en = "Clear chat context"
        case .send:          zh = "发送";           en = "Send"
        case .agentThinking: zh = "Agent 正在思考并执行工具..."; en = "Agent is thinking..."
        case .agentSteps:    zh = "Agent 思考与执行过程"; en = "Agent Steps (Reasoning)"
        case .chatPlaceholder: zh = "Enter发送，Shift+Enter换行"; en = "Enter to send, Shift+Enter for newline"
        case .loaded:        zh = "已加载";          en = "Loaded"
        case .saved:         zh = "已保存";          en = "Saved"

        // Calendar
        case .dayView:       zh = "日视图 (今天)";   en = "Day View (Today)"
        case .weekView:      zh = "周视图 (7天甘特图)"; en = "Week View (7 Days Gantt)"
        case .refresh:       zh = "刷新";           en = "Refresh"
        case .calendarDenied: zh = "日历权限被拒绝，请在系统设置中允许 MacMate 访问日历。"; en = "Calendar access denied. Please allow MacMate in System Settings."
        case .openSettings:  zh = "打开设置";        en = "Open Settings"

        // Plans
        case .longTermPlans: zh = "长期规划";        en = "Long-term Plans"
        case .addPlan:       zh = "添加规划";        en = "Add Plan"
        case .save:          zh = "保存";           en = "Save"
        case .cancel:        zh = "取消";           en = "Cancel"
        case .edit:          zh = "编辑";           en = "Edit"
        case .planContentHint: zh = "目标内容";      en = "Plan content"
        case .planDateHint:  zh = "目标日期 YYYY-MM-DD"; en = "Target date YYYY-MM-DD"
        case .planPromptHint: zh = "指导原则 / Prompt"; en = "Guiding principle / Prompt"
        case .confirmDelete: zh = "确认删除?";       en = "Confirm Delete?"
        case .confirmDeleteMsg: zh = "确实要删除此长期规划吗？"; en = "Are you sure you want to delete this plan?"
        case .delete:        zh = "删除";           en = "Delete"

        // Daily
        case .dailySummary:  zh = "日报总结";        en = "Daily Summary"
        case .reload:        zh = "重新加载";        en = "Reload"
        case .aiGenerateDraft: zh = "AI 生成草稿";   en = "AI Generate Draft"
        case .aiGenerating:  zh = "AI 生成中...";    en = "AI Generating..."
        case .saveDailyLog:  zh = "保存日报";        en = "Save Daily Log"
        case .dateHint:      zh = "日期 YYYY-MM-DD"; en = "Date YYYY-MM-DD"
        case .detailTitle:   zh = "日报详情";        en = "Daily Detail"
        case .summaryLabel:  zh = "总结";           en = "Summary"
        case .suggestionLabel: zh = "建议";          en = "Suggestions"
        case .close:         zh = "关闭";           en = "Close"

        // LLM
        case .llmConfiguration: zh = "LLM 配置";    en = "LLM Configuration"
        case .useAPI:        zh = "使用 API";       en = "Use API"
        case .useOllama:     zh = "使用 Ollama (本地)"; en = "Use Ollama (Local)"
        case .apiUrlHint:    zh = "API URL (OpenAI 兼容 /chat/completions)"; en = "API URL (OpenAI-compatible /chat/completions)"
        case .apiUrlTip:     zh = "输入基础 URL 即可 (如 https://api.openai.com)，系统会自动补全 /v1/chat/completions"; en = "Enter base URL (e.g. https://api.openai.com), /v1/chat/completions will be auto-appended"
        case .testConnection: zh = "测试连接";       en = "Test Connection"
        case .installedModels: zh = "已安装模型";     en = "Installed Models"
        case .startOllama:   zh = "启动 Ollama";    en = "Start Ollama"
        case .checkStatus:   zh = "检查状态";        en = "Check Status"
        case .listModels:    zh = "列出模型";        en = "List Models"
        case .pullModel:     zh = "拉取";           en = "Pull"
        case .runModel:      zh = "运行当前模型";     en = "Run Current Model"
        case .shellSecurityMode: zh = "Shell 安全模式"; en = "Shell Security Mode"
        case .apply:         zh = "应用";           en = "Apply"
        case .strictLabel:   zh = "Strict — 用户审查每条命令"; en = "Strict — User reviews every command"
        case .agentLabel:    zh = "Agent — AI 自主判断"; en = "Agent — AI decides autonomously"
        case .selfSupervisedLabel: zh = "Self-supervised — LLM 安全审查"; en = "Self-supervised — LLM safety review"
        case .strictDesc:    zh = "每条 Shell 命令执行前都需要用户手动确认，最安全。"; en = "Every shell command requires manual user confirmation. Safest mode."
        case .agentDesc:     zh = "AI 可执行大部分命令，但黑名单中的危险命令 (rm -rf, mkfs 等) 仍被拦截。"; en = "AI executes most commands, but blacklisted dangerous commands are still blocked."
        case .selfSupervisedDesc: zh = "所有命令先经 LLM 安全审查后再执行，需要 LLM 已配置。"; en = "All commands are reviewed by LLM before execution. Requires LLM configured."

        // Productivity
        case .tracked:       zh = "已追踪";          en = "Tracked"
        case .focus:         zh = "专注";            en = "Focus"
        case .distract:      zh = "分心";            en = "Distract"
        case .switches:      zh = "切换次数";        en = "Switches"
        case .distractPct:   zh = "分心率";          en = "Distract %"
        case .topApps:       zh = "常用应用";         en = "Top Apps"
        case .backgroundHotspots: zh = "后台热点";    en = "Background Hotspots"
        case .reminders:     zh = "提醒";            en = "Reminders"
        case .noData:        zh = "暂无数据";         en = "No data yet"
        case .noReminders:   zh = "暂无提醒，点击刷新获取最新分析"; en = "No reminders yet. Click Refresh to update."
        case .suggestion:    zh = "建议";            en = "Suggestion"

        // Scene
        case .sceneProfiles: zh = "场景配置";         en = "Scene Profiles"
        case .sceneSubtitle: zh = "一键切换工作/休闲模式，自动管理应用和勿扰状态"; en = "One-click switch between Focus/Relax mode"
        case .focusMode:     zh = "专注模式";         en = "Focus Mode"
        case .focusSub:      zh = "开启勿扰 · 关闭社交 · 启动 Terminal"; en = "DND on · Close social apps · Open Terminal"
        case .relaxMode:     zh = "休闲模式";         en = "Relax Mode"
        case .relaxSub:      zh = "关闭办公App · 关闭勿扰"; en = "Close work apps · DND off"
        case .switching:     zh = "切换中...";        en = "Switching..."

        // Music
        case .playerLabel:   zh = "播放器";           en = "Player"
        case .playlistHint:  zh = "歌单关键词 (仅 Apple Music)"; en = "Playlist keyword (Apple Music only)"
        case .play:          zh = "播放";             en = "Play"
        case .pause:         zh = "暂停";             en = "Pause"
        case .volume:        zh = "音量:";            en = "Volume:"
        case .nowPlaying:    zh = "正在播放";          en = "Now Playing"

        // Weather
        case .cityHint:      zh = "城市 (留空自动定位)"; en = "City (leave empty for auto-locate)"
        case .queryWeather:  zh = "查询天气";          en = "Get Weather"
        case .humidity:      zh = "湿度";              en = "Humidity"
        case .windSpeed:     zh = "风速";              en = "Wind"
        case .windDir:       zh = "风向";              en = "Direction"
        case .feelsLike:     zh = "体感";              en = "Feels like"

        // Quadrant
        case .eisenhowerMatrix: zh = "四象限矩阵";     en = "Eisenhower Matrix"
        case .analyze7Days:  zh = "分析7天日程";        en = "Analyze 7 Days"
        case .analyzeToday:  zh = "分析近期日程(今日至明早)"; en = "Analyze Today~Tomorrow"
        case .showDetailList: zh = "显示详细列表";      en = "Show Detail List"
        case .noQuadrantData: zh = "暂无数据，请点击上方按钮进行AI分析。"; en = "No data yet. Click a button above to run AI analysis."
        case .quadrantHint:  zh = "提示: 请确保LLM已配置，并在「系统设置 → 隐私与安全 → 日历」中授权。"; en = "Tip: Ensure LLM is configured and Calendar access is granted in System Settings."

        // Misc
        case .guidingPrinciple: zh = "指导原则"; en = "Guiding Principle"
        case .showDebugStatus: zh = "显示调试状态"; en = "Show Debug Status"
        }

        return current == .zh ? zh : en
    }
}
