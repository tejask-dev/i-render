import SwiftUI

@main
struct RoomProofApp: App {
    @StateObject private var store = ProjectStore()
    @Environment(\.scenePhase) private var phase
    var body: some Scene {
        WindowGroup {
            ContentView().environmentObject(store)
                .tint(Color(red: 0.03, green: 0.40, blue: 0.36))
                .onChange(of: phase) { _, value in
                    if value != .active { store.save() }
                }
        }
    }
}
