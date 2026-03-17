import SwiftUI

@available(macOS 13.0, *)
struct TestScroll: View {
    var body: some View {
        ScrollView {
            Text("Test")
        }
        .scrollIndicators(.visible)
    }
}
