import Foundation
import SwiftUI
import RoomProofCore

struct ProjectDocument: Codable, Identifiable {
    var schemaVersion: Int
    var id: String
    var title: String
    var revision: Int
    var room: RoomSpec
    var brief: DesignBrief
    var offers: [OfferSnapshot]
    var plan: LayoutPlan?
    var updatedAt: String
}

@MainActor final class ProjectStore: ObservableObject {
    @Published var project: ProjectDocument
    @Published var issues: [String] = []
    @Published var notice: String?
    @Published var sourcing = false
    @Published var analyzing = false
    @Published var progress: [String] = []
    @Published var analysis: AnalysisResponse?
    @Published var imageData: Data?
    @Published var proposed: LayoutPlan?
    @Published var baseURL = UserDefaults.standard.string(forKey: "roomproof.server") ?? ""
    @Published var token = PairingKeychain.read()
    @Published var health: HealthResponse?
    @Published var pendingSourcing: JobStart?
    private var sourceProjectID: String?
    private var sourceRequestID: String?
    private var sourceRevision: Int?
    private var sourcingTask: Task<Void, Never>?
    private var sourceGeneration = UUID()
    private let directory: URL

    init() {
        directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("RoomProof", isDirectory: true)
        let decoder = JSONDecoder()
        let fixture = Bundle.main.url(forResource: "project-example", withExtension: "json")!
        var initial = try! decoder.decode(ProjectDocument.self, from: Data(contentsOf: fixture))
        initial.id = UUID().uuidString
        initial.title = "My workspace"
        let last = UserDefaults.standard.string(forKey: "roomproof.last") ?? ""
        if let data = try? Data(contentsOf: directory.appendingPathComponent(last + ".json")),
           let saved = try? decoder.decode(ProjectDocument.self, from: data), saved.schemaVersion == 1 {
            initial = saved
        }
        project = initial
        revalidate()
    }

    var client: APIClient { APIClient(baseURL: baseURL, token: token) }
    var activePlan: LayoutPlan? { proposed ?? project.plan }
    var activeIssues: [String] {
        guard let plan = activePlan else { return issues }
        return Planner.validate(room: project.room, brief: project.brief, offers: project.offers, plan: plan)
    }
    var canExport: Bool { project.plan != nil && activeIssues.isEmpty && proposed == nil }
    var canResumeSourcing: Bool { sourceProjectID == project.id && sourceRequestID != nil }

    @discardableResult func save() -> Bool {
        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            project.updatedAt = ISO8601DateFormatter().string(from: Date())
            let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            var saved = project
            for i in saved.offers.indices where saved.offers[i].provenance == "live" { saved.offers[i].provenance = "saved" }
            if let plan = saved.plan { saved.plan = Planner.refreshMetadata(room: saved.room, brief: saved.brief, offers: saved.offers, plan: plan) ?? plan }
            try encoder.encode(saved).write(to: directory.appendingPathComponent(project.id + ".json"), options: [.atomic, .completeFileProtectionUnlessOpen])
            UserDefaults.standard.set(project.id, forKey: "roomproof.last")
            return true
        } catch { notice = "Could not save this project. Your current work is still open: \(error.localizedDescription)"; return false }
    }

    func savedProjects() -> [ProjectDocument] {
        ((try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension == "json" }
            .compactMap { url in try? JSONDecoder().decode(ProjectDocument.self, from: Data(contentsOf: url)) }
            .filter { $0.schemaVersion == 1 }.sorted { $0.updatedAt > $1.updatedAt }
    }

    func load(_ saved: ProjectDocument) {
        guard save() else { return }
        guard saved.id != project.id else { return }
        cancelRequests(); project = saved; proposed = nil; imageData = nil; analysis = nil; revalidate(); save()
    }

    func newProject() {
        guard save() else { return }
        cancelRequests()
        guard let url = Bundle.main.url(forResource: "project-example", withExtension: "json"),
              var fresh = try? JSONDecoder().decode(ProjectDocument.self, from: Data(contentsOf: url)) else { return }
        fresh.id = UUID().uuidString; fresh.title = "My workspace"
        project = fresh; proposed = nil; analysis = nil; imageData = nil; revalidate(); save()
    }

    func cancelRequests() { sourceGeneration = UUID(); sourcingTask?.cancel(); sourcingTask = nil; progress = sourcing ? ["Stopped waiting. Saved evidence remains available."] : []; sourcing = false }
    func changed() { project.revision += 1; proposed = nil; analysis = nil; revalidate(); save() }
    func revalidate() {
        if let plan = project.plan { issues = Planner.validate(room: project.room, brief: project.brief, offers: project.offers, plan: plan) }
        else { issues = [] }
    }
    func solve(keepUnresolvedPlan: Bool = false) {
        let result = Planner.solve(room: project.room, brief: project.brief, offers: project.offers, previous: project.plan)
        if result.plan != nil || !keepUnresolvedPlan { project.plan = result.plan }
        issues = result.issues; proposed = nil; project.revision += 1; save()
    }
    func previewMove(x: Int, z: Int, turn: Int? = nil) {
        guard var plan = activePlan else { return }
        plan.centerXMM = x; plan.centerZMM = z
        if let turn { plan.quarterTurns = (turn + 4) % 4 }
        proposed = plan
    }
    func finishMove() {
        guard let plan = proposed else { return }
        if activeIssues.isEmpty { project.plan = plan; proposed = nil; project.revision += 1; save() }
    }
    func repair() {
        guard let plan = activePlan else { return }
        let result = Planner.repair(room: project.room, brief: project.brief, offers: project.offers, proposed: plan)
        if let repaired = result.plan { project.plan = repaired; proposed = nil; project.revision += 1; save() }
        issues = result.issues
    }
    func configure() {
        baseURL = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        token = token.trimmingCharacters(in: .whitespacesAndNewlines)
        UserDefaults.standard.set(baseURL, forKey: "roomproof.server")
        if !PairingKeychain.write(token) { notice = "Could not save the pairing token securely." }
    }
    func checkConnection() async {
        configure()
        do { health = try await client.health(); notice = "Mac connected. Provider configuration is shown below; live calls are checked separately." }
        catch { health = nil; notice = error.localizedDescription }
    }
    func analyze() async {
        analyzing = true; defer { analyzing = false }
        let revision = project.revision, id = project.id
        do {
            let response = try await client.analyze(project: project, image: imageData)
            guard project.id == id, project.revision == revision, response.revision == revision, response.contractVersion == 1 else { return }
            analysis = response
        } catch { if project.id == id, project.revision == revision { notice = error.localizedDescription } }
    }
    func acceptAnalysis() {
        guard let result = analysis else { return }
        project.brief.preferClosedStorage = result.preferClosedStorage
        project.brief.style = result.style
        changed()
    }
    func source() {
        guard !sourcing else { return }
        let resume = canResumeSourcing ? pendingSourcing : nil
        if !canResumeSourcing {
            sourceRequestID = UUID().uuidString
            sourceProjectID = project.id
            sourceRevision = project.revision
            pendingSourcing = nil
        }
        let requestID = sourceRequestID!
        sourcing = true; progress = [resume == nil ? "Starting four product checks across two retailers…" : "Resuming the existing retailer check…"]
        for i in project.offers.indices where project.offers[i].provenance == "live" { project.offers[i].provenance = "saved" }
        if let plan = project.plan { project.plan = Planner.refreshMetadata(room: project.room, brief: project.brief, offers: project.offers, plan: plan) ?? plan }
        revalidate(); save()
        let revision = sourceRevision ?? project.revision, id = project.id, api = client
        let generation = UUID(); sourceGeneration = generation
        sourcingTask = Task {
            defer { if sourceGeneration == generation { sourcing = false } }
            do {
                let start: JobStart
                if let resume { start = resume } else { start = try await api.startSourcing(revision: revision, requestId: requestID) }
                try Task.checkCancellation()
                guard sourceGeneration == generation else { return }
                pendingSourcing = start; sourceProjectID = id
                for _ in 0..<400 {
                    try Task.checkCancellation()
                    let job = try await api.job(start.jobId)
                    try Task.checkCancellation()
                    guard sourceGeneration == generation else { return }
                    guard job.contractVersion == 1, job.jobId == start.jobId, job.requestId == start.requestId, job.revision == revision else { throw ClientError(message: "The retailer response did not match this request. Refresh to try again.") }
                    guard project.id == id else {
                        progress = ["Workspace changed. This check belongs to the previous workspace."]; return
                    }
                    progress = job.progress + job.errors
                    if ["done", "failed", "partial"].contains(job.state), !job.offers.isEmpty {
                        for offer in job.offers {
                            if let index = project.offers.firstIndex(where: { $0.id == offer.id }) { project.offers[index] = offer }
                        }
                        revalidate(); save()
                    }
                    if ["done", "partial", "failed"].contains(job.state) {
                        pendingSourcing = nil; sourceRequestID = nil
                        if job.state == "failed" { notice = "Retailer check failed. Saved offers retain their original evidence; review the source details." }
                        else {
                            solve(keepUnresolvedPlan: true)
                            if job.state == "partial" { notice = "Some products could not be refreshed. The plan labels every live or saved source; review the missing evidence before buying." }
                        }
                        return
                    }
                    try await Task.sleep(for: .seconds(1))
                }
                notice = "The retailer check is still running. Tap Resume check to keep waiting without starting another browser run."
            } catch is CancellationError { if sourceGeneration == generation { progress = ["Stopped waiting. Saved evidence is unchanged."] } }
              catch { if sourceGeneration == generation {
                  if (error as? ClientError)?.code == "unknown_job" { pendingSourcing = nil; sourceRequestID = nil }
                  notice = error.localizedDescription
              } }
        }
    }
}
