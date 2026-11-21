import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const fixture = mkdtempSync(join(tmpdir(), "rendi-companion-"));
try {
  const source = readFileSync(new URL("../frontend/src.js", import.meta.url), "utf8")
    .replace(/^import "[^"\n]+";\n/gm, "")
    .replaceAll('"./voice.js"', '"./stubs.mjs"')
    .replaceAll('"./dictation.js"', '"./dictation.mjs"')
    .replaceAll('"./ui.js"', '"./stubs.mjs"');
  writeFileSync(join(fixture, "src.mjs"), source + "\nexport { job };\n");
  writeFileSync(join(fixture, "dictation.mjs"), readFileSync(new URL("../frontend/dictation.js", import.meta.url)));
  writeFileSync(join(fixture, "stubs.mjs"), `
    export function createVoiceOutput(_notice, _platform, activity) {
      globalThis.playbackActivity = activity;
      return { say() {}, stop() { activity("idle"); }, browserAvailable: true };
    }
    export const icon = () => "", esc = (x) => String(x), pretty = (x) => x, drop = "",
      examples = [], exampleCards = () => "", actionLabels = {},
      scales = { desktop: ["Desktop", 20] }, sameOriginURL = (x) => x;
    export const request = (path, options) => globalThis.api(path, options);
    export const post = async () => ({}), multipart = async () => ({});
  `);

  const el = (props) => ({ dataset: {}, textContent: "", setAttribute() {}, focus() {}, ...props });
  const handlers = {};
  let nodes, renders = 0;
  const app = {
    set innerHTML(markup) {
      renders++;
      nodes = { "#notice": el(), '[data-action="voice"]': el() };
      if (markup.includes("data-rendi")) {
        nodes["[data-rendi]"] = el({ dataset: { state: "idle" } });
        nodes["[data-rendi-status]"] = el();
      }
      if (markup.includes('data-action="dictate"')) nodes['[data-action="dictate"] span'] = el();
      for (const field of markup.matchAll(/<input id="(size|name|vibe)"[^>]* value="([^"]*)"/g)) {
        const [, id, value] = field;
        nodes["#" + id] = el({ value, valueAsNumber: id === "size" ? Number(value) : NaN, selectionStart: 0 });
      }
    },
    querySelector: (key) => nodes[key] || null,
    querySelectorAll: () => [],
    addEventListener: (key, callback) => (handlers[key] = callback),
  };

  const recorders = [], recognizers = [], permissions = [], transcriptions = [];
  const defer = (queue, props = {}) => new Promise((resolve, reject) => queue.push({ resolve, reject, ...props }));
  const mediaDevices = { getUserMedia: (constraints) => {
    assert.deepEqual(constraints, { audio: true });
    return defer(permissions);
  } };
  const stream = () => {
    const track = { stopped: false, stop() { this.stopped = true; } };
    return { track, getTracks: () => [track] };
  };
  globalThis.MediaRecorder = class {
    static isTypeSupported() { return true; }
    constructor(_stream, { mimeType }) { this.mimeType = mimeType; recorders.push(this); }
    start() { this.state = "recording"; }
    stop() { this.state = "inactive"; }
  };
  globalThis.window = {
    addEventListener() {}, scrollTo() {},
    MediaRecorder,
    SpeechRecognition: class {
      constructor() { recognizers.push(this); }
      start() {}
      stop() {}
      abort() { this.aborted = true; }
    },
  };
  globalThis.document = { getElementById: () => app, querySelector: () => null };
  globalThis.location = { pathname: "/", hash: "" };
  globalThis.history = { replaceState() {} };
  Object.defineProperty(globalThis, "navigator", { value: { mediaDevices }, configurable: true });
  globalThis.requestAnimationFrame = (f) => f();
  globalThis.localStorage = { getItem: () => null };
  globalThis.api = (path, options) => {
    if (path === "/config") return Promise.resolve({ templates: [], salvage_keys: [], local_voice_available: true });
    assert.equal(path, "/transcribe");
    return defer(transcriptions, { signal: options.signal });
  };
  const tick = () => new Promise((resolve) => setImmediate(resolve));
  const click = (action) => handlers.click({ target: { closest: () => ({ dataset: { action } }) } });
  const phase = (state, label) => {
    assert.equal(nodes["[data-rendi]"]?.dataset.state, state);
    if (label) assert.match(nodes["[data-rendi-status]"].textContent, label);
  };
  const micLabel = () => nodes['[data-action="dictate"] span'].textContent;

  const { job } = await import(pathToFileURL(join(fixture, "src.mjs")));
  await tick();
  await click("start");
  await handlers.submit({ preventDefault() {}, target: { id: "interview-form" } });
  const answer = nodes["#vibe"], before = renders;
  answer.value = "playful";
  answer.selectionStart = 3;
  playbackActivity("thinking");
  phase("thinking", /Preparing my voice/);
  playbackActivity("speaking");
  phase("speaking");
  playbackActivity("idle");
  phase("idle");
  assert.equal(nodes["#vibe"], answer, "playback activity must keep the original form node");
  assert.equal(answer.value, "playful");
  assert.equal(answer.selectionStart, 3);
  assert.equal(renders, before);

  await click("dictate");
  phase("thinking", /Opening microphone/);
  assert.equal(recorders.length, 0, "permission pending is not recording");
  const first = stream();
  permissions.shift().resolve(first);
  await tick();
  phase("listening");
  await click("dictate");
  const finish = recorders[0].onstop();
  phase("thinking", /Transcribing on this Mac/);
  assert.ok(first.track.stopped);
  answer.value = "gentle";
  transcriptions.shift().resolve({ text: "curious" });
  await finish;
  phase("idle");
  assert.match(micLabel(), /On-device dictation/);
  assert.equal(answer.value, "gentle", "transcription must preserve an answer typed during capture");
  assert.equal(renders, before);

  await click("dictate");
  permissions.shift().resolve(stream());
  await tick();
  await click("dictate");
  const staleRecorder = recorders.at(-1), oldFinish = staleRecorder.onstop(), oldText = transcriptions.shift();
  await click("notebook");
  assert.ok(oldText.signal.aborted);
  await click("resume");
  await click("dictate");
  const next = stream();
  permissions.shift().resolve(next);
  await tick();
  const liveAnswer = nodes["#vibe"];
  oldText.resolve({ text: "chaotic" });
  await oldFinish;
  staleRecorder.onerror();
  phase("listening");
  assert.match(micLabel(), /Listening/);
  assert.ok(!next.track.stopped, "stale recorder error must leave the new stream open");
  assert.equal(liveAnswer.value, "gentle");
  await click("notebook");
  assert.ok(next.track.stopped);

  navigator.mediaDevices = null;
  await click("resume");
  await click("dictate");
  phase("thinking", /Opening microphone/);
  recognizers.at(-1).onstart();
  phase("listening");
  await click("dictate");
  phase("thinking", /Transcribing with your browser/);
  recognizers.at(-1).onaudioend();
  phase("thinking", /Transcribing with your browser/);
  recognizers.at(-1).onend();
  phase("idle");
  assert.equal(micLabel(), "Dictate answer");

  await click("dictate");
  const stale = recognizers.at(-1), lateStart = stale.onstart, lateEnd = stale.onend, lateResult = stale.onresult;
  await click("notebook");
  assert.ok(stale.aborted);
  assert.equal(stale.onresult, null);
  await click("resume");
  await click("dictate");
  lateStart();
  lateEnd();
  lateResult({ results: [[{ transcript: "chaotic" }]] });
  phase("thinking", /Opening microphone/);
  assert.equal(nodes["#vibe"].value, "gentle");
  const current = recognizers.at(-1);
  current.onstart();
  phase("listening");
  current.onend();
  phase("idle");

  await job("Saving your brief…", async () => {
    phase("thinking", /Saving your brief/);
    playbackActivity("speaking");
    phase("speaking");
  });
  phase("speaking");
  playbackActivity("idle");
  phase("idle");
  console.log("PASS Rendi playback, preserved form input, local dictation, and stale mic callbacks");
} finally {
  rmSync(fixture, { recursive: true, force: true });
}
