import SwiftUI
import RoomProofCore

struct FloorPlanView: View {
    @EnvironmentObject var store: ProjectStore
    @State private var dragOrigin: (Int, Int)?
    var body: some View {
        GeometryReader { geo in
            let room = store.project.room
            let scale = min((geo.size.width - 44) / CGFloat(max(room.widthMM, 1)), (geo.size.height - 44) / CGFloat(max(room.depthMM, 1)))
            let left = (geo.size.width - CGFloat(room.widthMM) * scale) / 2
            let top = (geo.size.height - CGFloat(room.depthMM) * scale) / 2
            ZStack(alignment: .topLeading) {
                Rectangle().fill(.white).overlay(Rectangle().stroke(Color.gray.opacity(0.45), lineWidth: 2))
                    .frame(width: CGFloat(max(room.widthMM, 1)) * scale, height: CGFloat(max(room.depthMM, 1)) * scale).offset(x: left, y: top)
                footprint(room.doorReserve, label: "DOOR", color: .orange, scale: scale, left: left, top: top, depth: room.depthMM)
                let kept = room.kept
                let kw = kept.quarterTurns % 2 == 0 ? kept.widthMM : kept.depthMM
                let kd = kept.quarterTurns % 2 == 0 ? kept.depthMM : kept.widthMM
                footprint(RectMM(xMM: kept.centerXMM - kw / 2, zMM: kept.centerZMM - kd / 2, widthMM: kw, depthMM: kd), label: kept.label, color: .gray, scale: scale, left: left, top: top, depth: room.depthMM)
                if let plan = store.activePlan {
                    let shapes = Planner.footprints(plan: plan, brief: store.project.brief, offers: store.project.offers)
                    ForEach(["pullback", "desk", "chair"], id: \.self) { key in
                        if let rect = shapes[key] {
                            footprint(rect, label: key.uppercased(), color: !store.activeIssues.isEmpty ? .red : key == "pullback" ? .mint : .teal, scale: scale, left: left, top: top, depth: room.depthMM)
                        }
                    }
                }
                Text("0,0").font(.caption2).foregroundStyle(.secondary).position(x: left + 5, y: top + CGFloat(room.depthMM) * scale + 12)
                Text("\(room.widthMM / 10) cm").font(.caption2).foregroundStyle(.secondary).position(x: geo.size.width / 2, y: top - 12)
            }
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 8).onChanged { value in
                guard let plan = store.activePlan, scale > 0 else { return }
                if dragOrigin == nil { dragOrigin = (plan.centerXMM, plan.centerZMM) }
                guard let origin = dragOrigin else { return }
                let x = Double(origin.0) + Double(value.translation.width / scale)
                let z = Double(origin.1) - Double(value.translation.height / scale)
                store.previewMove(x: Int((x / 50).rounded()) * 50, z: Int((z / 50).rounded()) * 50)
            }.onEnded { _ in store.finishMove(); dragOrigin = nil })
            .accessibilityLabel("Top-down room plan. Door reserve, retained item and workstation. Use movement buttons below as an alternative to dragging.")
        }.padding(4)
    }
    private func footprint(_ rect: RectMM, label: String, color: Color, scale: CGFloat, left: CGFloat, top: CGFloat, depth: Int) -> some View {
        RoundedRectangle(cornerRadius: 3).fill(color.opacity(0.25)).overlay(RoundedRectangle(cornerRadius: 3).stroke(color, lineWidth: 1.5))
            .overlay(Text(label).font(.system(size: 9, weight: .semibold)).lineLimit(1).minimumScaleFactor(0.5).padding(3))
            .frame(width: CGFloat(max(0, rect.widthMM)) * scale, height: CGFloat(max(0, rect.depthMM)) * scale)
            .offset(x: left + CGFloat(rect.xMM) * scale, y: top + CGFloat(depth - rect.zMM - rect.depthMM) * scale)
    }
}
