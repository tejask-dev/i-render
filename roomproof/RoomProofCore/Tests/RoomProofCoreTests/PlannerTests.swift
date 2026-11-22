import Foundation
import XCTest
import RoomProofCore

final class PlannerTests: XCTestCase {
    func testMetadataRefreshNeverRepairsInvalidPose() throws {
        let project = try confirmedExample()
        var plan = try XCTUnwrap(solve(project).plan)
        plan.centerXMM = 100
        plan.centerZMM = 100
        plan.provisional = false
        let refreshed = try XCTUnwrap(Planner.refreshMetadata(room: project.room, brief: project.brief, offers: project.offers, plan: plan))
        XCTAssertEqual(refreshed.centerXMM, 100)
        XCTAssertEqual(refreshed.centerZMM, 100)
        XCTAssertTrue(refreshed.provisional)
        XCTAssertFalse(validate(refreshed, in: project).isEmpty)
    }

    func testFixturesDecodeAndSampleRequiresConfirmation() throws {
        let catalog: [OfferSnapshot] = try fixture("catalog.json")
        var project: Example = try fixture("project-example.json")
        XCTAssertEqual(catalog, project.offers)
        XCTAssertEqual(Set(catalog.map(\.provenance)), ["saved"])
        XCTAssertNil(project.plan)
        XCTAssertEqual(project.room.source, "sample")
        let unconfirmed = solve(project)
        XCTAssertNil(unconfirmed.plan)
        XCTAssertEqual(unconfirmed.issues.first, "No checked layout found.")
        XCTAssertTrue(unconfirmed.issues.contains { $0.contains("floor is clear") })

        project.room.confirmed = true
        project.room.otherObjectsCleared = true
        let plan = try XCTUnwrap(solve(project).plan)
        XCTAssertTrue(plan.provisional)
        XCTAssertTrue(plan.reasons.contains { $0.contains("sample measurements") })
        let roundTrip = try JSONDecoder().decode(LayoutPlan.self, from: JSONEncoder().encode(plan))
        XCTAssertEqual(plan, roundTrip)
    }

    func testKnownFitStorageRankingAndOneCentBudgetFallback() throws {
        var project = try confirmedExample()
        project.brief.budgetCents = 24_800
        let plan = try XCTUnwrap(solve(project).plan)
        XCTAssertEqual(plan.deskOfferID, "ikea-desk")
        XCTAssertEqual(plan.chairOfferID, "ikea-chair")
        XCTAssertEqual(plan.subtotalCents, project.brief.budgetCents)
        XCTAssertTrue(plan.provisional)
        XCTAssertTrue(plan.reasons.contains { $0.contains("saved") })
        XCTAssertEqual(validate(plan, in: project), [])

        project.brief.budgetCents -= 1
        let replacement = try XCTUnwrap(solve(project, previous: plan).plan)
        XCTAssertEqual(replacement.deskOfferID, "jysk-desk")
        XCTAssertEqual(replacement.chairOfferID, "ikea-chair")
        XCTAssertEqual(replacement.subtotalCents, 17_899)
        XCTAssertEqual(replacement.centerXMM, plan.centerXMM)
        XCTAssertEqual(replacement.centerZMM, plan.centerZMM)
        XCTAssertEqual(replacement.quarterTurns, plan.quarterTurns)

        project.offers = project.offers.filter { $0.id == plan.deskOfferID || $0.id == plan.chairOfferID }
        XCTAssertNil(solve(project).plan)
        XCTAssertTrue(validate(plan, in: project).contains { $0.contains("exceed the CAD budget") })
    }

    func testPriorPoseDoesNotOutrankStoragePreference() throws {
        var project = try confirmedExample()
        project.brief.preferClosedStorage = false
        var plan = try XCTUnwrap(solve(project).plan)
        XCTAssertEqual(plan.deskOfferID, "jysk-desk")
        plan.centerXMM = 1_833
        plan.centerZMM = 391
        XCTAssertEqual(validate(plan, in: project), [])
        project.brief.preferClosedStorage = true
        let replacement = try XCTUnwrap(solve(project, previous: plan).plan)
        XCTAssertEqual(replacement.deskOfferID, "ikea-desk")
        XCTAssertEqual(replacement.centerXMM, plan.centerXMM)
        XCTAssertEqual(replacement.centerZMM, plan.centerZMM)
    }

    func testAllFootprintRotations() throws {
        let project = try confirmedExample()
        var plan = try XCTUnwrap(solve(project).plan)
        plan.chairOfferID = "jysk-chair"
        plan.centerXMM = 1600
        plan.centerZMM = 1400
        let expected = [
            [rect(1000, 1100, 1200, 600), rect(1315, 1700, 570, 460), rect(1315, 2160, 570, 600)],
            [rect(1300, 800, 600, 1200), rect(840, 1115, 460, 570), rect(240, 1115, 600, 570)],
            [rect(1000, 1100, 1200, 600), rect(1315, 640, 570, 460), rect(1315, 40, 570, 600)],
            [rect(1300, 800, 600, 1200), rect(1900, 1115, 460, 570), rect(2360, 1115, 600, 570)]
        ]
        for turn in 0..<4 {
            plan.quarterTurns = turn
            XCTAssertEqual(
                Planner.footprints(plan: plan, brief: project.brief, offers: project.offers),
                Dictionary(uniqueKeysWithValues: zip(["desk", "chair", "pullback"], expected[turn]))
            )
        }
    }

    func testDoorChecksPullbackAndAcceptsTouchingEdges() throws {
        var project = try confirmedExample()
        project.offers.removeAll { $0.id == "ikea-chair" }
        var plan = try XCTUnwrap(solve(project).plan)
        plan.centerXMM = 1800
        plan.centerZMM = 300
        plan.quarterTurns = 0
        project.room.doorReserve = rect(1500, 1100, 600, 300)
        XCTAssertEqual(validate(plan, in: project), ["The pullback overlaps the door reserve."])
        project.room.doorReserve.xMM = 2085
        XCTAssertEqual(validate(plan, in: project), [])
        project.brief.chairPullbackMM = 0
        project.room.doorReserve = rect(1500, 1060, 600, 300)
        XCTAssertEqual(validate(plan, in: project), [])
    }

    func testFirstOrientationUsesOffGridWallEndpoint() throws {
        var project = try confirmedExample()
        project.room.widthMM = 1271
        project.room.doorReserve = rect(0, 0, 71, 25)
        project.room.kept.widthMM = 200
        project.room.kept.centerXMM = 650
        let plan = try XCTUnwrap(solve(project).plan)
        XCTAssertEqual(plan.quarterTurns, 0)
        XCTAssertEqual(plan.centerXMM, 671)
        XCTAssertEqual(plan.centerZMM, 300)
        XCTAssertEqual(validate(plan, in: project), [])
    }

    func testRepairFindsNearestPoseAndKeepsSelectedPair() throws {
        var project = try confirmedExample()
        project.brief.preferClosedStorage = false
        var proposed = try XCTUnwrap(solve(project).plan)
        proposed.centerXMM = 1837
        proposed.centerZMM = 280
        project.brief.preferClosedStorage = true
        XCTAssertFalse(validate(proposed, in: project).isEmpty)
        let repair = Planner.repair(room: project.room, brief: project.brief, offers: project.offers, proposed: proposed)
        let plan = try XCTUnwrap(repair.plan)
        XCTAssertEqual(repair.issues, [])
        XCTAssertEqual(plan.deskOfferID, proposed.deskOfferID)
        XCTAssertEqual(plan.chairOfferID, proposed.chairOfferID)
        XCTAssertEqual(plan.centerXMM, 1837)
        XCTAssertEqual(plan.centerZMM, 300)
        XCTAssertEqual(plan.quarterTurns, 0)
        XCTAssertEqual(validate(plan, in: project), [])

        project.brief.budgetCents = plan.subtotalCents - 1
        XCTAssertNil(Planner.repair(
            room: project.room, brief: project.brief, offers: project.offers, proposed: proposed
        ).plan)
    }

    func testRepairCanFindUnsnappedInteriorClearance() throws {
        var project = try confirmedExample()
        project.room.widthMM = 2200
        var proposed = try XCTUnwrap(solve(project).plan)
        proposed.centerXMM = 1100
        proposed.centerZMM = 777
        proposed.quarterTurns = 0
        project.room.doorReserve = rect(1423, 1950, 100, 100)
        XCTAssertEqual(validate(proposed, in: project), ["The pullback overlaps the door reserve."])
        let repair = Planner.repair(room: project.room, brief: project.brief, offers: project.offers, proposed: proposed)
        let plan = try XCTUnwrap(repair.plan)
        XCTAssertEqual(plan.centerXMM, 1088)
        XCTAssertEqual(plan.centerZMM, 777)
        XCTAssertEqual(plan.quarterTurns, 0)
        XCTAssertEqual(validate(plan, in: project), [])
    }

    func testRejectsMissingConflictingUnavailableAndNonCADOffers() throws {
        var project = try confirmedExample()
        let valid = try XCTUnwrap(solve(project).plan)
        project.offers = project.offers.filter { $0.id == valid.deskOfferID || $0.id == valid.chairOfferID }
        project.offers[0].widthMM = nil
        project.offers[0].dimensionConflict = true
        project.offers[0].currency = "USD"
        project.offers[1].stock = "out_of_stock"
        let result = solve(project)
        XCTAssertNil(result.plan)
        for issue in ["missing valid dimensions", "conflicting dimensions", "CAD price", "out of stock"] {
            XCTAssertTrue(result.issues.contains { $0.contains(issue) })
        }
        XCTAssertEqual(Planner.footprints(plan: valid, brief: project.brief, offers: project.offers), [:])
    }

    func testRejectsUnsafeAndInconsistentRoomInputs() throws {
        var project = try confirmedExample()
        project.room.doorReserve.xMM = Int.max
        XCTAssertNil(solve(project).plan)
        project.room.doorReserve = rect(0, 0, 900, 1000)
        project.room.kept.centerXMM = 400
        project.room.kept.centerZMM = 200
        XCTAssertTrue(solve(project).issues.contains { $0.contains("retained item overlaps") })
        project.room.widthMM = Int.min
        XCTAssertNil(solve(project).plan)
    }

    func testPriceOverflowCannotProduceFit() throws {
        var project = try confirmedExample()
        project.brief.budgetCents = Int.max
        for index in project.offers.indices {
            project.offers[index].priceCents = Int.max
        }
        XCTAssertNil(solve(project).plan)
        XCTAssertTrue(solve(project).issues.contains { $0.contains("exceed the CAD budget") })
    }

    func testDeterministicAcrossOfferOrder() throws {
        var project = try confirmedExample()
        project.brief.preferClosedStorage = false
        for index in project.offers.indices {
            project.offers[index].priceCents = 100
        }
        let expected = solve(project)
        project.offers.reverse()
        XCTAssertEqual(solve(project), expected)
        XCTAssertEqual(expected.plan?.deskOfferID, "ikea-desk")
        XCTAssertEqual(expected.plan?.chairOfferID, "ikea-chair")
    }

    private struct Example: Decodable {
        var room: RoomSpec
        var brief: DesignBrief
        var offers: [OfferSnapshot]
        var plan: LayoutPlan?
    }

    private func fixture<T: Decodable>(_ filename: String) throws -> T {
        var repo = URL(fileURLWithPath: #filePath)
        for _ in 0..<5 { repo.deleteLastPathComponent() }
        let url = repo.appendingPathComponent("contracts/roomproof/\(filename)")
        return try JSONDecoder().decode(T.self, from: Data(contentsOf: url))
    }

    private func confirmedExample() throws -> Example {
        var project: Example = try fixture("project-example.json")
        project.room.source = "manual"
        project.room.confirmed = true
        project.room.otherObjectsCleared = true
        return project
    }

    private func solve(_ project: Example, previous: LayoutPlan? = nil) -> PlanResult {
        Planner.solve(room: project.room, brief: project.brief, offers: project.offers, previous: previous)
    }

    private func validate(_ plan: LayoutPlan, in project: Example) -> [String] {
        Planner.validate(room: project.room, brief: project.brief, offers: project.offers, plan: plan)
    }

    private func rect(_ x: Int, _ z: Int, _ width: Int, _ depth: Int) -> RectMM {
        RectMM(xMM: x, zMM: z, widthMM: width, depthMM: depth)
    }
}
