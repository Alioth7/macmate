import SwiftUI
import AppKit
import Darwin

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        signal(SIGPIPE, SIG_IGN)
        NSApp.setActivationPolicy(.regular)

        // Force app activation so the window can receive mouse/keyboard events.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            NSApp.activate(ignoringOtherApps: true)
            NSApp.windows.forEach { window in
                window.level = .normal
                window.makeKeyAndOrderFront(nil)
            }
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            sender.windows.forEach { $0.makeKeyAndOrderFront(nil) }
        }
        sender.activate(ignoringOtherApps: true)
        return true
    }
}

@main
struct MacMateUIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var bridge = PythonBridgeService()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(bridge)
                .frame(minWidth: 1080, minHeight: 700)
                .onAppear {
                    bridge.startBridgeProcessIfNeeded()
                }
        }
        .windowStyle(.hiddenTitleBar)
    }
}
