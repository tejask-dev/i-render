import CoreText
import RoomProofCore
import UIKit

enum FitSheet {
    @MainActor
    static func export(title: String, room: RoomSpec, brief: DesignBrief, offers: [OfferSnapshot], plan: LayoutPlan) throws -> URL {
        let issues = Planner.validate(room: room, brief: brief, offers: offers, plan: plan)
        guard issues.isEmpty else { throw ExportError.invalidPlan(issues.joined(separator: " ")) }

        let ids = [plan.deskOfferID, plan.chairOfferID]
        let selected = ids.compactMap { id in offers.first { $0.id == id } }
        let footprints = Planner.footprints(plan: plan, brief: brief, offers: selected)
        guard selected.count == 2, footprints["desk"] != nil, footprints["chair"] != nil else {
            throw ExportError.invalidPlan("The selected pair is missing dimensions.")
        }

        let format = UIGraphicsPDFRendererFormat()
        format.documentInfo = [
            kCGPDFContextTitle as String: "\(title) — RoomProof Fit Sheet",
            kCGPDFContextCreator as String: "RoomProof"
        ]
        let renderer = UIGraphicsPDFRenderer(bounds: Page.bounds, format: format)
        var rendered = true
        let data = renderer.pdfData { context in
            let page = Page(context)
            page.begin("MEASURED LAYOUT")
            page.text(title, size: 28, weight: .semibold)
            page.text(
                "Room \(cm(room.widthMM)) × \(cm(room.depthMM)) × \(cm(room.heightMM)) cm  ·  Width × depth × height",
                size: 12, color: Page.muted
            )
            page.space(14)
            page.drawPlan(room: room, footprints: footprints)
            page.space(13)
            page.text(
                "\(cad(plan.subtotalCents)) merchandise subtotal  /  \(cad(brief.budgetCents)) budget",
                size: 15, weight: .semibold
            )
            page.text("Subtotal excludes taxes and delivery.", color: Page.muted)
            page.space(9)
            page.text(
                "Door reserve  \(cm(room.doorReserve.widthMM)) × \(cm(room.doorReserve.depthMM)) cm  ·  Chair pullback  \(cm(brief.chairPullbackMM)) cm"
            )
            page.text(
                "Retained  \(room.kept.label)  ·  \(cm(room.kept.widthMM)) × \(cm(room.kept.depthMM)) × \(cm(room.kept.heightMM)) cm"
            )
            page.space(9)
            let undatedOffer = selected.contains { $0.checkedAt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            let status = plan.provisional || undatedOffer ? "Provisional fit" : "Checked footprint fit"
            page.text(status, size: 13, weight: .semibold, color: Page.accent)
            page.text("Measurements confirmed using the \(room.source) room source. The remaining floor was confirmed clear.")
            page.text(plan.reasons.joined(separator: " "), color: Page.muted)
            page.space(8)
            page.text(
                "Fit covers the modeled floor footprints and reserved clearances. Verify actual dimensions, door swing, delivery access, ergonomics, and assembly before buying.",
                color: Page.muted
            )

            page.begin("PRODUCT SOURCES")
            page.text("The selected pair", size: 28, weight: .semibold)
            page.text("Check current prices and store availability before buying.", color: Page.muted)
            for offer in selected {
                page.space(14)
                page.rule()
                page.space(12)
                page.text("\(offer.retailer)  ·  \(offer.name)", size: 18, weight: .semibold)
                page.text(
                    "\(offer.category.capitalized)  ·  SKU \(offer.sku)  ·  \(offer.priceCents.map(cad) ?? "Price unknown")",
                    size: 12, weight: .medium, color: Page.accent
                )
                if let width = offer.widthMM, let depth = offer.depthMM, let height = offer.heightMM {
                    page.text("External dimensions  \(cm(width)) × \(cm(depth)) × \(cm(height)) cm")
                }
                let checkedAt = offer.checkedAt.trimmingCharacters(in: .whitespacesAndNewlines)
                page.text(sourceStatus(offer.provenance, checkedAt: checkedAt), weight: .medium)
                page.text("Capture time  \(checkedAt.isEmpty ? "Unavailable" : checkedAt)")
                page.text("Stock  \(stockStatus(offer.stock))  ·  \(offer.stockScope.isEmpty ? "Store scope unavailable" : offer.stockScope)")
                page.text("Price conditions  \(offer.priceConditions.isEmpty ? "Unspecified" : offer.priceConditions)")
                page.space(4)
                if let url = URL(string: offer.url), ["https", "http"].contains(url.scheme ?? ""), url.host != nil {
                    page.text(offer.url, size: 10, color: Page.accent, url: url)
                } else {
                    page.text(offer.url.isEmpty ? "Retailer link unavailable" : offer.url, size: 10, color: Page.muted)
                }
                page.text(offer.evidenceQuote.isEmpty ? "Source excerpt unavailable." : offer.evidenceQuote, size: 10, color: Page.muted)
            }
            rendered = !page.failed
        }
        guard rendered else { throw ExportError.renderingFailed }

        let cache = try FileManager.default.url(for: .cachesDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let destination = cache.appendingPathComponent("RoomProof Fit Sheet \(UUID().uuidString.prefix(8)).pdf")
        try data.write(to: destination, options: .atomic)
        return destination
    }

    private static func cad(_ cents: Int) -> String {
        let price = (Decimal(cents) / 100).formatted(.currency(code: "CAD").locale(Locale(identifier: "en_CA")))
        return "CAD \(price)"
    }

    private static func cm(_ mm: Int) -> String {
        (Decimal(mm) / 10).formatted(.number.precision(.fractionLength(0...1)))
    }

    private static func sourceStatus(_ provenance: String, checkedAt: String) -> String {
        switch provenance {
        case "live": checkedAt.isEmpty ? "Undated source record" : "Retailer page capture"
        case "saved": "Saved catalog snapshot"
        case "sample": "Sample offer"
        default: "Source provenance unavailable"
        }
    }

    private static func stockStatus(_ stock: String) -> String {
        switch stock {
        case "in_stock": "Reported in stock"
        case "out_of_stock": "Reported out of stock"
        default: "Unknown"
        }
    }

    private enum ExportError: LocalizedError {
        case invalidPlan(String)
        case renderingFailed

        var errorDescription: String? {
            switch self {
            case .invalidPlan(let reason): reason
            case .renderingFailed: "The Fit Sheet could not render all source evidence."
            }
        }
    }

    @MainActor
    private final class Page {
        static let bounds = CGRect(x: 0, y: 0, width: 612, height: 792)
        static let ink = UIColor(red: 0.11, green: 0.16, blue: 0.15, alpha: 1)
        static let muted = UIColor(red: 0.33, green: 0.38, blue: 0.37, alpha: 1)
        static let accent = UIColor(red: 0.08, green: 0.36, blue: 0.31, alpha: 1)
        static let border = UIColor(red: 0.82, green: 0.86, blue: 0.84, alpha: 1)

        private let context: UIGraphicsPDFRendererContext
        private let margin: CGFloat = 52
        private let contentTop: CGFloat = 87
        private let contentBottom: CGFloat = 731
        private var width: CGFloat { Self.bounds.width - margin * 2 }
        private var y: CGFloat = 0
        private var number = 0
        private var section = ""
        private(set) var failed = false

        init(_ context: UIGraphicsPDFRendererContext) {
            self.context = context
        }

        func begin(_ section: String) {
            self.section = section
            number += 1
            context.beginPage()
            let band = CGRect(x: 0, y: 0, width: Self.bounds.width, height: 66)
            fill(band, Self.accent)
            line("ROOMPROOF", x: margin, y: 27, size: 12, weight: .bold, color: .white)
            line(section, x: 427, y: 29, size: 9, weight: .semibold, color: .white)
            line("RoomProof Fit Sheet", x: margin, y: 752, size: 9, color: Self.muted)
            line("\(number)", x: 548, y: 752, size: 9, color: Self.muted)
            y = contentTop
        }

        func space(_ points: CGFloat) { y += points }

        func rule() {
            if y > contentBottom { begin(section) }
            fill(CGRect(x: margin, y: y, width: width, height: 1), Self.border)
        }

        func text(
            _ string: String, size: CGFloat = 11, weight: UIFont.Weight = .regular, color: UIColor? = nil,
            url: URL? = nil
        ) {
            guard !string.isEmpty, !failed else { return }
            let font = UIFont.systemFont(ofSize: size, weight: weight)
            let paragraph = NSMutableParagraphStyle()
            paragraph.lineBreakMode = url == nil ? .byWordWrapping : .byCharWrapping
            paragraph.lineSpacing = 2
            let styled = NSAttributedString(
                string: string,
                attributes: [.font: font, .foregroundColor: color ?? Page.ink, .paragraphStyle: paragraph]
            )
            let framesetter = CTFramesetterCreateWithAttributedString(styled)
            var offset = 0
            while offset < styled.length {
                if contentBottom - y < font.lineHeight + 3 { begin(section) }
                let height = contentBottom - y
                let rect = CGRect(x: 0, y: 0, width: width, height: height)
                let range = CFRange(location: offset, length: 0)
                let frame = CTFramesetterCreateFrame(framesetter, range, CGPath(rect: rect, transform: nil), nil)
                let visible = CTFrameGetVisibleStringRange(frame)
                guard visible.length > 0 else {
                    if y > contentTop {
                        begin(section)
                        continue
                    }
                    failed = true
                    return
                }

                let graphics = context.cgContext
                graphics.saveGState()
                graphics.translateBy(x: margin, y: y + height)
                graphics.scaleBy(x: 1, y: -1)
                graphics.textMatrix = .identity
                CTFrameDraw(frame, graphics)
                graphics.restoreGState()

                let drawnSize = CTFramesetterSuggestFrameSizeWithConstraints(
                    framesetter, visible, nil, CGSize(width: width, height: .greatestFiniteMagnitude), nil
                )
                let drawnHeight = ceil(drawnSize.height) + 3
                if let url {
                    let link = CGRect(x: margin, y: y, width: min(width, drawnSize.width + 1), height: drawnHeight)
                    context.setURL(url, for: link.applying(graphics.userSpaceToDeviceSpaceTransform))
                }
                offset += visible.length
                y += drawnHeight
                if offset < styled.length { begin(section) }
            }
            y += 2
        }

        func drawPlan(room: RoomSpec, footprints: [String: RectMM]) {
            let planWidth = CGFloat(room.widthMM)
            let planDepth = CGFloat(room.depthMM)
            let scale = min((width - 72) / planWidth, 220 / planDepth)
            let diagramHeight = planDepth * scale
            if y + diagramHeight + 79 > contentBottom { begin(section) }
            let drawing = CGRect(
                x: margin + width / 2 - planWidth * scale / 2, y: y + 25,
                width: planWidth * scale, height: diagramHeight
            )
            let floor = UIColor(red: 0.97, green: 0.97, blue: 0.94, alpha: 1)
            fill(drawing, floor)
            stroke(drawing, Self.ink)
            let widthText = "\(FitSheet.cm(room.widthMM)) cm"
            let depthText = "\(FitSheet.cm(room.depthMM)) cm"
            let font = UIFont.monospacedDigitSystemFont(ofSize: 10, weight: .medium)
            let attributes: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: Self.muted]
            let widthLabel = NSString(string: widthText)
            let labelWidth = widthLabel.size(withAttributes: attributes).width
            widthLabel.draw(at: CGPoint(x: drawing.midX - labelWidth / 2, y: drawing.minY - 19), withAttributes: attributes)
            let graphics = context.cgContext
            graphics.saveGState()
            graphics.translateBy(x: drawing.minX - 22, y: drawing.midY)
            graphics.rotate(by: -.pi / 2)
            let depthLabel = NSString(string: depthText)
            let depthWidth = depthLabel.size(withAttributes: attributes).width
            depthLabel.draw(at: CGPoint(x: -depthWidth / 2, y: 0), withAttributes: attributes)
            graphics.restoreGState()

            let furniture = room.kept
            let turn = furniture.quarterTurns % 2 == 1
            let keptWidth = turn ? furniture.depthMM : furniture.widthMM
            let keptDepth = turn ? furniture.widthMM : furniture.depthMM
            let retained = RectMM(
                xMM: furniture.centerXMM - keptWidth / 2, zMM: furniture.centerZMM - keptDepth / 2,
                widthMM: keptWidth, depthMM: keptDepth
            )
            let door = UIColor(red: 0.63, green: 0.26, blue: 0.12, alpha: 1)
            let pullback = UIColor(red: 0.14, green: 0.40, blue: 0.60, alpha: 1)
            let desk = UIColor(red: 0.37, green: 0.24, blue: 0.12, alpha: 1)
            let chair = UIColor(red: 0.17, green: 0.29, blue: 0.34, alpha: 1)
            let shapes: [(String, RectMM?, UIColor, Bool)] = [
                ("Door reserve", room.doorReserve, door, true),
                ("Chair pullback", footprints["pullback"], pullback, true),
                ("Retained", retained, Self.accent, false),
                ("Desk", footprints["desk"], desk, false),
                ("Chair", footprints["chair"], chair, false)
            ]
            let active = shapes.filter { ($0.1?.widthMM ?? 0) > 0 && ($0.1?.depthMM ?? 0) > 0 }
            for (index, part) in active.enumerated() {
                guard let rectangle = part.1 else { continue }
                let shape = CGRect(
                    x: drawing.minX + CGFloat(rectangle.xMM) * scale,
                    y: drawing.maxY - (CGFloat(rectangle.zMM) + CGFloat(rectangle.depthMM)) * scale,
                    width: CGFloat(rectangle.widthMM) * scale,
                    height: CGFloat(rectangle.depthMM) * scale
                )
                let color = part.2
                fill(shape, color.withAlphaComponent(part.3 ? 0.12 : 0.29))
                stroke(shape, color, dashed: part.3)
                let caption = "\(index + 1)"
                if shape.width >= 13, shape.height >= 13 {
                    line(caption, x: shape.midX - 3, y: shape.midY - 7, size: 10, weight: .bold, color: color)
                }

                let legendWidth = width / 3
                let column = CGFloat(index % 3)
                let row = CGFloat(index / 3)
                let legendY = drawing.maxY + 14 + row * 20
                let glyph = CGRect(x: margin + column * legendWidth, y: legendY + 1, width: 14, height: 14)
                fill(glyph, color.withAlphaComponent(part.3 ? 0.12 : 0.29))
                stroke(glyph, color, dashed: part.3)
                line(caption, x: glyph.minX + 4, y: legendY, size: 10, weight: .bold, color: color)
                line(part.0, x: glyph.maxX + 6, y: legendY, size: 10, color: Self.ink)
            }
            y = drawing.maxY + 54
        }

        private func line(
            _ string: String, x: CGFloat, y: CGFloat, size: CGFloat, weight: UIFont.Weight = .regular, color: UIColor
        ) {
            (string as NSString).draw(
                at: CGPoint(x: x, y: y),
                withAttributes: [.font: UIFont.systemFont(ofSize: size, weight: weight), .foregroundColor: color]
            )
        }

        private func fill(_ rect: CGRect, _ color: UIColor) {
            context.cgContext.setFillColor(color.cgColor)
            context.cgContext.fill(rect)
        }

        private func stroke(_ rect: CGRect, _ color: UIColor, dashed: Bool = false) {
            let graphics = context.cgContext
            graphics.saveGState()
            graphics.setStrokeColor(color.cgColor)
            graphics.setLineWidth(1.1)
            if dashed { graphics.setLineDash(phase: 0, lengths: [4, 2]) }
            graphics.stroke(rect)
            graphics.restoreGState()
        }
    }
}
