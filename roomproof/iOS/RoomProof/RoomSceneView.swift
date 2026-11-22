import RealityKit
import RoomProofCore
import SwiftUI

struct RoomSceneView: UIViewRepresentable {
    var room: RoomSpec
    var brief: DesignBrief
    var offers: [OfferSnapshot]
    var plan: LayoutPlan?
    var invalid = false

    func makeUIView(context: Context) -> OrbitView { OrbitView() }

    func updateUIView(_ view: OrbitView, context: Context) {
        let selected = offers.filter { $0.id == plan?.deskOfferID || $0.id == plan?.chairOfferID }
        let footprints = plan.map { Planner.footprints(plan: $0, brief: brief, offers: selected) } ?? [:]
        view.update(room: room, footprints: footprints, offers: selected, turn: plan?.quarterTurns ?? 0, invalid: invalid)
    }

    final class OrbitView: UIView {
        private struct Furniture: Equatable {
            var footprints: [String: RectMM]
            var sizes: [String: SIMD3<Float>]
            var closedStorage: Bool
            var turn: Int
            var invalid: Bool
        }

        private let preview = ARView(frame: .zero, cameraMode: .nonAR, automaticallyConfigureSession: false)
        private let anchor = AnchorEntity(world: .zero)
        private let shell = Entity()
        private let contents = Entity()
        private let camera = PerspectiveCamera()
        private var currentRoom: RoomSpec?
        private var furniture: Furniture?
        private var cameraBounds = SIMD3<Float>(3, 1, 3)
        private var azimuth: Float = 0.66

        init() {
            super.init(frame: .zero)
            preview.environment.background = .color(UIColor(red: 0.91, green: 0.94, blue: 0.93, alpha: 1))
            preview.renderOptions.insert(.disableMotionBlur)
            preview.isUserInteractionEnabled = false
            addSubview(preview)

            camera.camera.fieldOfViewInDegrees = 38
            anchor.addChild(camera)
            anchor.addChild(shell)
            anchor.addChild(contents)
            addLight(from: [2, 5, 3], intensity: 1_850)
            addLight(from: [-3, 3, -2], intensity: 850)
            preview.scene.addAnchor(anchor)

            let pan = UIPanGestureRecognizer(target: self, action: #selector(orbit(_:)))
            addGestureRecognizer(pan)
            isAccessibilityElement = true
            accessibilityTraits = [.image, .adjustable]
            accessibilityLabel = "3D room preview"
            accessibilityHint = "Swipe up or down to rotate the room."
        }

        required init?(coder: NSCoder) { nil }

        override func layoutSubviews() {
            super.layoutSubviews()
            preview.frame = bounds
            frameCamera()
        }

        func update(
            room: RoomSpec, footprints: [String: RectMM], offers: [OfferSnapshot], turn: Int, invalid: Bool
        ) {
            var sizes: [String: SIMD3<Float>] = [:]
            for offer in offers {
                if let width = offer.widthMM, let height = offer.heightMM, let depth = offer.depthMM {
                    sizes[offer.category] = [meters(width), meters(height), meters(depth)]
                }
            }
            let newFurniture = Furniture(
                footprints: footprints, sizes: sizes,
                closedStorage: offers.contains { $0.category == "desk" && $0.closedStorage },
                turn: turn, invalid: invalid
            )
            let roomChanged = room != currentRoom
            let furnitureChanged = newFurniture != furniture
            guard roomChanged || furnitureChanged else { return }
            if roomChanged {
                currentRoom = room
                rebuildShell(room)
            }
            if furnitureChanged {
                furniture = newFurniture
                rebuildFurniture(newFurniture)
            }
            updateCameraBounds(room: room, furniture: newFurniture)
            let names = offers.map(\.name).joined(separator: " and ")
            accessibilityValue = footprints.isEmpty ? "Room and \(room.kept.label)" : "\(names), \(room.kept.label), and reserved clearances"
        }

        private func addLight(from position: SIMD3<Float>, intensity: Float) {
            let light = DirectionalLight()
            light.light.intensity = intensity
            light.look(at: .zero, from: position, relativeTo: nil)
            anchor.addChild(light)
        }

        private func rebuildShell(_ room: RoomSpec) {
            shell.children.removeAll()
            let width = meters(room.widthMM), depth = meters(room.depthMM)
            guard valid([width, depth]) else { return }

            let wall = wallHeight(room)
            let floor = UIColor(red: 0.78, green: 0.68, blue: 0.54, alpha: 1)
            let back = UIColor(red: 0.79, green: 0.82, blue: 0.77, alpha: 1)
            let side = UIColor(red: 0.91, green: 0.89, blue: 0.82, alpha: 1)
            box(shell, [width + 0.08, 0.07, depth + 0.08], [width / 2 - 0.02, -0.035, -depth / 2 - 0.02], floor)
            let planks = max(1, min(16, Int(depth / 0.32)))
            let seam = UIColor(red: 0.67, green: 0.58, blue: 0.46, alpha: 1)
            for row in 1..<planks {
                let z = -depth * Float(row) / Float(planks)
                box(shell, [width, 0.001, 0.003], [width / 2, 0.001, z], seam)
            }
            box(shell, [width, wall, 0.06], [width / 2, wall / 2, -depth - 0.03], back)
            box(shell, [0.06, wall, depth], [-0.03, wall / 2, -depth / 2], side)
            box(shell, [width, 0.035, 0.012], [width / 2, 0.018, -depth + 0.006], .white)
            box(shell, [0.012, 0.035, depth], [0.006, 0.018, -depth / 2], .white)

            reserve(room.doorReserve, in: shell, at: 0.004, color: UIColor(red: 0.69, green: 0.27, blue: 0.09, alpha: 1))
            let item = room.kept
            let size = SIMD3(meters(item.widthMM), meters(item.heightMM), meters(item.depthMM))
            if valid([size.x, size.y, size.z]) {
                let body = place(
                    in: shell, size: size, x: meters(item.centerXMM), z: worldZ(item.centerZMM), turn: item.quarterTurns
                )
                let finish = UIColor(red: 0.38, green: 0.45, blue: 0.43, alpha: 1)
                box(body, [1, 0.92, 0.96], [0, 0.46, 0.02], finish)
                box(body, [1, 0.08, 1], [0, 0.96, 0], finish)
                for x: Float in [-0.246, 0.246] {
                    box(body, [0.48, 0.83, 0.04], [x, 0.47, -0.48], UIColor(red: 0.48, green: 0.56, blue: 0.53, alpha: 1))
                    box(body, [0.10, 0.022, 0.018], [x, 0.70, -0.49], .darkGray)
                }
            }
        }

        private func rebuildFurniture(_ furniture: Furniture) {
            contents.children.removeAll()
            guard let desk = furniture.footprints["desk"], let chair = furniture.footprints["chair"],
                  let deskSize = furniture.sizes["desk"], let chairSize = furniture.sizes["chair"],
                  valid([deskSize.x, deskSize.y, deskSize.z, chairSize.x, chairSize.y, chairSize.z]) else { return }

            let alert = UIColor(red: 0.79, green: 0.22, blue: 0.22, alpha: 1)
            if let pullback = furniture.footprints["pullback"] {
                reserve(pullback, in: contents, at: 0.007, color: furniture.invalid ? alert : .systemTeal)
            }
            if furniture.invalid {
                reserve(desk, in: contents, at: 0.010, color: alert)
                reserve(chair, in: contents, at: 0.010, color: alert)
            }

            let deskBody = place(
                in: contents, size: deskSize, x: centerX(desk), z: worldCenterZ(desk), turn: furniture.turn
            )
            let tabletop = UIColor(red: 0.76, green: 0.55, blue: 0.35, alpha: 1)
            let frame = UIColor(red: 0.23, green: 0.24, blue: 0.23, alpha: 1)
            box(deskBody, [1, 0.075, 1], [0, 0.9625, 0], tabletop)
            for z: Float in [-0.42, 0.42] {
                box(deskBody, [0.042, 0.925, 0.075], [-0.43, 0.4625, z], frame)
                if !furniture.closedStorage {
                    box(deskBody, [0.042, 0.925, 0.075], [0.43, 0.4625, z], frame)
                }
            }
            if furniture.closedStorage {
                box(deskBody, [0.30, 0.925, 0.86], [0.33, 0.4625, 0], .white)
                for y: Float in [0.16, 0.35, 0.54, 0.73] {
                    box(deskBody, [0.285, 0.17, 0.022], [0.33, y, -0.43], UIColor(white: 0.89, alpha: 1))
                    box(deskBody, [0.09, 0.02, 0.018], [0.33, y + 0.045, -0.445], frame)
                }
            }

            // The chair faces the desk, so its back faces into the pullback reserve.
            let chairBody = place(
                in: contents, size: chairSize, x: centerX(chair), z: worldCenterZ(chair), turn: furniture.turn + 2
            )
            let fabric = UIColor(red: 0.22, green: 0.31, blue: 0.36, alpha: 1)
            let padding = UIColor(red: 0.31, green: 0.42, blue: 0.46, alpha: 1)
            box(chairBody, [0.76, 0.09, 0.72], [0, 0.47, -0.045], padding)
            box(chairBody, [0.67, 0.55, 0.14], [0, 0.725, 0.36], fabric)
            box(chairBody, [0.13, 0.42, 0.13], [0, 0.24, 0], frame)
            box(chairBody, [0.92, 0.035, 0.09], [0, 0.066, 0], frame)
            box(chairBody, [0.09, 0.035, 0.92], [0, 0.066, 0], frame)
            for x: Float in [-0.455, 0.455] {
                box(chairBody, [0.065, 0.058, 0.10], [x, 0.029, 0], frame)
                box(chairBody, [0.09, 0.043, 0.47], [x, 0.67, -0.04], fabric)
                box(chairBody, [0.045, 0.19, 0.07], [x, 0.56, 0.1], frame)
            }
            for z: Float in [-0.45, 0.45] {
                box(chairBody, [0.10, 0.058, 0.10], [0, 0.029, z], frame)
            }
        }

        private func place(in parent: Entity, size: SIMD3<Float>, x: Float, z: Float, turn: Int) -> Entity {
            let model = Entity()
            model.scale = size
            model.position = [x, 0, z]
            model.orientation = simd_quatf(angle: Float(turn % 4) * .pi / 2, axis: [0, 1, 0])
            parent.addChild(model)
            return model
        }

        private func box(_ parent: Entity, _ size: SIMD3<Float>, _ position: SIMD3<Float>, _ color: UIColor) {
            let material = SimpleMaterial(color: color, roughness: 0.82, isMetallic: false)
            addBox(parent, size, position, material)
        }

        private func addBox(_ parent: Entity, _ size: SIMD3<Float>, _ position: SIMD3<Float>, _ material: any RealityKit.Material) {
            let model = ModelEntity(mesh: .generateBox(size: size), materials: [material])
            model.position = position
            parent.addChild(model)
        }

        private func reserve(_ rect: RectMM, in parent: Entity, at y: Float, color: UIColor) {
            let width = meters(rect.widthMM), depth = meters(rect.depthMM)
            guard valid([width, depth]) else { return }
            let x = centerX(rect), z = worldCenterZ(rect)
            let edge = min(0.024, width / 5, depth / 5)
            var tint = UnlitMaterial(color: color)
            tint.blending = .transparent(opacity: 0.22)
            tint.writesDepth = false
            addBox(parent, [width, 0.001, depth], [x, y, z], tint)
            let outline = UnlitMaterial(color: color)
            for sign: Float in [-1, 1] {
                addBox(parent, [width, 0.003, edge], [x, y + 0.002, z + sign * (depth - edge) / 2], outline)
                addBox(parent, [edge, 0.003, depth - edge * 2], [x + sign * (width - edge) / 2, y + 0.002, z], outline)
            }
        }

        private func updateCameraBounds(room: RoomSpec, furniture: Furniture) {
            let width = meters(room.widthMM), depth = meters(room.depthMM)
            guard valid([width, depth]) else { return }
            let keptHeight = meters(room.kept.heightMM)
            let height = valid([keptHeight]) ? keptHeight : 0
            cameraBounds = [width, max(wallHeight(room), height, furniture.sizes.values.map(\.y).max() ?? 0), depth]
            frameCamera()
        }

        private func frameCamera() {
            guard bounds.width > 0, bounds.height > 0 else { return }
            let elevation: Float = 0.84
            let direction = SIMD3<Float>(sin(azimuth) * cos(elevation), sin(elevation), cos(azimuth) * cos(elevation))
            let right = simd_normalize(simd_cross(SIMD3<Float>(0, 1, 0), direction))
            let up = simd_cross(direction, right)
            let target = cameraBounds * [0.5, 0.28, -0.5]
            let halfVertical = tan(camera.camera.fieldOfViewInDegrees * .pi / 360) * 0.87
            let halfHorizontal = halfVertical * Float(bounds.width / bounds.height)
            var distance: Float = 0.3
            for x in [Float(-0.07), cameraBounds.x + 0.03] {
                for y in [Float(-0.07), cameraBounds.y] {
                    for z in [-cameraBounds.z - 0.07, Float(0.03)] {
                        let offset = SIMD3<Float>(x, y, z) - target
                        let need = max(abs(simd_dot(right, offset)) / halfHorizontal, abs(simd_dot(up, offset)) / halfVertical)
                        distance = max(distance, simd_dot(direction, offset) + need)
                    }
                }
            }
            camera.look(at: target, from: target + direction * distance, relativeTo: nil)
        }

        override func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
            guard let pan = gestureRecognizer as? UIPanGestureRecognizer else { return true }
            let velocity = pan.velocity(in: self)
            return abs(velocity.x) > abs(velocity.y)
        }

        @objc private func orbit(_ pan: UIPanGestureRecognizer) {
            rotate(by: -Float(pan.translation(in: self).x) * 0.007)
            pan.setTranslation(.zero, in: self)
        }

        override func accessibilityIncrement() { rotate(by: 0.16) }

        override func accessibilityDecrement() { rotate(by: -0.16) }

        private func rotate(by radians: Float) {
            azimuth = min(1.42, max(0.10, azimuth + radians))
            frameCamera()
        }

        private func wallHeight(_ room: RoomSpec) -> Float {
            max(0.10, min(0.70, meters(room.heightMM)))
        }

        private func meters(_ mm: Int) -> Float { Float(mm) / 1_000 }

        private func centerX(_ rect: RectMM) -> Float { meters(rect.xMM) + meters(rect.widthMM) / 2 }

        // Increasing plan Z goes up on the floor plan and away from the preview camera.
        private func worldZ(_ mm: Int) -> Float { -meters(mm) }

        private func worldCenterZ(_ rect: RectMM) -> Float { worldZ(rect.zMM) - meters(rect.depthMM) / 2 }

        private func valid(_ spans: [Float]) -> Bool { spans.allSatisfy { $0 > 0 && $0 <= 100 } }
    }
}
