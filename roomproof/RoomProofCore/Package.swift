// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "RoomProofCore",
    platforms: [.iOS(.v18), .macOS(.v14)],
    products: [.library(name: "RoomProofCore", targets: ["RoomProofCore"])],
    targets: [
        .target(name: "RoomProofCore"),
        .testTarget(name: "RoomProofCoreTests", dependencies: ["RoomProofCore"])
    ],
    swiftLanguageModes: [.v5]
)
