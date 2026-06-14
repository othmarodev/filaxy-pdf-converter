// swift-tools-version: 5.9
import PackageDescription

// Filaxy PDF Converter — a Filaxy Labs product.
// Free, open source, offline. The native macOS shell is pure Swift with zero
// third-party dependencies; the high-fidelity conversion + verification engine
// is bundled separately (see /engine) and invoked as an offline helper.
let package = Package(
    name: "FilaxyPDFConverter",
    defaultLocalization: "es",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "FilaxyPDFConverter", targets: ["FilaxyPDFConverter"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "FilaxyPDFConverter",
            path: "Sources/FilaxyPDFConverter",
            // Resources/*.lproj and the bundled engine are copied into the
            // .app by build-app.sh, not through SPM's resource pipeline.
            exclude: ["Resources"]
        )
    ]
)
