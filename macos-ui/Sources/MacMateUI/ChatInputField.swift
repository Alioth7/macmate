import SwiftUI

/// Thin wrapper around TextField that calls onSubmit on Enter.
/// Keeps the original single-line look.
struct ChatInputField: View {
    @Binding var text: String
    var isDisabled: Bool
    var placeholder: String = L10n.s(.chatPlaceholder)
    var onSubmit: () -> Void

    var body: some View {
        TextField(placeholder, text: $text)
            .textFieldStyle(.roundedBorder)
            .font(.custom("Avenir Next", size: 15))
            .disabled(isDisabled)
            .onSubmit {
                onSubmit()
            }
    }
}
