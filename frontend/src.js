import "@fontsource-variable/bricolage-grotesque/wght.css";
import "@fontsource-variable/dm-sans/wght.css";
import "./style.css";
import { spokenCentimeters, spokenVibe } from "./dictation.js";
import {
  icon,
  esc,
  pretty,
  drop,
  examples,
  exampleCards,
  actionLabels,
  scales,
  sameOriginURL,
  request,
  post,
  multipart,
} from "./ui.js";

const app = document.getElementById("app");
const defaults = () => ({
  stage: "home",
  slot: 0,
  editing: false,
  brief: {
    project_name: "",
    scale: "desktop",
    approx_size_cm: 20,
    vibe: [],
    adventure_aura: "",
    must_do: [],
    user_notes: "",
  },
  items: {},
  providers: { sketch: "local", drawer: "local" },
  excluded: new Set(),
  hits: [],
  error: "",
  memoryQuery: "",
  memoryHits: [],
  busy: "",
  selectedPart: null,
});
let s = defaults(),
  config = { templates: [], salvage_keys: [], vision_available: false },
  configProblem = "",
  viewer,
  viewGeneration = 0,
  recognition,
  recording,
  camera;
const steps = ["Brief", "Sketch", "Model", "Drawer", "Plan"];
const ranks = {
  interview: 0,
  confirm: 0,
  sketch: 1,
  model: 2,
  drawer: 3,
  inventory: 3,
  result: 4,
};
const voiceCapable = Boolean(window.speechSynthesis);
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let voiceOn = voiceCapable;
const $ = (selector) => app.querySelector(selector);
const btn = (label, act, cls = "primary", glyph = "arrow-right") =>
  `<button type="button" class="${cls}" data-action="${act}">${esc(label)}${glyph ? icon(glyph) : ""}</button>`;
const presentedSource = (source) =>
  ({
    example: "Example sketch",
    manual: "Manually entered",
    local: "On-device vision",
    gemini: "Gemini vision",
    cached_local: "Saved on-device recognition",
    cached_gemini: "Saved Gemini recognition",
  })[source] || "Server result";
const savedIndex = () => {
  try {
    return JSON.parse(localStorage.getItem("irender-projects") || "[]").filter(
      (p) => typeof p.id === "string",
    );
  } catch {
    return [];
  }
};
const explicitMemory = (hit) =>
  `<li><span class="source-tag">${hit.seeded ? "Example memory" : "Saved project"}</span><strong>${hit.project_id ? `<a href="/project/${encodeURIComponent(hit.project_id)}">${esc(hit.project_name)}</a>` : esc(hit.project_name)}</strong><p>${esc(hit.note || pretty(hit.outcome))}</p></li>`;
function say(line) {
  if (voiceOn && voiceCapable) {
    speechSynthesis.cancel();
    const voice = new SpeechSynthesisUtterance(line);
    const localVoice = speechSynthesis
      .getVoices()
      .find((v) => v.localService && v.lang.startsWith("en"));
    if (localVoice) voice.voice = localVoice;
    voice.rate = 1;
    voice.pitch = 1.08;
    speechSynthesis.speak(voice);
  }
}
function message(text) {
  const el = $("#notice");
  if (el) {
    el.textContent = text;
    el.hidden = !text;
  }
}
function clearDraft() {
  if (s.photoURL) URL.revokeObjectURL(s.photoURL);
  if (s.sketchURL) URL.revokeObjectURL(s.sketchURL);
  s = defaults();
}
function goto(stage) {
  s.stage = stage;
  s.error = "";
  render();
  requestAnimationFrame(() =>
    document.querySelector("main h1")?.focus({ preventScroll: true }),
  );
  window.scrollTo({ top: 0, behavior: "instant" });
}
function setUrl(hash) {
  history.replaceState(null, "", hash ? "/" + hash : "/");
}
function capture() {
  if (s.stage !== "interview" && s.stage !== "confirm") return;
  if ($("#name")) s.brief.project_name = $("#name").value.trim();
  if ($("#size") && Number.isFinite($("#size").valueAsNumber))
    s.brief.approx_size_cm = $("#size").valueAsNumber;
  if ($("#vibe"))
    s.brief.vibe = $("#vibe")
      .value.split(/[,;\s]+/)
      .map((a) => a.trim())
      .filter(Boolean);
  if ($("#adventure")) s.brief.adventure_aura = $("#adventure").value.trim();
}
function chooseExample(id) {
  const e = examples.find((e) => e.id === id);
  if (!e) return;
  if (s.stage === "sketch") {
    runSketch(id);
    return;
  }
  clearDraft();
  s.example = id;
  s.brief.project_name = e.name;
  s.brief.adventure_aura = e.adventure;
  s.brief.must_do = [...e.actions];
  s.brief.vibe = [...e.vibes];
  goto("interview");
  say(question());
}
function title(text) {
  return `<h1 tabindex="-1">${esc(text)}</h1>`;
}
function toolHead(eyebrow, heading, copy = "") {
  return `<div class="section-heading"><span class="eyebrow"><i></i>${esc(eyebrow)}</span>${title(heading)}${copy ? `<p>${esc(copy)}</p>` : ""}</div>`;
}
function progress() {
  const n = ranks[s.stage];
  if (n === undefined) return "";
  return `<ol class="progress" aria-label="Build progress">${steps.map((step, i) => `<li class="${i === n ? "current" : i < n ? "done" : ""}" ${i === n ? 'aria-current="step"' : ""}><span>${i < n ? icon("check") : i + 1}</span>${step}</li>`).join("")}</ol>`;
}
function home() {
  return `<section class="hero"><div class="hero-content"><div class="eyebrow"><i></i>Robot workshop</div><h1 tabindex="-1">Build a robot<br>with <em>Rendi.</em></h1><p>Turn a sketch and the parts in your junk drawer into a 3D robot and a build plan.</p><div class="actions">${btn("Start a build", "start")}${btn("Project notebook", "notebook", "secondary", "book-open")}</div></div><div class="hero-art"><img src="/rendi-workshop.webp" alt="Rendi, a turquoise droplet robot, waving from a workbench covered in sketches and spare parts."></div></section><section class="starter-section"><div class="row-title"><div><span class="eyebrow"><i></i>Sketchbook</span><h2>Start with a sketch</h2></div><span class="hint">Choose a starter robot to make your own.</span></div><div class="starters">${exampleCards("Start with")}</div></section>`;
}
const questions = [
  "How big is your robot?",
  "What’s its vibe?",
  "What adventure does it go on?",
];
function question() {
  return questions[s.slot] || "Did I get that right?";
}
const localDictation = () =>
  config.local_voice_available &&
  window.MediaRecorder &&
  navigator.mediaDevices?.getUserMedia;
function speechTools() {
  let label, copy;
  if (localDictation()) {
    label = "On-device dictation";
    copy = "Tap to record, then tap to stop. Audio is transcribed on this Mac.";
  } else if (Recognition) {
    label = "Dictate answer";
    copy = "Your browser may send audio off this Mac for transcription. You can also type your answer.";
  } else
    return '<div class="speech-tools"><small>Type your answers. Voice input is unavailable in this browser.</small></div>';
  return `<div class="speech-tools"><button type="button" class="quiet" data-action="dictate">${icon("mic")} <span>${label}</span></button><small>${copy}</small></div>`;
}
function interview() {
  const b = s.brief;
  const blocks = [
    `<div class="pills" role="group" aria-label="Robot scale">${Object.entries(
      scales,
    )
      .map(
        ([v, [name]]) =>
          `<button class="choice" type="button" data-scale="${v}" aria-pressed="${b.scale === v}">${name}</button>`,
      )
      .join(
        "",
      )}</div><div class="form-pair"><label>Approximate size (cm)<input id="size" type="number" min="3" max="150" step="1" required value="${esc(b.approx_size_cm)}"></label><label>Working title <span>(optional)</span><input id="name" maxlength="60" placeholder="e.g. Pocket Rover" value="${esc(b.project_name)}"></label></div>`,
    `<label>One to three words<input id="vibe" required maxlength="90" placeholder="Curious, playful, scrappy" value="${esc(b.vibe.join(", "))}"></label><div class="pills" aria-label="Suggested words">${["curious", "playful", "scrappy", "retro", "gentle", "chaotic"].map((v) => `<button type="button" class="choice" data-vibe="${v}" aria-pressed="${b.vibe.includes(v)}">${v}</button>`).join("")}</div>`,
    `<label>Adventure<textarea id="adventure" required maxlength="400" rows="2" placeholder="It rolls across my desk to deliver a tiny note.">${esc(b.adventure_aura)}</textarea></label><fieldset><legend>What should it do?</legend><div class="pills">${Object.entries(
      actionLabels,
    )
      .map(
        ([v, label]) =>
          `<button type="button" class="choice" data-function="${v}" aria-pressed="${b.must_do.includes(v)}">${esc(label)}</button>`,
      )
      .join("")}</div></fieldset>`,
  ];
  return `<div class="interview-layout"><aside class="companion"><img src="/rendi-workshop.webp" alt="Rendi in the workshop"><div><span>${drop} Rendi</span><small>Your build companion</small></div></aside><div class="card form-card"><span class="eyebrow"><i></i>Project brief · ${s.slot + 1} of 3</span>${title(question())}<p>${["Palm-sized or floor-roaming? Let’s give it room to move.", "Give it a little personality.", "Tell me what it does when nobody’s watching."][s.slot]}</p><form id="interview-form">${blocks[s.slot]}${speechTools()}<div class="actions"><button class="primary" type="submit">${s.editing ? "Update brief" : s.slot === 2 ? "Review brief" : "Continue"} ${icon("arrow-right")}</button>${s.slot > 0 && !s.editing ? btn("Back", "previous", "text-btn", "") : ""}</div></form>${s.hits.length ? `<div class="memory-note">${icon("book-open")}<div><strong>Rendi remembers ${esc(s.hits[0].project_name)}</strong><p>${esc(s.hits[0].note)} · ${s.hits[0].seeded ? "example memory" : "saved project"}</p></div></div>` : ""}</div></div>`;
}
function confirmBrief() {
  const b = s.brief;
  return `<div class="narrow">${toolHead("Project brief", "Did I get that right?", "Change any answer before we move to your sketch.")}<form id="confirm-form" class="card form-card"><label>Project name<input id="name" maxlength="60" required value="${esc(b.project_name)}"></label><dl class="summary">${[
    ["Scale", pretty(b.scale) + " · " + b.approx_size_cm + " cm"],
    ["Vibe", b.vibe.join(", ")],
    [
      "Adventure",
      b.adventure_aura +
        " · " +
        b.must_do.map((k) => actionLabels[k]).join(", "),
    ],
  ]
    .map(
      ([k, v], i) =>
        `<div><dt>${k}</dt><dd>${esc(v)}</dd><button type="button" class="quiet" data-edit="${i}" aria-label="Edit ${k}">${icon("pencil")}</button></div>`,
    )
    .join(
      "",
    )}</dl>${s.hits.length ? `<div class="memory-note">${icon("book-open")}<div><strong>${s.hits[0].seeded ? "Example memory" : "From your notebook"} · ${esc(s.hits[0].project_name)}</strong><p>${esc(s.hits[0].note)}</p></div></div>` : ""}<button class="primary" type="submit">Confirm brief ${icon("check")}</button></form></div>`;
}
function availableProviders() {
  return config.vision_providers || {
    local: config.vision_source === "local",
    gemini: config.vision_source === "gemini",
  };
}
const applePhoto = (file) =>
  /image\/hei[cf]/i.test(file.type) || /\.hei[cf]$/i.test(file.name);
const cameraCapable = () =>
  Boolean(Object.values(availableProviders()).some(Boolean) && navigator.mediaDevices?.getUserMedia);
function cameraTools(kind) {
  if (!cameraCapable()) return "";
  return `<button type="button" class="quiet camera-open" data-action="camera" data-kind="${kind}">${icon("focus")} <span>Use camera instead</span></button><div class="camera" id="camera-${kind}" hidden><video playsinline muted aria-label="Live camera preview"></video><small class="camera-status" role="status"></small><div class="actions"><button type="button" class="primary" data-action="camera-take" disabled>Take photo ${icon("check")}</button><button type="button" class="secondary" data-action="camera-cancel">Cancel</button></div></div>`;
}
function uploadBox(kind) {
  const sketch = kind === "sketch",
    file = sketch ? s.sketchFile : s.photo,
    preview = sketch ? s.sketchURL : s.photoURL;
  const provider = s.providers[kind],
    available = availableProviders(),
    online = Object.values(available).some(Boolean),
    canScan = Boolean(available[provider]);
  const choice = online ? `<div class="provider-picker" role="group" aria-label="Process this photo with">${[["local", "On this Mac"], ["gemini", "Gemini"]].map(([value, label]) =>
    `<button type="button" class="choice" data-provider="${value}" data-kind="${kind}" aria-pressed="${provider === value}" ${available[value] ? "" : "disabled"}>${label}${available[value] ? "" : " · offline"}</button>`
  ).join("")}</div>` : "";
  const info = !online ? "Photo recognition is offline. Use an example sketch or enter your drawer items by hand."
    : provider === "gemini" ? (sketch ? "Send this sketch and your confirmed brief to Google when you choose the button below." : "Send this drawer photo to Google when you choose the button below.")
    : canScan ? "This photo stays on this Mac." : "On-device recognition is offline. Choose Gemini to send this photo to Google.";
  const scanLabel = provider === "gemini" ? (sketch ? "Send sketch to Gemini" : "Send drawer photo to Gemini")
    : sketch ? "Build from photo" : "Identify items";
  return `<section class="upload card"><div class="upload-symbol">${icon("upload")}</div><h2>${sketch ? "Use your own sketch" : "Scan your drawer"}</h2>${choice}<p>${esc(info)}</p><label class="file-label">Choose ${sketch ? "sketch" : "drawer"} photo<input type="file" id="upload-${kind}" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif" ${online ? "" : "disabled"}></label>${cameraTools(kind)}${file ? `<div class="upload-preview">${applePhoto(file) ? icon("box") : `<img src="${esc(preview)}" alt="Selected ${kind} photo">`}<span>${esc(file.name)}</span></div>${canScan ? btn(scanLabel, "scan-" + kind, "primary", "eye") : ""}${s.error && provider === "gemini" && available.local ? btn("Retry on this Mac", "retry-local", "secondary", "") : ""}` : ""}<small>JPG, PNG, WebP or HEIC/HEIF · up to 10 MB</small></section>`;
}
function sketches() {
  return `${toolHead("Sketch input", "Show me your sketch.", "Upload a drawing or build from one of these example designs.")}<div class="input-layout">${uploadBox("sketch")}<section class="card pad"><h2>Example sketches</h2><p>${s.example ? esc(examples.find((e) => e.id === s.example).name + " is your starter. Choose it to generate the model or pick another.") : "Each example creates a real model at your chosen size."}</p><div class="starters column">${exampleCards("Build")}</div></section></div>`;
}
function modelPanel() {
  const spec = s.model.spec;
  const p =
    (s.selectedPart && spec.parts.find((p) => p.id === s.selectedPart)) ||
    spec.parts[0];
  return `<div class="model-grid"><div class="viewer" id="viewer"><span class="viewer-status">Loading 3D model…</span><button type="button" class="spin-toggle" data-spin hidden>Pause orbit</button><button type="button" class="view-fit" data-fit aria-label="Fit model">${icon("focus")}</button><span class="view-guide">${icon("move-3d")} Drag to orbit · scroll to zoom</span></div><section class="card part-panel"><span class="eyebrow"><i></i>Part inspector</span><h2>${spec.parts.length} parts</h2><div class="part-list" role="group" aria-label="Model parts">${spec.parts.map((part) => `<button type="button" class="choice" aria-pressed="${p?.id === part.id}" data-part="${esc(part.id)}">${esc(part.label)}</button>`).join("")}</div><div id="part-info" aria-live="polite"></div></section></div>`;
}
function sketchReference() {
  const url = s.model.sketch_url;
  if (!url) return "";
  return `<details class="card pad sketch-reference"><summary>Original sketch</summary><img src="${esc(sameOriginURL(url))}" alt="Original drawing used to generate this model" loading="lazy"></details>`;
}
function unresolvedNotice() {
  const unresolved = s.model.unresolved_actions || [];
  if (!unresolved.length) return "";
  return `<p class="safety"><strong>Still to design</strong> · ${esc(unresolved.map((name) => actionLabels[name] || pretty(name)).join(", "))}. The plan includes their components. Their positions in the model still need to be designed.</p>`;
}
function modelView() {
  const spec = s.model.spec;
  return `${toolHead(presentedSource(s.model.source), spec.robot_name || s.brief.project_name, "Select a part to inspect its estimated dimensions. Measure the physical parts before printing.")}${unresolvedNotice()}${modelPanel()}${sketchReference()}${Number(spec.confidence) < 0.3 ? '<p class="safety">Low confidence. Check the shapes and dimensions against your sketch before printing.</p>' : ""}<div class="bottom-row"><div class="actions">${btn("Open the drawer", "drawer")}${downloadLink("STL")}${downloadLink("GLB")}</div><details class="assumptions"><summary>Model assumptions (${spec.assumptions.length})</summary><ul>${spec.assumptions.map((a) => `<li>${esc(a)}</li>`).join("") || "<li>No model assumptions recorded.</li>"}</ul></details></div>`;
}
function downloadLink(kind) {
  const url = s.model[kind === "STL" ? "stl_url" : "glb_url"];
  return `<a class="secondary" href="${esc(sameOriginURL(url))}" download>${icon("download")} Download ${kind}</a>`;
}
function selectPart(id) {
  const part = s.model?.spec.parts.find((p) => p.id === id);
  if (!part) return;
  s.selectedPart = part.id;
  const spec = s.model.spec;
  for (const el of app.querySelectorAll("[data-part]"))
    el.setAttribute("aria-pressed", el.dataset.part === id);
  const labels = {
    box: ["L", "W", "H"],
    rounded_box: ["L", "W", "H"],
    cylinder: ["Ø", "H"],
    cone: ["Base Ø", "Top Ø", "H"],
    wheel: ["Ø", "W"],
    sphere: ["Ø"],
    arm_link: ["L", "W", "T"],
    motor_mount: ["Motor Ø"],
    antenna: ["L"],
  };
  const dims =
    part.dims_mm
      .map((v, i) =>
        `${labels[part.primitive]?.[i] || ""} ${Math.round(v * 10) / 10} mm`.trim(),
      )
      .join(" · ") ||
    (part.primitive === "servo_mount"
      ? "SG90 standard mounting profile"
      : "Fixed profile");
  const functions = spec.functions
    .filter((f) => f.parts.includes(id))
    .map((f) => f.name);
  const plan = s.plan?.plan;
  const allocations = (plan?.allocations || []).filter((unit) => unit.part_id === id);
  const donors = allocations.filter((unit) => unit.status === "drawer");
  const unfilled = allocations.filter((unit) => unit.status === "source");
  for (const box of app.querySelectorAll("[data-box-index]"))
    box.classList.toggle("matched", donors.some((unit) => unit.item_index === Number(box.dataset.boxIndex)));
  for (const row of app.querySelectorAll("[data-donor-row]"))
    row.classList.toggle("matched", plan.from_your_drawer[Number(row.dataset.donorRow)].part_ids?.includes(id) || false);
  for (const row of app.querySelectorAll("[data-source-row]"))
    row.classList.toggle("matched", plan.to_source[Number(row.dataset.sourceRow)].part_ids?.includes(id) || false);

  const info = $("#part-info");
  if (info) {
    const matched = donors.map((unit) =>
      `<p><strong>${esc(pretty(unit.need))}</strong> · <a href="#drawer-matches">${esc("Item " + (unit.item_index + 1) + " · " + unit.raw_name)}</a></p>`
    ).join("");
    const missing = unfilled.map((unit) => `<p>Still to source · ${esc(pretty(unit.need))}</p>`).join("");
    const status = plan?.allocations ? (matched + missing || "<p>No drawer component is assigned to this model part.</p>") : "";
    info.innerHTML = `<h3>${esc(part.label)}</h3><p>${esc(pretty(part.category))} · ${esc(pretty(part.primitive))}</p><dl><dt>Model dimensions</dt><dd>${esc(dims)}</dd><dt>Function</dt><dd>${esc(part.function || functions.map(pretty).join(", ") || "Unassigned")}</dd></dl>${status}`;
  }
  viewer?.select(id);
}
function drawer() {
  const keys = config.salvage_keys || [];
  return `${toolHead("Parts inventory", "What’s in your drawer?", "Scan a photo or count items by hand. An empty drawer works too.")}<div class="input-layout">${uploadBox("drawer")}<section class="card pad"><div class="split"><h2>Manual inventory</h2><span id="item-count" class="source-tag"></span></div><div class="inventory-controls">${keys.map((k) => `<div class="counter"><span>${esc(k.label)}</span><div><button type="button" data-minus="${esc(k.id)}" aria-label="Remove one ${esc(k.label)}">${icon("minus")}</button><output id="qty-${esc(k.id)}">${s.items[k.id] || 0}</output><button type="button" data-plus="${esc(k.id)}" aria-label="Add one ${esc(k.label)}">${icon("plus")}</button></div></div>`).join("")}</div><div class="actions">${btn("Use manual inventory", "manual", "primary", "check")}</div></section></div>`;
}
function tally() {
  const count = Object.values(s.items).reduce((a, b) => a + b, 0);
  if ($("#item-count")) $("#item-count").textContent = count + " / 15 items";
  for (const el of app.querySelectorAll("[data-minus]"))
    el.disabled = !(s.items[el.dataset.minus] > 0);
  for (const el of app.querySelectorAll("[data-plus]"))
    el.disabled = count >= 15;
}
const unsafeLabels = new Set([
  "microwave",
  "crt_tv_monitor",
  "disposable_camera",
]);
const heldOut = (item) =>
  Boolean(item.blocked) ||
  unsafeLabels.has(item.label) ||
  /swollen|bulging|puffed/i.test(item.condition_note || "");
function annotation() {
  const items = s.inv?.inventory?.items || [];
  const photo = s.inv?.inventory?.photo_url || s.inv?.photo_url;
  const url = photo ? sameOriginURL(photo) : s.photoURL;
  if (!url || s.inv.source === "manual") return "";
  return `<div class="photo-map"><img src="${esc(url)}" alt="Your drawer with numbered detections">${items
    .map((item, i) => {
      if (item.box_2d?.length !== 4) return "";
      const clamp = (v) => Math.max(0, Math.min(1000, Number(v) || 0)) / 10;
      const [y, x, Y, X] = item.box_2d.map(clamp);
      return `<span class="box-over${s.excluded.has(i) || item.user_excluded ? " excluded-box" : ""}" data-box-index="${i}" style="left:${x}%;top:${y}%;width:${Math.max(0, X - x)}%;height:${Math.max(0, Y - y)}%"><b>${i + 1}</b></span>`;
    })
    .join("")}</div>`;
}
function inventory() {
  const items = s.inv.inventory.items;
  const row = (item, i) => {
    const name = item.raw_name || pretty(item.label), excluded = s.excluded.has(i);
    return `<li><strong>${esc(name)}</strong> ${heldOut(item) ? '<span class="danger">Do not open or salvage</span>' : ""}<small>${esc(item.condition_note || (item.label === "other" ? "Contents unknown" : "Recorded in inventory"))}</small>${heldOut(item) ? "" : `<button type="button" class="choice exclude-item" data-exclude="${i}" aria-label="${esc((excluded ? "Restore " : "Exclude ") + name)}">${excluded ? "Restore item" : "Exclude item"}</button>`}</li>`;
  };
  return `${toolHead(presentedSource(s.inv.source), "Your drawer inventory", items.length ? "Exclude anything you don’t recognize before matching parts." : "Your drawer is empty. We’ll list the components to source.")}<div class="inventory-review">${annotation()}<section class="card pad"><h2>${items.length} ${items.length === 1 ? "item" : "items"}</h2><ol class="detected">${items.map(row).join("")}</ol><div class="actions">${btn("Match my parts", "match")}${btn("Change inventory", "drawer", "secondary", "")}</div></section></div>`;
}
function briefDetails() {
  const b = s.brief;
  return `<details class="card pad"><summary>Idea and model assumptions</summary><dl class="compact"><dt>Scale</dt><dd>${esc(b.scale)} · ${esc(b.approx_size_cm)} cm</dd><dt>Vibe</dt><dd>${esc(b.vibe.join(", "))}</dd><dt>Adventure</dt><dd>${esc(b.adventure_aura)}</dd><dt>Functions</dt><dd>${esc(s.model.spec.functions.map((f) => pretty(f.name)).join(", "))}</dd></dl><ul>${s.model.spec.assumptions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></details>`;
}
function result() {
  const p = s.plan.plan,
    got = p.from_your_drawer,
    missing = p.to_source,
    warnings = Array.from(
      new Set([
        ...(p.safety_notes || []),
        ...(s.inv?.inventory?.items || [])
          .filter((item) => heldOut(item) && !item.user_excluded)
          .map(
            (it) =>
              "Leave " +
              (it.raw_name || pretty(it.label)) +
              " intact. Do not open or reuse its parts.",
          ),
      ]),
    );
  const candidateCount = got.reduce((sum, row) => sum + row.qty, 0);
  const requiredCount = candidateCount + missing.reduce((sum, row) => sum + row.qty, 0);
  const allocationContext = (row) => {
    const places = (row.part_ids || []).map((id) => s.model.spec.parts.find((part) => part.id === id)?.label).filter(Boolean);
    if (places.length) return `<small>Model · ${esc(places.join(", "))}</small>`;
    if (row.functions?.length) return `<small>For ${esc(row.functions.map((name) => actionLabels[name] || pretty(name)).join(", "))} · mount unspecified</small>`;
    return "";
  };
  const donorRows = got.map((row, i) => {
    const item = s.inv.inventory.items[row.item_index];
    const name = item?.raw_name || pretty(row.source);
    const donor = Number.isInteger(row.item_index) ? `Item ${row.item_index + 1} · ${name}` : name;
    return `<details class="part-row" data-donor-row="${i}"><summary><b>${esc(pretty(row.need))} ×${esc(row.qty)}</b><span>${esc(donor)}</span></summary>${allocationContext(row)}<p>${esc(row.how)}</p>${row.tools?.length ? `<small>Tools · ${esc(row.tools.join(", "))}</small>` : ""}${row.substitution ? `<p>Substitution · ${esc(row.substitution)}</p>` : ""}</details>`;
  }).join("");
  const excludedNames = s.inv.inventory.items.filter((item, i) => s.excluded.has(i) || item.user_excluded)
    .map((item) => item.raw_name || pretty(item.label));
  const photo = annotation();
  const drawerPanel = `<section class="card pad" id="drawer-matches"><span class="eyebrow"><i></i>Salvage</span><h2>From your drawer</h2>${photo}${donorRows || "<p>No matching parts found.</p>"}${excludedNames.length ? `<p><small>Left out of the match · ${esc(excludedNames.join(", "))}</small></p>` : ""}</section>`;
  const sourcePanel = `<section class="card pad"><span class="eyebrow"><i></i>Parts list</span><h2>Still to source</h2>${missing.map((r, i) => `<div class="part-row" data-source-row="${i}"><b>${esc(pretty(r.need))} ×${esc(r.qty)}</b><p>${esc(r.suggestion)}</p>${allocationContext(r)}</div>`).join("") || (requiredCount ? "<p>Your drawer has candidates for every required component.</p>" : "<p>No component requirements have been mapped.</p>")}</section>`;
  const score = `<div class="score"><strong>${esc(p.drawer_score)}<small>%</small></strong><div><h2>${candidateCount} of ${requiredCount} required components have drawer candidates.</h2><span>Check their fit and electrical ratings before use.</span></div></div>`;
  const notes = warnings.length ? `<aside class="safety">${icon("triangle-alert")}<div><strong>Safety notes</strong><ul>${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div></aside>` : "";
  const steps = `<section class="card pad"><h2>Build steps</h2><ol class="build-steps">${p.steps.map((a) => `<li>${esc(typeof a === "string" ? a : [a.title, a.detail].filter(Boolean).join(" — "))}</li>`).join("")}</ol></section>`;
  const memory = p.memory_notes?.length ? `<section class="card pad"><h2>Rendi remembers</h2>${p.memory_notes.map((a) => `<p>${esc(a)}</p>`).join("")}</section>` : "";
  return `${toolHead("Build plan", s.brief.project_name, "Model · " + presentedSource(s.model.source) + "  /  Drawer · " + presentedSource(s.inv?.source))}${unresolvedNotice()}${score}${modelPanel()}<div class="results">${drawerPanel}${sourcePanel}</div>${notes}<div class="results">${steps}<div class="stack">${sketchReference()}${briefDetails()}${memory}</div></div><div class="actions end-actions">${s.projectId ? '<span class="saved">' + icon("check") + " Saved to Rendi’s memory</span>" : btn("Save to Rendi’s memory", "save", "primary", "save")}${downloadLink("STL")}${downloadLink("GLB")}${btn("Start a new idea", "new", "text-btn", "arrow-right")}</div>`;
}
function notebook() {
  const index = savedIndex();
  return `${toolHead("Project notebook", "Rendi’s notebook", "Search past builds for parts, ideas or lessons to use again.")}<div class="input-layout"><section class="card pad"><h2>Find a memory</h2><form id="memory-form"><label>Search by project, part or action<input name="q" placeholder="Try wheels or glow" value="${esc(s.memoryQuery)}" required maxlength="100"></label><button class="primary">${icon("search")} Search memories</button></form>${s.didSearch ? `<ul class="memory-results">${s.memoryHits.map(explicitMemory).join("") || "<li>No matching memories yet.</li>"}</ul>` : ""}</section><section class="card pad"><h2>Saved on this browser</h2>${index.length ? `<ul class="saved-list">${index.map((p) => `<li><a href="/project/${encodeURIComponent(p.id)}">${icon("box")} ${esc(p.name)} ${icon("arrow-up-right")}</a></li>`).join("")}</ul>` : "<p>Save a completed plan to reopen it here.</p>"}${s.returnStage ? btn("Back to build", "resume", "secondary", "arrow-left") : btn("Start a build", "start", "secondary", "arrow-right")}</section></div>`;
}
function render() {
  cancelRecording();
  closeCamera();
  viewGeneration++;
  const generation = viewGeneration;
  viewer?.dispose();
  viewer = null;
  if (recognition) {
    recognition.onend = null;
    recognition.onerror = null;
    recognition.abort();
    recognition = null;
  }
  const outer = {
    home,
    interview,
    confirm: confirmBrief,
    sketch: sketches,
    model: modelView,
    drawer,
    inventory,
    result,
    notebook,
  };
  app.innerHTML = `<header><div class="topbar"><button class="brand" data-action="home" aria-label="I, Render home">${drop}<span>I, Render<span class="brand-period">.</span></span></button><nav aria-label="Main"><button class="nav-btn ${s.stage !== "notebook" ? "active" : ""}" data-action="workshop">${icon("pencil-ruler")} Workshop</button><button class="nav-btn ${s.stage === "notebook" ? "active" : ""}" data-action="notebook">${icon("book-open")} Notebook</button></nav><button class="sound" data-action="voice" aria-pressed="${voiceOn}" ${voiceCapable ? "" : "disabled"}>${icon(voiceOn ? "volume-2" : "volume-x")} <span>Voice ${voiceOn ? "on" : "off"}</span></button></div></header><main id="work" tabindex="-1">${progress()}<div id="notice" role="alert" ${s.error || configProblem ? "" : "hidden"}>${esc(s.error || configProblem)}</div>${s.stage === "loading" ? toolHead("Notebook", "Opening saved build…") : outer[s.stage]()}</main><footer><div>${drop}<b>I, Render</b></div>${ranks[s.stage] !== undefined && !s.projectId ? btn("Reset build", "reset", "text-btn", "rotate-ccw") : "<span>Rendi’s robot workshop</span>"}</footer>${s.busy ? `<div class="busy" role="status"><span class="spinner"></span><strong>${esc(s.busy)}</strong></div>` : ""}`;
  if (s.stage === "model" || s.stage === "result") {
    const id = s.selectedPart || s.model.spec.parts[0]?.id;
    selectPart(id);
    const holder = $("#viewer");
    import("./viewer.js")
      .then(({ mountViewer }) => {
        if (generation !== viewGeneration) return;
        viewer = mountViewer(
          holder,
          sameOriginURL(s.model.glb_url),
          s.model.spec.parts,
          selectPart,
        );
        viewer?.select(id);
      })
      .catch(() => {
        if (generation === viewGeneration)
          holder.querySelector(".viewer-status").textContent =
            "3D preview failed. Select parts below or download the model.";
      });
  }
  if (s.stage === "drawer") tally();
}
async function job(status, work) {
  if (s.busy) return;
  s.busy = status;
  s.error = "";
  render();
  try {
    await work();
  } catch (e) {
    s.error = e.message || "Something went wrong. Please try again.";
  } finally {
    s.busy = "";
    render();
    if (s.error) $("#notice")?.scrollIntoView({ block: "center" });
  }
}
async function remember(q) {
  if (!q) return;
  try {
    s.hits = await request("/memory/search?q=" + encodeURIComponent(q));
  } catch {
    s.hits = [];
  }
}
async function runSketch(template) {
  await job(
    template
      ? "Building your dimensioned example…"
      : "Reading the sketch and building your model…",
    async () => {
      s.model = await multipart("/sketch", {
        brief_id: s.brief_id,
        ...(template ? { template } : { image: s.sketchFile, provider: s.providers.sketch }),
      });
      s.selectedPart = null;
      s.inv = null;
      s.plan = null;
      s.projectId = null;
      goto("model");
    },
  );
}
async function loadProject(id) {
  await job("Opening your saved build…", async () => {
    const project = await request("/projects/" + encodeURIComponent(id));
    clearDraft();
    s.projectId = id;
    s.brief = project.brief;
    s.model = {
      spec: project.spec,
      source: project.source,
      glb_url: project.glb_url,
      stl_url: project.stl_url,
      sketch_url: project.sketch_url,
      unresolved_actions: project.unresolved_actions,
    };
    s.inv = {
      inventory: project.inventory || { items: [] },
      source: project.inventory_source,
      photo_url: project.inventory_photo_url,
    };
    s.excluded = new Set(project.excluded_indices || []);
    s.plan = { plan: project.plan };
    goto("result");
  });
}
const answerField = () => $(["#size", "#vibe", "#adventure"][s.slot]);
function acceptTranscript(phrase, originalValue) {
  const slot = s.slot;
  if (answerField()?.value !== originalValue) {
    message("Kept the answer you typed while dictation was running.");
    return;
  }
  if (!phrase) {
    message("I didn’t hear an answer. Try again or type it below.");
    return;
  }
  if (slot === 0) {
    let scale = Object.keys(scales).find((k) =>
      phrase.toLowerCase().includes(k),
    );
    if (!scale)
      scale = /palm|hand/i.test(phrase)
        ? "handheld"
        : /desk|table/i.test(phrase)
          ? "desktop"
          : /floor|ground/i.test(phrase)
            ? "floor"
            : /wear/i.test(phrase)
              ? "wearable"
              : "";
    capture();
    const cm = spokenCentimeters(phrase);
    const scaleOnly = scale && /^(?:a |an )?(?:handheld|desktop|floor|wearable|(?:desk|table|palm|floor)[ -]sized)(?: robot)?[.!?]?$/i.test(phrase.trim());
    if (scale && (cm !== null || scaleOnly)) s.brief.scale = scale;
    if (cm !== null) s.brief.approx_size_cm = cm;
    else if (scaleOnly) s.brief.approx_size_cm = scales[scale][1];
    render();
    if (cm === null && !scaleOnly) $("#size").value = originalValue;
    message("Heard “" + phrase + "”. " +
      (cm !== null ? "Check the size before continuing." : scaleOnly
        ? "The " + scale + " preset uses " + s.brief.approx_size_cm + " cm. You can edit it before continuing."
        : "I couldn’t identify one size with units. Review the size field or enter centimeters before continuing."));
  }
  if (slot === 1)
    $("#vibe").value = spokenVibe(phrase);
  if (slot === 2) {
    $("#adventure").value = phrase;
    message("Check the adventure and select what the robot should do.");
  }
}
function cancelRecording() {
  const session = recording;
  if (!session) return;
  recording = null;
  clearTimeout(session.timer);
  if (session.recorder?.state === "recording") session.recorder.stop();
  session.stream?.getTracks().forEach((track) => track.stop());
  session.controller.abort();
}
async function deviceDictation() {
  if (recording) {
    if (recording.recorder?.state === "recording") recording.recorder.stop();
    return;
  }
  const session = { controller: new AbortController(), originalValue: answerField()?.value };
  recording = session;
  const status = (text) => {
    const label = $('[data-action="dictate"] span');
    if (label) label.textContent = text;
  };
  try {
    if (voiceCapable) speechSynthesis.cancel();
    status("Opening microphone…");
    session.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (recording !== session) {
      session.stream.getTracks().forEach((track) => track.stop());
      return;
    }
    const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
      (t) => MediaRecorder.isTypeSupported(t),
    );
    const recorder = new MediaRecorder(
      session.stream,
      mime ? { mimeType: mime } : undefined,
    );
    session.recorder = recorder;
    const chunks = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data);
    };
    recorder.onerror = () => {
      cancelRecording();
      status("On-device dictation");
      message("Recording failed. Try again or type your answer.");
    };
    recorder.onstop = async () => {
      clearTimeout(session.timer);
      session.stream.getTracks().forEach((track) => track.stop());
      if (recording !== session) return;
      status("Transcribing on this Mac…");
      try {
        const data = new FormData();
        data.append(
          "audio",
          new Blob(chunks, { type: recorder.mimeType }),
          recorder.mimeType.includes("mp4") ? "answer.m4a" : "answer.webm",
        );
        const result = await request("/transcribe", {
          method: "POST",
          body: data,
          signal: session.controller.signal,
        });
        if (recording === session) {
          recording = null;
          acceptTranscript(String(result.text || "").trim(), session.originalValue);
        }
      } catch (e) {
        if (recording === session) message(e.message);
      } finally {
        if (recording === session) recording = null;
        status("On-device dictation");
      }
    };
    recorder.start();
    status("Listening… tap to stop");
    session.timer = setTimeout(() => {
      if (recorder.state === "recording") recorder.stop();
    }, 12000);
  } catch (e) {
    if (recording === session) {
      cancelRecording();
      status("On-device dictation");
      message(
        e.name === "NotAllowedError"
          ? "Microphone permission was denied. Type your answer or enable access in the browser."
          : "The microphone could not start. You can type your answer.",
      );
    }
  }
}
function dictation() {
  if (localDictation()) {
    deviceDictation();
    return;
  }
  if (!Recognition) return;
  if (recognition) {
    recognition.stop();
    return;
  }
  const r = new Recognition();
  recognition = r;
  r.lang = "en-US";
  r.interimResults = false;
  r.continuous = false;
  const stage = s.stage,
    slot = s.slot,
    originalValue = answerField()?.value;
  const el = $('[data-action="dictate"] span');
  if (el) el.textContent = "Listening… tap to stop";
  if (voiceCapable) speechSynthesis.cancel();
  r.onresult = (e) => {
    if (recognition === r && s.stage === stage && s.slot === slot)
      acceptTranscript(e.results[0][0].transcript.trim(), originalValue);
  };
  r.onerror = (e) =>
    message(
      "Speech input " +
        (e.error === "not-allowed"
          ? "permission was denied"
          : "is unavailable") +
        ". You can type your answer.",
    );
  r.onend = () => {
    if (recognition === r) recognition = null;
    const text = $('[data-action="dictate"] span');
    if (text) text.textContent = "Dictate answer";
  };
  try {
    r.start();
  } catch {
    recognition = null;
    message("Speech input could not start. You can type your answer.");
  }
}
function acceptFile(kind, file) {
  if (
    file.size > 10 * 1024 * 1024 ||
    (!["image/jpeg", "image/png", "image/webp"].includes(file.type) &&
      !applePhoto(file))
  ) {
    message("Choose a JPG, PNG, WebP or HEIC/HEIF image under 10 MB.");
    return false;
  }
  const name = kind === "sketch" ? "sketchURL" : "photoURL";
  if (s[name]) URL.revokeObjectURL(s[name]);
  s[name] = URL.createObjectURL(file);
  s[kind === "sketch" ? "sketchFile" : "photo"] = file;
  s.providers[kind] = "local";
  s.error = "";
  render();
  return true;
}
function pickFile(input) {
  const kind = input.id === "upload-sketch" ? "sketch" : "drawer",
    file = input.files[0];
  if (!file) return;
  if (!acceptFile(kind, file)) input.value = "";
}
function stopTracks(stream) {
  stream?.getTracks().forEach((track) => {
    track.onended = null;
    track.stop();
  });
}
function closeCamera() {
  const session = camera;
  if (!session) return;
  camera = null;
  stopTracks(session.stream);
  if (session.box.isConnected) {
    const video = session.box.querySelector("video");
    video.pause();
    video.srcObject = null;
    session.box.hidden = true;
    session.opener.hidden = false;
  }
}
async function openCamera(kind) {
  const box = $("#camera-" + CSS.escape(kind)),
    opener = $('[data-action="camera"]');
  if (camera || !box || !opener || !cameraCapable()) return;
  const session = { kind, box, opener };
  camera = session;
  const video = box.querySelector("video"),
    status = box.querySelector(".camera-status"),
    take = box.querySelector('[data-action="camera-take"]');
  message("");
  take.disabled = true;
  status.textContent = "Opening camera…";
  box.hidden = false;
  opener.hidden = true;
  box.querySelector('[data-action="camera-cancel"]').focus();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
      audio: false,
    });
    if (camera !== session) {
      stopTracks(stream);
      return;
    }
    session.stream = stream;
    for (const track of stream.getTracks())
      track.onended = () => {
        if (camera !== session) return;
        closeCamera();
        message("The camera stopped. Try again or choose a photo file.");
      };
    video.srcObject = stream;
    await video.play();
    if (!video.videoWidth)
      await new Promise((ready) =>
        video.addEventListener("loadeddata", ready, { once: true }),
      );
    if (camera !== session) return;
    status.textContent =
      "Frame the " +
      kind +
      ", then take a photo. Nothing is sent until you choose to.";
    take.disabled = false;
    take.focus();
  } catch (e) {
    if (camera !== session) return;
    closeCamera();
    opener.focus();
    message(
      e.name === "NotAllowedError" || e.name === "SecurityError"
        ? "Camera permission was denied. Choose a photo file or enable access in the browser."
        : e.name === "NotFoundError" || e.name === "OverconstrainedError"
          ? "No camera was found. Choose a photo file instead."
          : "The camera could not start. Choose a photo file instead.",
    );
  }
}
function takePhoto() {
  const session = camera;
  if (!session?.stream || session.capturing) return;
  const video = session.box.querySelector("video");
  if (!video.videoWidth || !video.videoHeight) return;
  session.capturing = true;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    stopTracks(session.stream);
    video.pause();
    session.box.querySelector('[data-action="camera-take"]').disabled = true;
    session.box.querySelector(".camera-status").textContent = "Saving photo…";
    canvas.toBlob(
      (blob) => {
        if (camera !== session) return;
        closeCamera();
        if (!blob) {
          message("The photo could not be captured. Try again or choose a file.");
          return;
        }
        const file = new File(
          [blob],
          session.kind + "-camera-" + Date.now() + ".jpg",
          { type: "image/jpeg" },
        );
        if (acceptFile(session.kind, file))
          $(`[data-action="scan-${session.kind}"]`)?.focus();
      },
      "image/jpeg",
      0.9,
    );
  } catch {
    closeCamera();
    session.opener.focus();
    message("The photo could not be captured. Try again or choose a file.");
  }
}
function spokenInventory() {
  const names = (s.inv?.inventory?.items || []).map(
    (item) => item.raw_name || pretty(item.label),
  );
  if (!names.length)
    return "I didn’t spot any items in that photo. You can count them by hand.";
  const listed = names.slice(0, 4).join(", "),
    more = names.length - 4;
  return `I spotted ${names.length} ${names.length === 1 ? "item" : "items"}: ${listed}${more > 0 ? ", and " + more + " more" : ""}. Check the list before we match parts.`;
}
app.addEventListener("change", (e) => {
  if (e.target.type === "file") pickFile(e.target);
});
app.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (s.busy) return;
  const form = e.target;
  if (form.id === "interview-form") {
    capture();
    const b = s.brief;
    if (s.slot === 0) {
      if (
        !Number.isInteger(b.approx_size_cm) ||
        b.approx_size_cm < 3 ||
        b.approx_size_cm > 150
      )
        return message("Choose a size between 3 and 150 cm.");
      if (b.project_name) {
        form.querySelector("button[type=submit]").disabled = true;
        await remember(b.project_name);
        if (!form.isConnected) return;
      }
    }
    if (s.slot === 1 && (!b.vibe.length || b.vibe.length > 3))
      return message("Pick one, two or three vibe words.");
    if (s.slot === 2 && (!b.adventure_aura || !b.must_do.length))
      return message("Add an adventure and pick at least one action.");
    if (s.slot === 2) {
      if (!b.project_name)
        b.project_name =
          b.vibe[0].slice(0, 1).toUpperCase() + b.vibe[0].slice(1) + " Bot";
      form.querySelector("button[type=submit]").disabled = true;
      await remember(
        b.adventure_aura + " " + b.must_do.join(" ") + " " + b.project_name,
      );
      if (!form.isConnected) return;
    }
    if (s.editing || s.slot === 2) {
      s.editing = false;
      goto("confirm");
      const hit = s.hits[0];
      const recall = hit ? ", which reminds me of " + (hit.seeded ? "the example " : "your saved build ") + hit.project_name : "";
      say(`I’m picturing your ${b.vibe.join(", ")} robot at ${b.approx_size_cm} centimeters, ready to ${b.must_do.map((action) => actionLabels[action].toLowerCase()).join(" and ")}${recall}. Did I get that right?`);
    } else {
      s.slot++;
      goto("interview");
      say(question());
    }
  }
  if (form.id === "confirm-form") {
    capture();
    await job("Saving your brief…", async () => {
      const result = await post("/brief", s.brief);
      s.brief_id = result.brief_id;
      goto("sketch");
      say("Love it. Show me your sketch!");
    });
  }
  if (form.id === "memory-form") {
    s.memoryQuery = form.elements.q.value.trim();
    await job("Looking through Rendi’s notebook…", async () => {
      s.memoryHits = await request(
        "/memory/search?q=" + encodeURIComponent(s.memoryQuery),
      );
      s.didSearch = true;
    });
  }
});
app.addEventListener("click", async (e) => {
  const t = e.target.closest("button");
  if (!t || t.disabled || s.busy) return;
  if (t.dataset.example) {
    chooseExample(t.dataset.example);
    return;
  }
  if (t.dataset.exclude !== undefined) {
    const i = Number(t.dataset.exclude);
    if (s.excluded.has(i)) s.excluded.delete(i);
    else s.excluded.add(i);
    render();
    $(`[data-exclude="${i}"]`)?.focus();
    return;
  }
  if (t.dataset.provider) {
    s.providers[t.dataset.kind] = t.dataset.provider;
    s.error = "";
    render();
    $('[data-provider="' + t.dataset.provider + '"]')?.focus();
    return;
  }
  if (t.dataset.part) {
    selectPart(t.dataset.part);
    return;
  }
  if (t.dataset.edit !== undefined) {
    capture();
    s.editing = true;
    s.slot = Number(t.dataset.edit);
    goto("interview");
    say(question());
    return;
  }
  if (t.dataset.scale) {
    capture();
    s.brief.scale = t.dataset.scale;
    s.brief.approx_size_cm = scales[t.dataset.scale][1];
    render();
    return;
  }
  if (t.dataset.vibe) {
    capture();
    const v = t.dataset.vibe;
    const list = s.brief.vibe;
    if (!list.includes(v) && list.length >= 3)
      return message("Choose up to three words.");
    s.brief.vibe = list.includes(v)
      ? list.filter((x) => x !== v)
      : [...list, v];
    render();
    return;
  }
  if (t.dataset.function) {
    capture();
    const k = t.dataset.function,
      l = s.brief.must_do;
    s.brief.must_do = l.includes(k) ? l.filter((f) => f !== k) : [...l, k];
    render();
    return;
  }
  if (t.dataset.plus || t.dataset.minus) {
    const k = t.dataset.plus || t.dataset.minus;
    s.items[k] = (s.items[k] || 0) + (t.dataset.plus ? 1 : -1);
    $("#qty-" + CSS.escape(k)).textContent = s.items[k];
    tally();
    return;
  }
  switch (t.dataset.action) {
    case "voice":
      capture();
      voiceOn = !voiceOn;
      if (!voiceOn) speechSynthesis.cancel();
      render();
      if (voiceOn)
        say(
          s.stage === "interview"
            ? question()
            : "Hey, I’m Rendi. Let’s make a robot!",
        );
      break;
    case "dictate":
      dictation();
      break;
    case "camera":
      openCamera(t.dataset.kind);
      break;
    case "camera-take":
      takePhoto();
      break;
    case "camera-cancel": {
      const opener = camera?.opener;
      closeCamera();
      opener?.focus();
      break;
    }
    case "home":
    case "workshop":
      if (s.stage === "notebook" && s.returnStage) {
        const go = s.returnStage;
        s.returnStage = null;
        goto(go);
      } else if (s.stage === "home" || s.stage === "notebook") {
        goto("home");
      } else {
        window.scrollTo({ top: 0 });
      }
      break;
    case "resume": {
      const stage = s.returnStage || "home";
      s.returnStage = null;
      goto(stage);
      break;
    }
    case "notebook":
      if (s.stage !== "notebook") {
        capture();
        s.returnStage = s.stage !== "home" ? s.stage : null;
        goto("notebook");
      }
      break;
    case "start":
    case "new":
      clearDraft();
      setUrl("");
      goto("interview");
      say(question());
      break;
    case "reset":
      if (
        window.confirm(
          "Discard this in-progress build and return to the workshop? Saved projects will stay in the notebook.",
        )
      ) {
        clearDraft();
        setUrl("");
        goto("home");
      }
      break;
    case "previous":
      capture();
      s.slot--;
      goto("interview");
      say(question());
      break;
    case "retry-local":
      s.providers[s.stage] = "local";
      render();
      $('[data-action="scan-' + s.stage + '"]')?.click();
      break;
    case "scan-sketch":
      if (s.sketchFile) await runSketch(null);
      break;
    case "drawer":
      goto("drawer");
      break;
    case "manual":
    case "scan-drawer": {
      const manual = t.dataset.action === "manual";
      await job(
        manual ? "Sorting your drawer…" : "Identifying items in the photo…",
        async () => {
          const ids = Object.entries(s.items).flatMap(([id, n]) =>
            Array(n).fill(id),
          );
          s.inv = await multipart(
            "/junk",
            manual ? { items: JSON.stringify(ids) } : { image: s.photo, provider: s.providers.drawer },
          );
          s.excluded.clear();
          goto("inventory");
          if (!manual) say(spokenInventory());
        },
      );
      break;
    }
    case "match":
      await job("Matching parts and writing your plan…", async () => {
        s.plan = await post("/plan", {
          brief_id: s.brief_id,
          spec_id: s.model.spec_id,
          inventory_id: s.inv.inventory_id,
          excluded_indices: [...s.excluded],
        });
        goto("result");
      });
      break;
    case "save":
      await job("Saving to Rendi’s memory…", async () => {
        const { project_id: id } = await post("/projects", {
          plan_id: s.plan.plan_id,
          outcome: "planned",
        });
        s.projectId = id;
        setUrl("project/" + encodeURIComponent(id));
        try {
          localStorage.setItem(
            "irender-projects",
            JSON.stringify(
              [
                { id, name: s.brief.project_name },
                ...savedIndex().filter((p) => p.id !== id),
              ].slice(0, 80),
            ),
          );
        } catch {
          s.error =
            "Saved on the server. Bookmark this address to reopen the project.";
        }
      });
      break;
  }
});
async function boot() {
  try {
    config = await request("/config");
  } catch (e) {
    configProblem = e.message;
  }
  const match =
    location.pathname.match(/^\/project\/([^/]+)\/?$/) ||
    location.hash.match(/^#project\/(.+)$/);
  if (match) {
    s.stage = "loading";
    await loadProject(decodeURIComponent(match[1]));
    if (!s.projectId && s.stage === "loading") s.stage = "notebook";
  }
  render();
}
window.addEventListener("pagehide", cancelRecording);
window.addEventListener("pagehide", closeCamera);
window.addEventListener("hashchange", () => {
  const match = location.hash.match(/^#project\/(.+)$/);
  if (match) loadProject(decodeURIComponent(match[1]));
});
render();
boot();
