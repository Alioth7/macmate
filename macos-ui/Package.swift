// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MacMateUI",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "MacMateUI", targets: ["MacMateUI"])
    ],
    targets: [
        .executableTarget(
            name: "MacMateUI",
            path: "Sources/MacMateUI"
        )
    ]
)
