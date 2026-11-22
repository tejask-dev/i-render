# RoomProof contract v1 (frozen worker boundary)

JSON camelCase. Swift public structs Codable/Equatable, mutable properties, public memberwise initializers. Unknown JSON fields may be ignored. Dates are ISO8601 strings. Numeric geometry = integer mm; money = integer CAD cents. Display conversions are UI-only.

## Models
RectMM: xMM,zMM,widthMM,depthMM (axis-aligned lower-left origin).
KeptItem: id,label,widthMM,depthMM,heightMM,centerXMM,centerZMM,quarterTurns.
RoomSpec: widthMM,depthMM,heightMM,doorReserve:RectMM,kept:KeptItem,source:String,confirmed:Bool,otherObjectsCleared:Bool.
DesignBrief: budgetCents:Int,preferClosedStorage:Bool,style:String,chairPullbackMM:Int,notes:String.
OfferSnapshot: id,retailer,sku,name,category (desk|chair), widthMM:Int?,depthMM:Int?,heightMM:Int?,priceCents:Int?,currency,stock(in_stock|out_of_stock|unknown),stockScope,closedStorage:Bool,url,evidenceQuote,checkedAt,provenance(live|saved|sample),dimensionConflict:Bool,priceConditions:String.
LayoutPlan: deskOfferID,chairOfferID,centerXMM:Int,centerZMM:Int,quarterTurns:Int,subtotalCents:Int,provisional:Bool,reasons:[String]. Center is desk center. q0 front+Z; q1 front-X; q2 front-Z; q3 front+X. Chair centered in front, entirely outside desk; pullback rectangle extends behind chair. Room X right/Z forward; origin interior corner. q1/3 swap footprint width/depth. Touching edges do not overlap. Retained item uses same orientation convention.
PlanResult: plan:LayoutPlan?,issues:[String].

## Swift API owned by geometry worker
Planner.solve(room:RoomSpec,brief:DesignBrief,offers:[OfferSnapshot],previous:LayoutPlan? = nil) -> PlanResult.
Planner.validate(room:RoomSpec,brief:DesignBrief,offers:[OfferSnapshot],plan:LayoutPlan) -> [String] (empty means valid).
Planner.repair(room:RoomSpec,brief:DesignBrief,offers:[OfferSnapshot],proposed:LayoutPlan) -> PlanResult (nearest valid pose using selected pair).
Planner.footprints(plan:LayoutPlan,brief:DesignBrief,offers:[OfferSnapshot]) -> [String:RectMM] keys desk,chair,pullback; helpers return empty for unknown dimensions.
RectMM center can be computed. Solver all four pair combos, four wallflush orientations,100mm increments+endpoints. Hardvalidity first then storage preference then price then stable placement. Preserve previous pose if feasible; otherwise distance then fixed tie. No-fit wording: No checked layout found. Validate bounds/positive dims/room confirmation/otherObjectsCleared/stockunavailable/currency/finite budgets/missingdimensions. Saved/unknown stock makes plan provisional; sample remains explicit at UI.

## HTTP API owned by Claude backend worker
All endpoints bearer ROOMPROOF_PAIR_TOKEN, configured at launch; failclosed if absent. GET /api/roomproof/health -> {contractVersion:1,geminiConfigured:Bool,tinyfishConfigured:Bool} (configuration is not live validation).
POST /api/roomproof/analyze JSON {requestId,revision:Int,text:String,room:RoomSpec,brief:DesignBrief,imageBase64:String?} -> {contractVersion:1,requestId,revision,preferClosedStorage:Bool,style:String,questions:[String],summary:String,provider:"gemini",model:String}. Do not alter room/budget or mark confirmation. Limit text4000chars,image10MBdecoded; reuse read_image. Gemini25sec deadline, no fabricated offline success.
POST /api/roomproof/sourcing JSON {requestId,revision:Int,storeLocation:String} ->202 {jobId,requestId,revision}. Exact catalog URLs only; no client-controlled URL fetching. Dedupe requestId+payload; conflicting replay409. GET /api/roomproof/jobs/{id} -> {contractVersion:1,jobId,requestId,revision,state:queued|running|partial|done|failed,progress:[String],offers:[OfferSnapshot],errors:[String]}. Bounded memory retention30min, concurrency2, partial good results retained. No automatic client retry after unknownjob; user refresh.
Errors {code,message,retryable}. Credentials fromenv only. GEMINI_MODEL defaultgemini-3.5-flash-lite. TINYFISH_API_KEY. ROOMPROOF_PAIR_TOKEN. No env values inlogs. Use httpx trust_env=False. TinyFish POST https://agent.tinyfish.ai/v1/automation/run-sse with X-API-Key and {url,goal,output_schema}; terminalCOMPLETE.status COMPLETED and .result. Keep run IDs internally, don't expose signed streaming URLs. Tests mock providertransport and use contractfixture. Never live API calls from worker.

## Native persistence
ProjectDocument (coordinator owns): schemaVersion1,id,title,revision,room,brief,offers,plan?,updatedAt. Atomic localJSON. Catalog fixture is provenance saved; authored test fixture sample. User-confirmed actual room required for positive claims. Runtime project photo/state excluded fromGit.
