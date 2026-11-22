public struct RectMM: Codable, Equatable {
    public var xMM: Int
    public var zMM: Int
    public var widthMM: Int
    public var depthMM: Int

    public init(xMM: Int, zMM: Int, widthMM: Int, depthMM: Int) {
        self.xMM = xMM
        self.zMM = zMM
        self.widthMM = widthMM
        self.depthMM = depthMM
    }

    public var centerXMM: Int { Self.midpoint(origin: xMM, span: widthMM) }
    public var centerZMM: Int { Self.midpoint(origin: zMM, span: depthMM) }

    private static func midpoint(origin: Int, span: Int) -> Int {
        let (center, overflow) = origin.addingReportingOverflow(span / 2)
        guard overflow else { return center }
        return origin > 0 ? Int.max : Int.min
    }
}

public struct KeptItem: Codable, Equatable {
    public var id: String
    public var label: String
    public var widthMM: Int
    public var depthMM: Int
    public var heightMM: Int
    public var centerXMM: Int
    public var centerZMM: Int
    public var quarterTurns: Int

    public init(
        id: String, label: String, widthMM: Int, depthMM: Int, heightMM: Int,
        centerXMM: Int, centerZMM: Int, quarterTurns: Int
    ) {
        self.id = id
        self.label = label
        self.widthMM = widthMM
        self.depthMM = depthMM
        self.heightMM = heightMM
        self.centerXMM = centerXMM
        self.centerZMM = centerZMM
        self.quarterTurns = quarterTurns
    }
}

public struct RoomSpec: Codable, Equatable {
    public var widthMM: Int
    public var depthMM: Int
    public var heightMM: Int
    public var doorReserve: RectMM
    public var kept: KeptItem
    public var source: String
    public var confirmed: Bool
    public var otherObjectsCleared: Bool

    public init(
        widthMM: Int, depthMM: Int, heightMM: Int, doorReserve: RectMM, kept: KeptItem,
        source: String, confirmed: Bool, otherObjectsCleared: Bool
    ) {
        self.widthMM = widthMM
        self.depthMM = depthMM
        self.heightMM = heightMM
        self.doorReserve = doorReserve
        self.kept = kept
        self.source = source
        self.confirmed = confirmed
        self.otherObjectsCleared = otherObjectsCleared
    }
}

public struct DesignBrief: Codable, Equatable {
    public var budgetCents: Int
    public var preferClosedStorage: Bool
    public var style: String
    public var chairPullbackMM: Int
    public var notes: String

    public init(budgetCents: Int, preferClosedStorage: Bool, style: String, chairPullbackMM: Int, notes: String) {
        self.budgetCents = budgetCents
        self.preferClosedStorage = preferClosedStorage
        self.style = style
        self.chairPullbackMM = chairPullbackMM
        self.notes = notes
    }
}

public struct OfferSnapshot: Codable, Equatable {
    public var id: String
    public var retailer: String
    public var sku: String
    public var name: String
    public var category: String
    public var widthMM: Int?
    public var depthMM: Int?
    public var heightMM: Int?
    public var priceCents: Int?
    public var currency: String
    public var stock: String
    public var stockScope: String
    public var closedStorage: Bool
    public var url: String
    public var evidenceQuote: String
    public var checkedAt: String
    public var provenance: String
    public var dimensionConflict: Bool
    public var priceConditions: String

    public init(
        id: String, retailer: String, sku: String, name: String, category: String,
        widthMM: Int?, depthMM: Int?, heightMM: Int?, priceCents: Int?, currency: String,
        stock: String, stockScope: String, closedStorage: Bool, url: String,
        evidenceQuote: String, checkedAt: String, provenance: String, dimensionConflict: Bool,
        priceConditions: String
    ) {
        self.id = id
        self.retailer = retailer
        self.sku = sku
        self.name = name
        self.category = category
        self.widthMM = widthMM
        self.depthMM = depthMM
        self.heightMM = heightMM
        self.priceCents = priceCents
        self.currency = currency
        self.stock = stock
        self.stockScope = stockScope
        self.closedStorage = closedStorage
        self.url = url
        self.evidenceQuote = evidenceQuote
        self.checkedAt = checkedAt
        self.provenance = provenance
        self.dimensionConflict = dimensionConflict
        self.priceConditions = priceConditions
    }
}

public struct LayoutPlan: Codable, Equatable {
    public var deskOfferID: String
    public var chairOfferID: String
    public var centerXMM: Int
    public var centerZMM: Int
    public var quarterTurns: Int
    public var subtotalCents: Int
    public var provisional: Bool
    public var reasons: [String]

    public init(
        deskOfferID: String, chairOfferID: String, centerXMM: Int, centerZMM: Int, quarterTurns: Int,
        subtotalCents: Int, provisional: Bool, reasons: [String]
    ) {
        self.deskOfferID = deskOfferID
        self.chairOfferID = chairOfferID
        self.centerXMM = centerXMM
        self.centerZMM = centerZMM
        self.quarterTurns = quarterTurns
        self.subtotalCents = subtotalCents
        self.provisional = provisional
        self.reasons = reasons
    }
}

public struct PlanResult: Codable, Equatable {
    public var plan: LayoutPlan?
    public var issues: [String]

    public init(plan: LayoutPlan?, issues: [String]) {
        self.plan = plan
        self.issues = issues
    }
}
