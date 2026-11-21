import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

// Exercise the real entry module with a small DOM and network fixture, without opening a browser.
const fixture = mkdtempSync(join(tmpdir(), "rendi-provider-refresh-"));
try {
  const source = readFileSync(new URL("../frontend/src.js", import.meta.url), "utf8")
    .replace(/^import "[^"\n]+";\n/gm, "")
    .replaceAll('"./voice.js"', '"./stubs.mjs"')
    .replaceAll('"./dictation.js"', '"./stubs.mjs"')
    .replaceAll('"./ui.js"', '"./stubs.mjs"');
  writeFileSync(join(fixture, "src.mjs"), source);
  writeFileSync(join(fixture, "stubs.mjs"), "export const createVoiceOutput = () => ({ say() {}, stop() {}, browserAvailable: true });\nexport const spokenCentimeters = () => null, spokenVibe = () => [];\nexport const icon = () => \"\", esc = (x) => String(x), pretty = (x) => x, drop = \"\", examples = [], exampleCards = () => \"\",\n  actionLabels = {}, scales = {}, sameOriginURL = (x) => x;\nexport const request = (path) => globalThis.api(path);\nexport const post = async () => ({}), multipart = (path, body) => globalThis.upload(path, body);");

  const el = () => ({ dataset: {}, setAttribute() {}, focus() {}, scrollIntoView() {}, textContent: "", matches: () => false });
  const handlers = {}, win = {};
  let renders = 0;
  const app = { _h: "", get innerHTML() { return this._h; }, set innerHTML(v) { this._h = v; renders++; },
    querySelector: () => el(), querySelectorAll: () => [], contains: () => false,
    addEventListener: (n, f) => (handlers[n] = f) };
  globalThis.document = { getElementById: () => app, activeElement: null, querySelector: () => el() };
  globalThis.window = { addEventListener: (n, f) => (win[n] = f), scrollTo() {}, Audio: class {}, confirm: () => true };
  globalThis.location = { pathname: "/", hash: "" };
  globalThis.history = { replaceState() {} };
  Object.defineProperty(globalThis, "navigator", { value: { mediaDevices: null }, configurable: true });
  globalThis.requestAnimationFrame = (f) => f();
  globalThis.localStorage = { getItem: () => null, setItem() {} };
  globalThis.URL.createObjectURL = () => "blob:x"; globalThis.URL.revokeObjectURL = () => {};
  const pending = [];
  globalThis.api = (path) => { assert.equal(path, "/config"); return new Promise((ok, fail) => pending.push({ ok, fail })); };
  const uploads = [];
  globalThis.upload = async (path, body) => { uploads.push([path, body]); throw new Error("offline"); };
  const cfg = (local, gemini) => ({ templates: [], salvage_keys: [], vision_available: local, vision_providers: { local, gemini },
    vision_source: local ? "local" : null, elevenlabs_voice_available: true, local_voice_available: true });
  const tick = () => new Promise((r) => setTimeout(r, 0));
  const click = (dataset) => handlers.click({ target: { closest: () => ({ dataset, disabled: false, focus() {} }) } });
  
  await import(pathToFileURL(join(fixture, "src.mjs")));
  pending.shift().ok(cfg(false, false)); await tick();          // boot: everything offline
  // Exercise drawer entry and the shared sketch/drawer provider controls.
  await click({ action: "drawer" }); await tick();
  assert.equal(pending.length, 1, "entering drawer refreshes /config");
  assert.match(app.innerHTML, /id="upload-drawer"[^>]*disabled/);
  // choose a file while offline state shown is impossible (input disabled); Ollama starts:
  let before = renders;
  pending.shift().ok(cfg(true, false)); await tick();
  assert.ok(renders > before, "changed availability re-renders");
  assert.doesNotMatch(app.innerHTML, /id="upload-drawer"[^>]*disabled/);
  // pick a file, then stale-vs-new ordering on focus refreshes
  handlers.change({ target: { type: "file", id: "upload-drawer", files: [{ name: "d.png", type: "image/png", size: 5 }], dataset: {}, value: "" } });
  assert.match(app.innerHTML, /d\.png/);
  win.focus(); win.focus(); await tick();
  assert.equal(pending.length, 2);
  const [older, newer] = pending.splice(0);
  newer.ok(cfg(true, true)); await tick();
  assert.match(app.innerHTML, /data-provider="gemini" data-kind="drawer" aria-pressed="false" >/);
  older.ok(cfg(false, false)); await tick();                     // stale response must not win
  assert.doesNotMatch(app.innerHTML, /id="upload-drawer"[^>]*disabled/);
  assert.match(app.innerHTML, /d\.png/, "chosen file survives refresh");
  assert.match(app.innerHTML, /data-provider="local" data-kind="drawer" aria-pressed="true"/, "no auto cloud");
  // unchanged response does not re-render
  before = renders; win.focus(); await tick(); pending.shift().ok(cfg(true, true)); await tick();
  assert.equal(renders, before);
  // failed refresh keeps state
  win.focus(); await tick(); pending.shift().fail(new Error("down")); await tick();
  assert.equal(renders, before); assert.doesNotMatch(app.innerHTML, /role="alert" >down/);
  // explicit gemini choice, then gemini disappears -> falls back to local, never the reverse
  await click({ provider: "gemini", kind: "drawer" });
  assert.match(app.innerHTML, /Send drawer photo to Gemini/);
  win.focus(); await tick(); pending.shift().ok(cfg(true, false)); await tick();
  assert.match(app.innerHTML, /data-provider="local" data-kind="drawer" aria-pressed="true"/);
  assert.doesNotMatch(app.innerHTML, /Send drawer photo to Gemini/);
  assert.match(app.innerHTML, /d\.png/);
  // local goes away while local selected: stays local (no auto cloud) even if gemini is up
  win.focus(); await tick(); pending.shift().ok(cfg(false, true)); await tick();
  assert.match(app.innerHTML, /data-provider="local" data-kind="drawer" aria-pressed="true"/);
  assert.equal(uploads.length, 0, "refresh never uploads");
  // failed scan triggers a refresh
  win.focus(); await tick(); pending.shift().ok(cfg(true, true)); await tick();
  await click({ action: "scan-drawer" }); await tick();
  assert.equal(uploads.length, 1); assert.equal(uploads[0][1].provider, "local");
  assert.equal(pending.length, 1, "failed scan refreshes");
  pending.shift().ok(cfg(false, true)); await tick();
  assert.match(app.innerHTML, /offline/); assert.match(app.innerHTML, /d\.png/);
  // leaving the stage: late response does not re-render another stage
  win.focus(); await tick(); before = renders;
  await click({ action: "notebook" }); const afterNav = renders;
  pending.shift().ok(cfg(true, true)); await tick();
  assert.equal(renders, afterNav);
  // voice fields untouched by refresh: elevenlabs stays as first loaded even if a later response differs
  await click({ action: "resume" }); await tick();
  pending.shift().ok({ ...cfg(true, true), elevenlabs_voice_available: false }); await tick();
  assert.match(app.innerHTML, /<option value="elevenlabs"  >/);
  console.log("PASS provider refresh, stale responses, preserved file, explicit cloud selection and unchanged voice settings");
} finally {
  rmSync(fixture, { recursive: true, force: true });
}
