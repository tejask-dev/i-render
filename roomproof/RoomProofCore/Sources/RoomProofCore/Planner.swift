public enum Planner {
    public static func refreshMetadata(room: RoomSpec, brief: DesignBrief, offers: [OfferSnapshot], plan: LayoutPlan) -> LayoutPlan? {
        let (pair, _) = selectedPair(room: room, brief: brief, offers: offers, plan: plan)
        return pair?.plan(at: Pose(plan))
    }

    public static func solve(
        room: RoomSpec, brief: DesignBrief, offers: [OfferSnapshot], previous: LayoutPlan? = nil
    ) -> PlanResult {
        let (site, inputIssues) = checkedSite(room: room, brief: brief)
        guard let site else { return noFit(inputIssues) }

        let desks = offers.filter { $0.category == "desk" }
        let chairs = offers.filter { $0.category == "chair" }
        guard !desks.isEmpty, !chairs.isEmpty else {
            return noFit(["A desk and a chair are required."])
        }

        let counts = Dictionary(grouping: offers, by: \.id).mapValues(\.count)
        var pairs: [Pair] = []
        var issues: [String] = []
        for desk in desks.sorted(by: { $0.id < $1.id }) {
            for chair in chairs.sorted(by: { $0.id < $1.id }) {
                guard counts[desk.id] == 1, counts[chair.id] == 1 else {
                    issues.append("Each offer must have a unique ID.")
                    continue
                }
                let (pair, pairIssues) = checkedPair(desk: desk, chair: chair, room: room, brief: brief)
                issues += pairIssues
                if let pair { pairs.append(pair) }
            }
        }

        pairs.sort {
            $0.rank(preferClosedStorage: brief.preferClosedStorage)
                < $1.rank(preferClosedStorage: brief.preferClosedStorage)
        }
        let target = previous.map(Pose.init)
        for pair in pairs {
            if let pose = placement(site: site, pair: pair, pullback: brief.chairPullbackMM, target: target, wallsOnly: true) {
                return PlanResult(plan: pair.plan(at: pose), issues: [])
            }
        }
        if !pairs.isEmpty { issues.append("The furniture and chair clearance could not fit around the room obstacles.") }
        return noFit(issues)
    }

    public static func validate(
        room: RoomSpec, brief: DesignBrief, offers: [OfferSnapshot], plan: LayoutPlan
    ) -> [String] {
        let (site, inputIssues) = checkedSite(room: room, brief: brief)
        guard let site else { return inputIssues }
        let (pair, pairIssues) = selectedPair(room: room, brief: brief, offers: offers, plan: plan)
        guard let pair else { return pairIssues }
        let pose = Pose(plan)
        guard let layout = pair.layout(turn: pose.turn, pullback: brief.chairPullbackMM) else {
            return ["The layout rotation must be a quarter-turn from 0 through 3."]
        }

        var issues = layout.issues(at: pose, in: site)
        if plan.subtotalCents != pair.subtotal { issues.append("The layout subtotal has changed.") }
        if plan.provisional != !pair.reasons.isEmpty { issues.append("The layout confidence label must be refreshed.") }
        return issues
    }

    public static func repair(
        room: RoomSpec, brief: DesignBrief, offers: [OfferSnapshot], proposed: LayoutPlan
    ) -> PlanResult {
        let (site, inputIssues) = checkedSite(room: room, brief: brief)
        guard let site else { return noFit(inputIssues) }
        let (pair, pairIssues) = selectedPair(room: room, brief: brief, offers: offers, plan: proposed)
        guard let pair else { return noFit(pairIssues) }
        guard let pose = placement(
            site: site, pair: pair, pullback: brief.chairPullbackMM, target: Pose(proposed), wallsOnly: false
        ) else {
            return noFit(["The selected furniture and chair clearance could not fit around the room obstacles."])
        }
        return PlanResult(plan: pair.plan(at: pose), issues: [])
    }

    public static func footprints(
        plan: LayoutPlan, brief: DesignBrief, offers: [OfferSnapshot]
    ) -> [String: RectMM] {
        guard let (deskOffer, chairOffer) = selectedOffers(for: plan, from: offers),
              let desk = Dimensions(deskOffer), let chair = Dimensions(chairOffer),
              !deskOffer.dimensionConflict, !chairOffer.dimensionConflict,
              (0...maximumSpan).contains(brief.chairPullbackMM),
              signedSpan.contains(plan.centerXMM), signedSpan.contains(plan.centerZMM),
              let layout = Layout(desk: desk, chair: chair, turn: plan.quarterTurns, pullback: brief.chairPullbackMM) else {
            return [:]
        }
        return Dictionary(uniqueKeysWithValues: layout.parts.map { part in
            (part.name, part.rect.translated(x: plan.centerXMM, z: plan.centerZMM))
        })
    }

    private static func placement(
        site: Site, pair: Pair, pullback: Int, target: Pose?, wallsOnly: Bool
    ) -> Pose? {
        if let target, let layout = pair.layout(turn: target.turn, pullback: pullback),
           layout.issues(at: target, in: site).isEmpty {
            return target
        }

        var best: Pose?
        for turn in 0..<4 {
            guard let layout = pair.layout(turn: turn, pullback: pullback),
                  let (xRange, zRange) = layout.ranges(in: site) else { continue }

            let xValues: [Int]
            let zValues: [Int]
            if wallsOnly {
                xValues = turn % 2 == 0 ? wallSteps(xRange) : [turn == 1 ? xRange.upperBound : xRange.lowerBound]
                zValues = turn % 2 == 1 ? wallSteps(zRange) : [turn == 0 ? zRange.lowerBound : zRange.upperBound]
            } else if let target {
                (xValues, zValues) = layout.nearestCandidates(to: target, in: site, xRange: xRange, zRange: zRange)
            } else {
                continue
            }

            for x in xValues {
                for z in zValues {
                    let pose = Pose(x: x, z: z, turn: turn)
                    if let best, best.rank(relativeTo: target) <= pose.rank(relativeTo: target) { continue }
                    if layout.issues(at: pose, in: site).isEmpty { best = pose }
                }
            }
        }
        return best
    }

    private static func wallSteps(_ range: ClosedRange<Int>) -> [Int] {
        var values = Array(stride(from: range.lowerBound, through: range.upperBound, by: 100))
        if values.last != range.upperBound { values.append(range.upperBound) }
        return values
    }

    private static func checkedSite(room: RoomSpec, brief: DesignBrief) -> (Site?, [String]) {
        var issues: [String] = []
        if !room.confirmed { issues.append("Confirm the measurements and obstacle positions.") }
        if !room.otherObjectsCleared { issues.append("Confirm that the rest of the floor is clear.") }
        if brief.budgetCents < 0 { issues.append("Enter a nonnegative CAD budget.") }
        if !(0...maximumSpan).contains(brief.chairPullbackMM) { issues.append("Enter a valid chair pullback distance.") }
        guard positiveSpan.contains(room.widthMM), positiveSpan.contains(room.depthMM),
              positiveSpan.contains(room.heightMM) else {
            return (nil, issues + ["Room dimensions must be greater than zero and at most 100 m."])
        }

        let roomBounds = RectMM(xMM: 0, zMM: 0, widthMM: room.widthMM, depthMM: room.depthMM)
        let door = room.doorReserve
        guard positiveSpan.contains(door.widthMM), positiveSpan.contains(door.depthMM),
              door.xMM >= 0, door.zMM >= 0,
              door.xMM <= room.widthMM - door.widthMM, door.zMM <= room.depthMM - door.depthMM else {
            return (nil, issues + ["Enter a positive door reserve completely inside the room."])
        }

        let item = room.kept
        guard positiveSpan.contains(item.widthMM), positiveSpan.contains(item.depthMM),
              (1...room.heightMM).contains(item.heightMM) else {
            return (nil, issues + ["Enter valid dimensions for the retained item."])
        }
        guard (0..<4).contains(item.quarterTurns), (0...room.widthMM).contains(item.centerXMM),
              (0...room.depthMM).contains(item.centerZMM) else {
            return (nil, issues + ["Enter a valid position and rotation for the retained item."])
        }
        let rotated = item.quarterTurns % 2 == 1
        let kept = RectMM.centered(
            x: item.centerXMM, z: item.centerZMM,
            width: rotated ? item.depthMM : item.widthMM, depth: rotated ? item.widthMM : item.depthMM
        )
        if !roomBounds.contains(kept) { issues.append("The retained item must sit entirely inside the room.") }
        if kept.overlaps(door) { issues.append("The retained item overlaps the door reserve.") }
        guard issues.isEmpty else { return (nil, issues) }
        return (Site(bounds: roomBounds, obstacles: [("door reserve", door), ("retained item", kept)]), [])
    }

    private static func selectedPair(
        room: RoomSpec, brief: DesignBrief, offers: [OfferSnapshot], plan: LayoutPlan
    ) -> (Pair?, [String]) {
        guard let (desk, chair) = selectedOffers(for: plan, from: offers) else {
            return (nil, ["The selected desk or chair offer is missing or ambiguous."])
        }
        return checkedPair(desk: desk, chair: chair, room: room, brief: brief)
    }

    private static func selectedOffers(
        for plan: LayoutPlan, from offers: [OfferSnapshot]
    ) -> (OfferSnapshot, OfferSnapshot)? {
        let desks = offers.filter { $0.id == plan.deskOfferID }
        let chairs = offers.filter { $0.id == plan.chairOfferID }
        guard desks.count == 1, chairs.count == 1, desks[0].category == "desk", chairs[0].category == "chair" else {
            return nil
        }
        return (desks[0], chairs[0])
    }

    private static func checkedPair(
        desk: OfferSnapshot, chair: OfferSnapshot, room: RoomSpec, brief: DesignBrief
    ) -> (Pair?, [String]) {
        let deskDimensions = Dimensions(desk)
        let chairDimensions = Dimensions(chair)
        var issues: [String] = []
        var reasons: [String] = []
        if room.source == "sample" { reasons.append("The room uses sample measurements.") }
        for (offer, dimensions) in [(desk, deskDimensions), (chair, chairDimensions)] {
            if offer.dimensionConflict { issues.append("\(offer.name) has conflicting dimensions.") }
            if let dimensions {
                if dimensions.height > room.heightMM { issues.append("\(offer.name) is taller than the room.") }
            } else {
                issues.append("\(offer.name) is missing valid dimensions.")
            }
            if offer.currency != "CAD" { issues.append("\(offer.name) requires a CAD price.") }
            if offer.priceCents.map({ $0 >= 0 }) != true { issues.append("\(offer.name) is missing a valid price.") }
            switch offer.stock {
            case "out_of_stock": issues.append("\(offer.name) is out of stock.")
            case "in_stock": break
            default: reasons.append("\(offer.name) stock is unverified.")
            }
            switch offer.provenance {
            case "saved": reasons.append("\(offer.name) uses saved retailer data.")
            case "sample": reasons.append("\(offer.name) uses sample offer data.")
            case "live": break
            default: reasons.append("\(offer.name) source is unverified.")
            }
        }
        guard issues.isEmpty, let deskDimensions, let chairDimensions,
              let deskPrice = desk.priceCents, let chairPrice = chair.priceCents else {
            return (nil, issues)
        }
        let (subtotal, overflow) = deskPrice.addingReportingOverflow(chairPrice)
        guard !overflow, subtotal <= brief.budgetCents else {
            return (nil, ["\(desk.name) and \(chair.name) exceed the CAD budget."])
        }
        return (Pair(
            deskID: desk.id, chairID: chair.id, desk: deskDimensions, chair: chairDimensions,
            closedStorage: desk.closedStorage, subtotal: subtotal, reasons: reasons
        ), [])
    }

    private static func noFit(_ issues: [String]) -> PlanResult {
        var seen: Set<String> = []
        return PlanResult(
            plan: nil,
            issues: ["No checked layout found."] + issues.filter { seen.insert($0).inserted }
        )
    }
}

// These bounds keep dimensions physical and all geometry arithmetic within Int.
private let maximumSpan = 100_000
private let positiveSpan = 1...maximumSpan
private let signedSpan = (-maximumSpan)...maximumSpan

private struct Dimensions {
    let width: Int
    let depth: Int
    let height: Int

    init?(_ offer: OfferSnapshot) {
        guard let width = offer.widthMM, let depth = offer.depthMM, let height = offer.heightMM,
              positiveSpan.contains(width), positiveSpan.contains(depth), positiveSpan.contains(height) else { return nil }
        self.width = width
        self.depth = depth
        self.height = height
    }
}

private struct Pair {
    let deskID: String
    let chairID: String
    let desk: Dimensions
    let chair: Dimensions
    let closedStorage: Bool
    let subtotal: Int
    let reasons: [String]

    func rank(preferClosedStorage: Bool) -> (Int, Int, String, String) {
        (preferClosedStorage && closedStorage ? 0 : 1, subtotal, deskID, chairID)
    }

    func plan(at pose: Pose) -> LayoutPlan {
        LayoutPlan(
            deskOfferID: deskID, chairOfferID: chairID,
            centerXMM: pose.x, centerZMM: pose.z, quarterTurns: pose.turn,
            subtotalCents: subtotal, provisional: !reasons.isEmpty, reasons: reasons
        )
    }

    func layout(turn: Int, pullback: Int) -> Layout? {
        Layout(desk: desk, chair: chair, turn: turn, pullback: pullback)
    }
}

private struct Pose {
    let x: Int
    let z: Int
    let turn: Int

    init(x: Int, z: Int, turn: Int) {
        self.x = x
        self.z = z
        self.turn = turn
    }

    init(_ plan: LayoutPlan) {
        self.init(x: plan.centerXMM, z: plan.centerZMM, turn: plan.quarterTurns)
    }

    func rank(relativeTo target: Pose?) -> (Double, Int, Int, Int, Int) {
        guard let target else { return (0, 0, turn, x, z) }
        let dx = Double(x) - Double(target.x)
        let dz = Double(z) - Double(target.z)
        let turnDelta = abs(turn - (target.turn % 4 + 4) % 4)
        return (dx * dx + dz * dz, min(turnDelta, 4 - turnDelta), turn, x, z)
    }
}

private struct Site {
    let bounds: RectMM
    let obstacles: [(name: String, rect: RectMM)]
}

private struct Layout {
    let parts: [(name: String, rect: RectMM)]

    init?(desk: Dimensions, chair: Dimensions, turn: Int, pullback: Int) {
        let deskRect: RectMM
        let chairRect: RectMM
        let clearance: RectMM
        switch turn {
        case 0:
            deskRect = .centered(x: 0, z: 0, width: desk.width, depth: desk.depth)
            chairRect = RectMM(xMM: -chair.width / 2, zMM: deskRect.maxZ, widthMM: chair.width, depthMM: chair.depth)
            clearance = RectMM(xMM: chairRect.xMM, zMM: chairRect.maxZ, widthMM: chair.width, depthMM: pullback)
        case 1:
            deskRect = .centered(x: 0, z: 0, width: desk.depth, depth: desk.width)
            chairRect = RectMM(xMM: deskRect.xMM - chair.depth, zMM: -chair.width / 2, widthMM: chair.depth, depthMM: chair.width)
            clearance = RectMM(xMM: chairRect.xMM - pullback, zMM: chairRect.zMM, widthMM: pullback, depthMM: chair.width)
        case 2:
            deskRect = .centered(x: 0, z: 0, width: desk.width, depth: desk.depth)
            chairRect = RectMM(xMM: -chair.width / 2, zMM: deskRect.zMM - chair.depth, widthMM: chair.width, depthMM: chair.depth)
            clearance = RectMM(xMM: chairRect.xMM, zMM: chairRect.zMM - pullback, widthMM: chair.width, depthMM: pullback)
        case 3:
            deskRect = .centered(x: 0, z: 0, width: desk.depth, depth: desk.width)
            chairRect = RectMM(xMM: deskRect.maxX, zMM: -chair.width / 2, widthMM: chair.depth, depthMM: chair.width)
            clearance = RectMM(xMM: chairRect.maxX, zMM: chairRect.zMM, widthMM: pullback, depthMM: chair.width)
        default:
            return nil
        }
        parts = [("desk", deskRect), ("chair", chairRect), ("pullback", clearance)]
    }

    func ranges(in site: Site) -> (ClosedRange<Int>, ClosedRange<Int>)? {
        let xMin = site.bounds.xMM - parts.map(\.rect.xMM).min()!
        let xMax = site.bounds.maxX - parts.map(\.rect.maxX).max()!
        let zMin = site.bounds.zMM - parts.map(\.rect.zMM).min()!
        let zMax = site.bounds.maxZ - parts.map(\.rect.maxZ).max()!
        guard xMin <= xMax, zMin <= zMax else { return nil }
        return (xMin...xMax, zMin...zMax)
    }

    func issues(at pose: Pose, in site: Site) -> [String] {
        guard let (xRange, zRange) = ranges(in: site), xRange.contains(pose.x), zRange.contains(pose.z) else {
            return ["The desk, chair and pullback clearance must sit entirely inside the room."]
        }
        var issues: [String] = []
        for part in parts {
            let placed = part.rect.translated(x: pose.x, z: pose.z)
            for obstacle in site.obstacles where placed.overlaps(obstacle.rect) {
                issues.append("The \(part.name) overlaps the \(obstacle.name).")
            }
        }
        return issues
    }

    func nearestCandidates(
        to target: Pose, in site: Site, xRange: ClosedRange<Int>, zRange: ClosedRange<Int>
    ) -> ([Int], [Int]) {
        var xValues: Set<Int> = [target.x.clamped(to: xRange), xRange.lowerBound, xRange.upperBound]
        var zValues: Set<Int> = [target.z.clamped(to: zRange), zRange.lowerBound, zRange.upperBound]
        // Fit can change only where the edges of a moving part and an obstacle meet.
        for part in parts where part.rect.widthMM > 0 && part.rect.depthMM > 0 {
            for obstacle in site.obstacles {
                xValues.insert((obstacle.rect.xMM - part.rect.maxX).clamped(to: xRange))
                xValues.insert((obstacle.rect.maxX - part.rect.xMM).clamped(to: xRange))
                zValues.insert((obstacle.rect.zMM - part.rect.maxZ).clamped(to: zRange))
                zValues.insert((obstacle.rect.maxZ - part.rect.zMM).clamped(to: zRange))
            }
        }
        return (xValues.sorted(), zValues.sorted())
    }
}

private extension Int {
    func clamped(to range: ClosedRange<Int>) -> Int {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

private extension RectMM {
    var maxX: Int { xMM + widthMM }
    var maxZ: Int { zMM + depthMM }

    static func centered(x: Int, z: Int, width: Int, depth: Int) -> RectMM {
        RectMM(xMM: x - width / 2, zMM: z - depth / 2, widthMM: width, depthMM: depth)
    }

    func translated(x: Int, z: Int) -> RectMM {
        RectMM(xMM: xMM + x, zMM: zMM + z, widthMM: widthMM, depthMM: depthMM)
    }

    func contains(_ other: RectMM) -> Bool {
        xMM <= other.xMM && other.maxX <= maxX && zMM <= other.zMM && other.maxZ <= maxZ
    }

    func overlaps(_ other: RectMM) -> Bool {
        widthMM > 0 && depthMM > 0 && other.widthMM > 0 && other.depthMM > 0
            && xMM < other.maxX && other.xMM < maxX && zMM < other.maxZ && other.zMM < maxZ
    }
}
