import Foundation
import EventKit
import AppKit

enum NativeCalendarError: LocalizedError {
    case accessDenied

    var errorDescription: String? {
        switch self {
        case .accessDenied:
            return "Calendar access denied"
        }
    }
}

actor NativeCalendarService {
    static let shared = NativeCalendarService()

    private let store = EKEventStore()

    func fetchUpcomingEvents(days: Int = 14) async throws -> [CalendarEvent] {
        let accessGranted = try await ensureAccess()
        guard accessGranted else {
            throw NativeCalendarError.accessDenied
        }

        let start = Calendar.current.startOfDay(for: Date())
        guard let end = Calendar.current.date(byAdding: .day, value: days, to: start) else {
            return []
        }

        let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
        let events = store.events(matching: predicate).sorted { $0.startDate < $1.startDate }

        return events.compactMap { event in
            guard let startDate = event.startDate, let endDate = event.endDate else {
                return nil
            }
            let durationHours = max(0, endDate.timeIntervalSince(startDate) / 3600.0)

            return CalendarEvent(
                task: event.title?.isEmpty == false ? event.title! : "(No Title)",
                start: Self.formatter.string(from: startDate),
                finish: Self.formatter.string(from: endDate),
                duration: String(format: "%.1fh", durationHours)
            )
        }
    }

    private func ensureAccess() async throws -> Bool {
        let status = EKEventStore.authorizationStatus(for: .event)
        switch status {
        case .authorized, .fullAccess:
            return true
        case .notDetermined:
            return try await requestAccess()
        case .restricted, .denied, .writeOnly:
            return false
        @unknown default:
            return false
        }
    }

    private func requestAccess() async throws -> Bool {
        if #available(macOS 14.0, *) {
            return try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Bool, Error>) in
                store.requestFullAccessToEvents { granted, error in
                    if let error {
                        continuation.resume(throwing: error)
                    } else {
                        continuation.resume(returning: granted)
                    }
                }
            }
        }

        return try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Bool, Error>) in
            store.requestAccess(to: .event) { granted, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: granted)
                }
            }
        }
    }

    private static let formatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        return formatter
    }()

    nonisolated static func openCalendarPrivacySettings() {
        guard let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars") else {
            return
        }
        NSWorkspace.shared.open(url)
    }
}
