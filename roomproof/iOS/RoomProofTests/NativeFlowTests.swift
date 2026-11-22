import XCTest
import PDFKit
import RoomProofCore
@testable import RoomProof

@MainActor final class NativeFlowTests: XCTestCase {
    private func example() -> ProjectStore {
        let store = ProjectStore()
        store.newProject()
        store.project.title = "Native integration fixture"
        store.project.room.confirmed = true
        store.project.room.otherObjectsCleared = true
        store.project.room.source = "sample"
        store.solve()
        return store
    }

    func testBundledResourcesAndBudgetRepair() throws {
        let store = example()
        let original = try XCTUnwrap(store.project.plan)
        XCTAssertEqual(original.subtotalCents, 24800)
        XCTAssertTrue(original.provisional)
        store.project.brief.budgetCents = 20000
        store.solve()
        let cheaper = try XCTUnwrap(store.project.plan)
        XCTAssertEqual(cheaper.subtotalCents, 17899)
        XCTAssertNotEqual(original.deskOfferID, cheaper.deskOfferID)
        XCTAssertEqual(store.activeIssues, [])
        store.project.brief.budgetCents = 100
        store.solve()
        XCTAssertNil(store.project.plan)
        XCTAssertFalse(store.issues.isEmpty)
    }

    func testInvalidMoveDoesNotOverwriteSavedPlanAndRepairWorks() throws {
        let store = example()
        let original = try XCTUnwrap(store.project.plan)
        store.previewMove(x: 100, z: 100)
        store.finishMove()
        XCTAssertEqual(store.project.plan, original)
        XCTAssertFalse(store.activeIssues.isEmpty)
        XCTAssertFalse(store.canExport)
        store.repair()
        XCTAssertNil(store.proposed)
        XCTAssertEqual(store.activeIssues, [])
        XCTAssertTrue(store.canExport)
    }

    func testSaveReopenKeepsEvidenceAndMeasurements() throws {
        let store = example()
        let expected = store.project
        store.save()
        let reopened = ProjectStore()
        XCTAssertEqual(reopened.project.id, expected.id)
        XCTAssertEqual(reopened.project.room, expected.room)
        XCTAssertEqual(reopened.project.plan, expected.plan)
        XCTAssertEqual(reopened.project.offers.map(\.checkedAt), expected.offers.map(\.checkedAt))
    }

    func testFitSheetContainsSelectedEvidenceAndQualifications() throws {
        let store = example()
        let plan = try XCTUnwrap(store.project.plan)
        let url = try FitSheet.export(title: store.project.title, room: store.project.room, brief: store.project.brief, offers: store.project.offers, plan: plan)
        let pdf = try XCTUnwrap(PDFDocument(url: url))
        XCTAssertGreaterThanOrEqual(pdf.pageCount, 2)
        let text = try XCTUnwrap(pdf.string)
        XCTAssertTrue(text.contains("LAGKAPTEN"))
        XCTAssertTrue(text.contains("RENBERGET"))
        XCTAssertTrue(text.lowercased().contains("provisional"))
        XCTAssertTrue(text.lowercased().contains("delivery"))
        XCTAssertTrue(text.contains("ikea.com"))
        XCTAssertFalse(text.contains("JYSK"))
        print("ROOMPROOF_PDF_ARTIFACT \(url.path)")
    }

    func testPrivateMacAddressesExcludePublicHTTP() {
        for host in ["localhost", "mac.local", "127.0.0.1", "192.168.1.9", "172.20.10.2", "10.0.0.2"] { XCTAssertTrue(APIClient.isPrivateHost(host)) }
        for host in ["example.com", "192.168.1.9.example.com", "8.8.8.8", "172.32.0.1", "192.168.999.1"] { XCTAssertFalse(APIClient.isPrivateHost(host)) }
    }

    func testReopenedLiveEvidenceBecomesSavedAndProvisional() throws {
        let store = example()
        store.project.room.source = "manual"
        for i in store.project.offers.indices {
            store.project.offers[i].provenance = "live"
            store.project.offers[i].stock = "in_stock"
            store.project.offers[i].checkedAt = "2026-11-22T01:00:00Z"
        }
        store.solve()
        XCTAssertFalse(try XCTUnwrap(store.project.plan).provisional)
        let reopened = ProjectStore()
        XCTAssertTrue(reopened.project.offers.allSatisfy { $0.provenance == "saved" })
        XCTAssertTrue(try XCTUnwrap(reopened.project.plan).provisional)
    }

    func testIncompleteRefreshKeepsPoseButBlocksExport() throws {
        let store = example()
        let previous = try XCTUnwrap(store.project.plan)
        for i in store.project.offers.indices { store.project.offers[i].widthMM = nil }
        store.solve(keepUnresolvedPlan: true)
        XCTAssertEqual(store.project.plan, previous)
        XCTAssertFalse(store.activeIssues.isEmpty)
        XCTAssertFalse(store.canExport)
    }

    func testEditingAndStoppingRetainsSourcingForSameWorkspace() {
        let store = example()
        store.baseURL = ""
        store.source()
        store.project.title = "Changed while checking"
        store.changed()
        store.cancelRequests()
        XCTAssertTrue(store.canResumeSourcing)
        store.newProject()
        XCTAssertFalse(store.canResumeSourcing)
    }
}
