import SwiftUI
import PhotosUI
import RoomProofCore

private let ink = Color(red: 0.10, green: 0.18, blue: 0.20)
private let accent = Color(red: 0.03, green: 0.40, blue: 0.36)
func money(_ cents: Int) -> String { (Double(cents) / 100).formatted(.currency(code: "CAD")) }

struct ContentView: View {
    @EnvironmentObject var store: ProjectStore
    @State private var tab = 0
    @State private var settings = false
    @State private var library = false
    @State private var confirmNew = false
    var body: some View {
        NavigationStack {
            TabView(selection: $tab) {
                RoomForm().tabItem { Label("Room", systemImage: "square.dashed") }.tag(0)
                BriefView().tabItem { Label("Brief", systemImage: "sparkles") }.tag(1)
                PlanView().tabItem { Label("Plan", systemImage: "cube.transparent") }.tag(2)
            }
            .navigationTitle("RoomProof")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button { library = true } label: { Image(systemName: "folder") }.accessibilityLabel("Saved projects") }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button { confirmNew = true } label: { Image(systemName: "plus") }.accessibilityLabel("New project")
                    Button { settings = true } label: { Image(systemName: "network") }.accessibilityLabel("Connect to Mac")
                }
            }
            .sheet(isPresented: $settings) { ConnectionView() }
            .sheet(isPresented: $library) {
                NavigationStack {
                    List(store.savedProjects()) { doc in
                        Button { store.load(doc); tab = doc.plan == nil ? 0 : 2; library = false } label: {
                            VStack(alignment: .leading) { Text(doc.title).font(.headline); Text(doc.updatedAt).font(.caption).foregroundStyle(.secondary) }
                        }
                    }.navigationTitle("Saved workspaces")
                        .toolbar { Button("Done") { library = false } }
                }
            }
            .confirmationDialog("Start a new workspace? Your current project will be saved.", isPresented: $confirmNew) {
                Button("New workspace") { store.newProject(); tab = 0 }
            }
            .alert("RoomProof", isPresented: Binding(get: { store.notice != nil }, set: { if !$0 { store.notice = nil } })) {
                Button("OK") { store.notice = nil }
            } message: { Text(store.notice ?? "") }
            .onAppear { if store.project.plan != nil { tab = 2 } }
        }
    }
}

struct RoomForm: View {
    @EnvironmentObject var store: ProjectStore
    private func measurement(_ path: WritableKeyPath<RoomSpec, Int>) -> Binding<Int> {
        Binding(get: { store.project.room[keyPath: path] }, set: { value in
            store.project.room[keyPath: path] = value
            store.project.room.confirmed = false
            store.changed()
        })
    }
    var body: some View {
        Form {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Make room for\nbetter work.").font(.system(size: 32, weight: .semibold, design: .rounded)).foregroundStyle(ink)
                    Text("Start with measurements. Keep what matters. Find a workstation that fits.").foregroundStyle(.secondary)
                }.padding(.vertical, 10)
                TextField("Workspace name", text: $store.project.title)
                    .onChange(of: store.project.title) { _, _ in store.changed() }
            }
            Section("Your room · centimetres") {
                CMField("Width", value: measurement(\.widthMM))
                CMField("Depth", value: measurement(\.depthMM))
                CMField("Height", value: measurement(\.heightMM))
                Text("On iPhone 16, enter measured dimensions. A photograph cannot establish precise room size.").font(.caption).foregroundStyle(.secondary)
            }
            Section("Doorway clearance · centimetres") {
                CMField("From left wall", value: measurement(\.doorReserve.xMM))
                CMField("From bottom wall", value: measurement(\.doorReserve.zMM))
                CMField("Reserved width", value: measurement(\.doorReserve.widthMM))
                CMField("Reserved depth", value: measurement(\.doorReserve.depthMM))
                Text("Reserve a rectangle for the doorway and its swing. Coordinates match the top-down plan.").font(.caption).foregroundStyle(.secondary)
            }
            Section("One piece to keep · centimetres") {
                TextField("Item name", text: $store.project.room.kept.label)
                    .onChange(of: store.project.room.kept.label) { _, _ in store.changed() }
                CMField("Width", value: measurement(\.kept.widthMM))
                CMField("Depth", value: measurement(\.kept.depthMM))
                CMField("Height", value: measurement(\.kept.heightMM))
                CMField("Centre from left", value: measurement(\.kept.centerXMM))
                CMField("Centre from bottom", value: measurement(\.kept.centerZMM))
                Picker("Rotation", selection: measurement(\.kept.quarterTurns)) {
                    ForEach(0..<4) { Text("\($0 * 90)°").tag($0) }
                }
            }
            Section {
                Toggle("I checked these measurements", isOn: $store.project.room.confirmed)
                Toggle("Other objects will be removed or are outside this planning area", isOn: $store.project.room.otherObjectsCleared)
                Button("Confirm room and save") {
                    store.project.room.source = "manual"
                    store.changed(); store.solve()
                    if store.project.plan != nil { store.notice = "Room saved. Open Brief to describe your workspace, then Plan to explore the layout." }
                    else if !store.issues.isEmpty { store.notice = store.issues.joined(separator: "\n") }
                }.disabled(!store.project.room.confirmed || !store.project.room.otherObjectsCleared)
            } footer: { Text("Checks cover the modeled floor footprints and reserved spaces. They do not establish delivery access or ergonomic suitability.") }
        }
        .scrollDismissesKeyboard(.interactively)
    }
}

struct CMField: View {
    var label: String
    @Binding var value: Int
    init(_ label: String, value: Binding<Int>) { self.label = label; _value = value }
    var body: some View {
        HStack {
            Text(label)
            Spacer()
            TextField("cm", value: Binding(get: { Double(value) / 10 }, set: { if $0.isFinite { value = Int(min(100_000, max(-100_000, $0 * 10)).rounded()) } }), format: .number.precision(.fractionLength(0...1)))
                .keyboardType(.decimalPad).multilineTextAlignment(.trailing).frame(maxWidth: 110)
                .accessibilityLabel(label + " in centimetres")
            Text("cm").foregroundStyle(.secondary)
        }
    }
}

struct BriefView: View {
    @EnvironmentObject var store: ProjectStore
    @State private var photo: PhotosPickerItem?
    @State private var camera = false
    var body: some View {
        Form {
            Section {
                Text("A workspace for you.").font(.title2.bold()).foregroundStyle(ink)
                Text("Tell us what matters. You make the final choices; Gemini helps interpret the brief.").foregroundStyle(.secondary)
                TextField("A calm desk setup with closed storage…", text: $store.project.brief.notes, axis: .vertical).lineLimit(3...6)
                    .onChange(of: store.project.brief.notes) { _, new in if new.count > 4000 { store.project.brief.notes = String(new.prefix(4000)) }; store.changed() }
                HStack {
                    PhotosPicker(selection: $photo, matching: .images) { Label(store.imageData == nil ? "Add room photo" : "Replace photo", systemImage: "photo") }
                    Spacer()
                    if UIImagePickerController.isSourceTypeAvailable(.camera) {
                        Button { camera = true } label: { Image(systemName: "camera") }.accessibilityLabel("Photograph workspace")
                    }
                }
                if store.imageData != nil { Button("Remove photo") { photo = nil; store.imageData = nil; store.changed() } }
                Text("Optional photo: use a staged room without people or private documents. It informs style, not measurements.").font(.caption).foregroundStyle(.secondary)
                Button {
                    Task { await store.analyze() }
                } label: { HStack { if store.analyzing { ProgressView() }; Text(store.analyzing ? "Interpreting brief…" : "Interpret with Gemini") } }
                    .disabled(store.analyzing || store.project.brief.notes.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            if let result = store.analysis {
                Section("Gemini suggestion · review first") {
                    Text(result.summary)
                    Text("Style: \(result.style)")
                    Text(result.preferClosedStorage ? "Prefer closed storage" : "Storage is optional")
                    ForEach(result.questions, id: \.self) { Text($0).foregroundStyle(.orange) }
                    Button("Apply these preferences") { store.acceptAnalysis() }
                    Text("\(result.provider) · \(result.model)").font(.caption).foregroundStyle(.secondary)
                }
            }
            Section {
                HStack {
                    Text("Merchandise budget")
                    Spacer()
                    TextField("CAD", value: Binding(get: { Double(store.project.brief.budgetCents) / 100 }, set: { if $0.isFinite { store.project.brief.budgetCents = Int(min(10_000_000, max(0, $0 * 100)).rounded()); store.changed() } }), format: .number.precision(.fractionLength(0...2)))
                        .keyboardType(.decimalPad).multilineTextAlignment(.trailing).frame(maxWidth: 100)
                    Text("CAD").foregroundStyle(.secondary)
                }
                Toggle("Prefer closed storage", isOn: $store.project.brief.preferClosedStorage).onChange(of: store.project.brief.preferClosedStorage) { _, _ in store.changed() }
                TextField("Style", text: $store.project.brief.style).onChange(of: store.project.brief.style) { _, _ in store.changed() }
                CMField("Chair pullback", value: $store.project.brief.chairPullbackMM)
                    .onChange(of: store.project.brief.chairPullbackMM) { _, _ in store.changed() }
                Button("Build my plan") { store.changed(); store.solve(); if store.project.plan == nil { store.notice = store.issues.joined(separator: "\n") } }
            } header: { Text("Your confirmed choices") } footer: { Text("Tax and delivery are not included. You can complete the brief manually if Gemini is unavailable.") }
        }
        .scrollDismissesKeyboard(.interactively)
        .sheet(isPresented: $camera) { CameraCapture { data in
            guard let data else { store.notice = "Could not read that photo. Try taking it again."; return }
            guard data.count <= 10 * 1024 * 1024 else { store.notice = "Choose an image smaller than 10 MB."; return }
            photo = nil; store.imageData = data; store.changed()
        } }
        .onChange(of: photo) { _, item in
            guard let item else { return }
            let projectID = store.project.id
            Task {
                let data = try? await item.loadTransferable(type: Data.self)
                guard projectID == store.project.id, item == photo else { return }
                if let data, data.count <= 10 * 1024 * 1024 { store.imageData = data; store.changed() }
                else { store.notice = "Choose an image smaller than 10 MB." }
            }
        }
    }
}

struct PlanView: View {
    @EnvironmentObject var store: ProjectStore
    @State private var topDown = false
    @State private var pdf: URL?
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(store.project.title).font(.title2.bold()).foregroundStyle(ink)
                        Text("\(store.project.room.widthMM / 10) × \(store.project.room.depthMM / 10) cm · \(store.project.room.source == "sample" ? "Example room" : "User measurements")").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button { topDown.toggle() } label: { Image(systemName: topDown ? "cube" : "square.dashed") }.accessibilityLabel(topDown ? "Show 3D" : "Show editable floor plan")
                }
                Group {
                    if topDown { FloorPlanView().environmentObject(store) }
                    else { RoomSceneView(room: store.project.room, brief: store.project.brief, offers: store.project.offers, plan: store.activePlan, invalid: !store.activeIssues.isEmpty) }
                }.frame(height: 320).background(Color(red: 0.93, green: 0.95, blue: 0.94)).clipShape(RoundedRectangle(cornerRadius: 24))
                HStack {
                    Text("Budget")
                    Slider(value: Binding(get: { Double(store.project.brief.budgetCents) / 100 }, set: { store.project.brief.budgetCents = Int($0.rounded()) * 100; store.project.revision += 1; store.solve() }), in: 100...600, step: 5)
                    Text(money(store.project.brief.budgetCents)).font(.subheadline.monospacedDigit())
                }
                if let plan = store.activePlan {
                    HStack {
                        VStack(alignment: .leading) {
                            Text(money(plan.subtotalCents)).font(.system(size: 30, weight: .semibold, design: .rounded))
                            Text("Merchandise · tax & delivery excluded").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text(!store.activeIssues.isEmpty ? "Needs repair" : plan.provisional ? "Provisional" : "Fit checked").font(.caption.bold()).padding(9).background((plan.provisional || !store.activeIssues.isEmpty ? Color.orange : accent).opacity(0.12)).clipShape(Capsule())
                    }
                    HStack(spacing: 12) {
                        moveButton("Left", icon: "arrow.left", dx: -100, dz: 0)
                        moveButton("Up", icon: "arrow.up", dx: 0, dz: 100)
                        moveButton("Down", icon: "arrow.down", dx: 0, dz: -100)
                        moveButton("Right", icon: "arrow.right", dx: 100, dz: 0)
                        Button { store.previewMove(x: plan.centerXMM, z: plan.centerZMM, turn: plan.quarterTurns + 1); store.finishMove() } label: { Image(systemName: "rotate.right") }.frame(minWidth: 44, minHeight: 44).accessibilityLabel("Rotate workstation 90 degrees")
                    }.buttonStyle(.bordered)
                    Text(topDown ? "Drag the workstation on the plan, or move it in 10 cm steps." : "Use the arrows or switch to the floor plan to drag. Furniture appearance is approximate.").font(.caption).foregroundStyle(.secondary)
                    if !store.activeIssues.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Label("This placement needs a change", systemImage: "exclamationmark.triangle").font(.headline)
                            ForEach(store.activeIssues, id: \.self) { Text($0).font(.subheadline) }
                            HStack { Button("Fix position") { store.repair() }; if store.proposed != nil { Button("Undo move") { store.proposed = nil } } }
                        }.padding().frame(maxWidth: .infinity, alignment: .leading).background(Color.orange.opacity(0.10)).clipShape(RoundedRectangle(cornerRadius: 16))
                    }
                    ForEach(plan.reasons, id: \.self) { Text($0).font(.subheadline).foregroundStyle(.secondary) }
                } else {
                    Text("Your next workspace starts here.").font(.title3.bold())
                    ForEach(store.issues, id: \.self) { Text($0).foregroundStyle(.orange) }
                    Button("Find a layout") { store.solve() }.buttonStyle(.borderedProminent)
                    Text("Confirm the room and brief first. Saved retailer facts support a provisional preview while live evidence is checked.").font(.caption).foregroundStyle(.secondary)
                }
                Divider()
                HStack {
                    Text("Products & evidence").font(.title3.bold())
                    Spacer()
                    Button(store.sourcing ? "Stop waiting" : store.canResumeSourcing ? "Resume check" : "Refresh") { if store.sourcing { store.cancelRequests() } else { store.source() } }
                }
                if store.sourcing { ProgressView("Checking retailer pages…").font(.caption) }
                ForEach(store.progress, id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) }
                ForEach(store.project.offers, id: \.id) { offer in OfferCard(offer: offer, selected: store.project.plan.map { [$0.deskOfferID, $0.chairOfferID].contains(offer.id) } ?? false) }
                Button {
                    guard let plan = store.project.plan else { return }
                    do { pdf = try FitSheet.export(title: store.project.title, room: store.project.room, brief: store.project.brief, offers: store.project.offers, plan: plan) }
                    catch { store.notice = "Could not create Fit Sheet: \(error.localizedDescription)" }
                } label: { Label("Create Purchase Fit Sheet", systemImage: "doc.richtext").frame(maxWidth: .infinity) }.buttonStyle(.borderedProminent).controlSize(.large).disabled(!store.canExport)
                if let pdf, store.canExport { ShareLink(item: pdf) { Label("Share PDF", systemImage: "square.and.arrow.up").frame(maxWidth: .infinity) }.buttonStyle(.bordered) }
                Text("Fit checks cover your confirmed floor footprints and reserves. Stock, prices and conditions are snapshots, not purchase guarantees.").font(.caption).foregroundStyle(.secondary)
            }.padding(20)
        }
        .onChange(of: store.project.id) { _, _ in pdf = nil }
        .onChange(of: store.project.revision) { _, _ in pdf = nil }
        .onChange(of: store.project.offers) { _, _ in pdf = nil }
    }
    private func moveButton(_ title: String, icon: String, dx: Int, dz: Int) -> some View {
        Button { if let p = store.activePlan { store.previewMove(x: p.centerXMM + dx, z: p.centerZMM + dz); store.finishMove() } } label: { Image(systemName: icon) }.frame(minWidth: 44, minHeight: 44).accessibilityLabel("Move workstation " + title + " 10 centimetres")
    }
}

struct OfferCard: View {
    var offer: OfferSnapshot
    var selected: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: offer.category == "desk" ? "table.furniture" : "chair.lounge").font(.title2).foregroundStyle(accent).frame(width: 38)
                VStack(alignment: .leading) { Text(offer.name).font(.headline); Text(offer.retailer + " · " + offer.sku).font(.caption).foregroundStyle(.secondary) }
                Spacer()
                Text(offer.priceCents.map(money) ?? "Unpriced").font(.subheadline.bold())
            }
            Text("\(offer.widthMM.map { String(Double($0) / 10) } ?? "?") × \(offer.depthMM.map { String(Double($0) / 10) } ?? "?") cm footprint · \(selected ? "In this plan" : "Alternative")").font(.caption)
            Text("\(offer.provenance.capitalized) evidence · \(offer.stock.replacingOccurrences(of: "_", with: " "))").font(.caption.bold()).foregroundStyle(offer.stock == "in_stock" ? accent : .orange)
            Text(offer.checkedAt.isEmpty ? "Capture time not retained — refresh before purchase" : "Checked \(offer.checkedAt)").font(.caption).foregroundStyle(.secondary)
            DisclosureGroup("Source details") {
                VStack(alignment: .leading, spacing: 6) {
                    Text(offer.stockScope); Text(offer.evidenceQuote); Text(offer.priceConditions)
                    if offer.dimensionConflict { Text("Conflicting dimensions — excluded from fit checks").foregroundStyle(.orange) }
                    if let url = URL(string: offer.url), url.scheme == "https" { Link("Open retailer product", destination: url) }
                }.font(.caption).frame(maxWidth: .infinity, alignment: .leading)
            }.font(.caption)
        }.padding().background(selected ? accent.opacity(0.06) : Color(.secondarySystemGroupedBackground)).overlay(RoundedRectangle(cornerRadius: 16).stroke(selected ? accent.opacity(0.25) : Color.gray.opacity(0.15))).clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

struct ConnectionView: View {
    @EnvironmentObject var store: ProjectStore
    @Environment(\.dismiss) var dismiss
    @State private var checking = false
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("http://your-mac.local:8767", text: $store.baseURL).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("Pairing token", text: $store.token).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button(checking ? "Connecting…" : "Save and check connection") {
                        checking = true; Task { await store.checkConnection(); checking = false }
                    }.disabled(checking)
                } header: { Text("Your paired Mac") } footer: { Text("Use your private hotspot. Provider API keys stay on the Mac; this phone stores only the pairing token in Keychain.") }
                if let health = store.health {
                    Section("Backend configuration") {
                        Label("Contract \(health.contractVersion)", systemImage: "checkmark.circle")
                        Text("Gemini: \(health.geminiConfigured ? "configured" : "key missing")")
                        Text("TinyFish: \(health.tinyfishConfigured ? "configured" : "key missing")")
                        Text("Configured does not mean a live request has passed.").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }.navigationTitle("Connect to Mac").navigationBarTitleDisplayMode(.inline).toolbar { Button("Done") { store.configure(); dismiss() } }
        }
    }
}

struct CameraCapture: UIViewControllerRepresentable {
    var onCapture: (Data?) -> Void
    @Environment(\.dismiss) var dismiss
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let controller = UIImagePickerController(); controller.sourceType = .camera; controller.delegate = context.coordinator; return controller
    }
    func updateUIViewController(_ controller: UIImagePickerController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }
    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        var parent: CameraCapture
        init(parent: CameraCapture) { self.parent = parent }
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { parent.dismiss() }
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            parent.onCapture((info[.originalImage] as? UIImage)?.jpegData(compressionQuality: 0.75)); parent.dismiss()
        }
    }
}
