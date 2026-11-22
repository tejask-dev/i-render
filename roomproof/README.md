# RoomProof

A native iPhone workspace planner: keep one existing item, choose a desk and chair within a CAD merchandise budget, check the modeled floor space, and export the measurements and retailer evidence. The regular iPhone 16 uses manual measurements. Photos only inform style.

## Open and run

Open `iOS/RoomProof.xcodeproj` in Xcode. Select the RoomProof scheme and a simulator, or select your own development team and a connected iPhone with Developer Mode enabled. The project requires iOS 18 or later. `iOS/project.yml` is the XcodeGen source if regeneration is needed; the generated project is included.

For Gemini and retailer sourcing, run `Start RoomProof.command` at the repository root. Its private settings file is `.var/roomproof-config.json`; it is ignored by Git. Add provider keys there, set the Mac's private-hotspot IP as `ROOMPROOF_HOST`, and restart. Enter `http://<mac-private-ip>:8767` and only the pairing token in the app's Connect to Mac screen. Keep the phone and Mac on that private network. Provider keys never belong in the iOS app.

Without provider setup, the local planner and PDF still work using clearly labeled saved catalog data. They do not demonstrate a live sponsor integration. Start with measured room dimensions, door reserve and a retained item, confirm both room switches, then use Brief and Plan. Invalid moves remain previews until explicitly repaired or undone.

## Focused checks

From the repository root:

```sh
swift test --package-path roomproof/RoomProofCore
.venv/bin/python -B -m eval.check_roomproof
```

The Python check mocks all provider traffic. Native hosted checks cover the budget switch, invalid placement/repair, save/reopen, saved evidence provenance, private HTTP addresses and PDF contents:

```sh
xcodebuild -project roomproof/iOS/RoomProof.xcodeproj -scheme RoomProof \
  -destination 'platform=iOS Simulator,name=iPhone 17e' \
  -derivedDataPath /private/tmp/RoomProofBuild \
  -parallel-testing-enabled NO CODE_SIGN_IDENTITY=- ENABLE_DEBUG_DYLIB=NO test
```

Use an installed simulator name. Keep DerivedData outside `~/Documents` if the simulator loader stalls on protected build paths. No development certificate is needed for this simulator command.

The deterministic core owns integer millimetres and CAD cents. Gemini proposes qualitative preferences for confirmation. TinyFish checks only four pinned Canadian product pages; missing or ambiguous evidence stays unknown. Source timestamps and live/saved/sample labels remain visible. The fit check covers modeled floor footprints and reserves; it does not establish delivery access, ergonomics or current stock.

Build decisions, current gaps and the three-minute rehearsal are in `docs/roomproof/` at the repository root. Do not submit or publish from this branch without authorization.
