import Foundation

struct BridgeEnvelope: Codable {
    let id: String?
    let ok: Bool
    let result: JSONValue?
    let error: String?
}

struct BridgeRequest: Encodable {
    let id: String
    let action: String
    let payload: [String: JSONValue]
}

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: String
    let content: String
}

struct CalendarEvent: Identifiable {
    let id = UUID()
    let task: String
    let start: String
    let finish: String
    let duration: String

    static func from(json: [String: JSONValue]) -> CalendarEvent {
        CalendarEvent(
            task: json["Task"]?.stringValue ?? "",
            start: json["Start"]?.stringValue ?? "",
            finish: json["Finish"]?.stringValue ?? "",
            duration: json["Duration"]?.stringValue ?? ""
        )
    }
}

struct PlanItem: Identifiable {
    let id: Int
    let content: String
    let customPrompt: String
    let targetDate: String
    let status: String

    static func from(json: [String: JSONValue]) -> PlanItem {
        PlanItem(
            id: json["id"]?.intValue ?? -1,
            content: json["content"]?.stringValue ?? "",
            customPrompt: json["custom_prompt"]?.stringValue ?? "",
            targetDate: json["target_date"]?.stringValue ?? "",
            status: json["status"]?.stringValue ?? "active"
        )
    }
}

struct DailyLogItem: Identifiable {
    var id: String { date + timestamp }
    let date: String
    let summary: String
    let suggestions: String
    let timestamp: String

    static func from(json: [String: JSONValue]) -> DailyLogItem {
        DailyLogItem(
            date: json["date"]?.stringValue ?? "",
            summary: json["summary"]?.stringValue ?? "",
            suggestions: json["suggestions"]?.stringValue ?? "",
            timestamp: json["timestamp"]?.stringValue ?? ""
        )
    }
}

struct QuadrantItem: Identifiable {
    let id = UUID()
    let title: String
    let urgency: Int
    let importance: Int
    let quadrant: String
    let description: String

    static func from(json: [String: JSONValue]) -> QuadrantItem {
        QuadrantItem(
            title: json["title"]?.stringValue ?? "",
            urgency: json["urgency"]?.intValue ?? 5,
            importance: json["importance"]?.intValue ?? 5,
            quadrant: json["quadrant"]?.stringValue ?? "Q2",
            description: json["description"]?.stringValue ?? ""
        )
    }
}

struct LLMSettingsData {
    var mode: String = "api"
    var apiURL: String = ""
    var apiKey: String = ""
    var apiModel: String = "deepseek/deepseek-v3.2-251201"
    var ollamaHost: String = "http://127.0.0.1:11434"
    var ollamaModel: String = "qwen2.5:7b"

    static func from(json: [String: JSONValue]) -> LLMSettingsData {
        LLMSettingsData(
            mode: json["mode"]?.stringValue ?? "api",
            apiURL: json["api_url"]?.stringValue ?? "",
            apiKey: json["api_key"]?.stringValue ?? "",
            apiModel: json["api_model"]?.stringValue ?? "deepseek/deepseek-v3.2-251201",
            ollamaHost: json["ollama_host"]?.stringValue ?? "http://127.0.0.1:11434",
            ollamaModel: json["ollama_model"]?.stringValue ?? "qwen2.5:7b"
        )
    }

    func toPayload() -> [String: JSONValue] {
        [
            "mode": .string(mode),
            "api_url": .string(apiURL),
            "api_key": .string(apiKey),
            "api_model": .string(apiModel),
            "ollama_host": .string(ollamaHost),
            "ollama_model": .string(ollamaModel),
        ]
    }
}

enum JSONValue: Codable {
    case string(String)
    case number(Double)
    case int(Int)
    case bool(Bool)
    case array([JSONValue])
    case object([String: JSONValue])
    case null

    var stringValue: String? {
        switch self {
        case .string(let value): return value
        case .number(let value): return String(value)
        case .int(let value): return String(value)
        default: return nil
        }
    }

    var intValue: Int? {
        switch self {
        case .int(let value): return value
        case .number(let value): return Int(value)
        case .string(let value): return Int(value)
        default: return nil
        }
    }

    var boolValue: Bool? {
        switch self {
        case .bool(let value): return value
        case .string(let value):
            if value.lowercased() == "true" { return true }
            if value.lowercased() == "false" { return false }
            return nil
        case .int(let value): return value != 0
        default: return nil
        }
    }

    var objectValue: [String: JSONValue]? {
        if case .object(let object) = self { return object }
        return nil
    }

    var arrayValue: [JSONValue]? {
        if case .array(let array) = self { return array }
        return nil
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Int.self) {
            self = .int(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            throw DecodingError.typeMismatch(
                JSONValue.self,
                DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Unsupported JSON value")
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .int(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}
