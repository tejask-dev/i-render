# RoomProof implementation brief

Approved 2026-11-21. Native iPhone workspace procurement for adult professionals. Current user device is **iPhone 16 (non-Pro)**; manual measurements are the primary path. Optional RoomPlan is capability-gated, never simulated as live. Preserve I, Render on main; all new work on codex/roomproof. No event submission, social publication, purchases or roster changes.

## Complete vertical slice
Create/resume -> enter/confirm rectangular room, door reserve and one retained item -> text brief/optional nonpersonal photo -> Gemini preferences confirmed by user -> actual IKEA/JYSK sourcing -> local dimension/budget solver -> editable 3D/top-down plan -> budget change and nearest valid repair -> atomic save/reopen -> PDF Fit Sheet with sources and qualifications.

Four initial Canadian SKUs: IKEA LAGKAPTEN/ALEX desk S99521435; RENBERGET chair 40611094; JYSK VANDBORG desk; GUSUM chair. Mixed retailers permitted. CAD merchandise subtotal excludes tax/delivery. Catalog captures are labeled saved, not live. Unknown availability is provisional; unavailable offers excluded; missing/conflicting dimensions cannot establish fit. A sample fixture is never a sponsor integration.

## Technical decisions
SwiftUI iOS18+, Swift5 language mode; RealityKit category models at actual external dimensions; local Swift package for one geometry engine and Codable models. Display cm but store integer mm. No geometry or money from an LLM. Chair stays fully outside desk plus editable pullback (default600mm). Plan is floor-footprint/door-reserve proof only, not delivery, ergonomics or assembly guarantee.

Mac FastAPI service separate from old app, port8767; keys in ignored local env, pairing bearer token in iPhone Keychain, private-hotspot transport. Gemini3.5 Flash-Lite structured text/optional-image input; actual model verified by preflight. TinyFish two concurrent read-only browser jobs for exact variants/price/dimensions/stock/source evidence; 90sec attempt, maxone transient retry. User changes are revision guarded. Phone persists final snapshots and plan; failures keep old results with original timestamps.

## Team and acceptance
Run2530376a-a3b0-4a64-9cfd-93b024ed57dc. Coordinator owns contracts, Xcode, SwiftUI, integration/live checks. Claude owns backend/roomproof and adapter tests. Native worker owns roomproof/RoomProofCore. Workers do not delegate or edit outside scope. Shared contract+fixtures committed before launch. Fresh external read-only reviewer after integration; source must remain stable during review.

First gates: app builds/installs, phone reaches private backend, genuine Gemini response, genuine TinyFish result. Local core proceeds with labeled fixtures if credentials/device unavailable; those gates remain incomplete. Focused geometry/contract tests, one physical end-to-end rehearsal and offline recovery. Goal is not complete without actual provider and physical evidence. Feature freeze07:30 Toronto Nov22, event08:50. No submission.
