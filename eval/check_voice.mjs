import assert from "node:assert/strict";
import { createVoiceOutput } from "../frontend/voice.js";

function deferred() {
  let resolve, reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

const requests = [], players = [], revoked = [], spoken = [], notices = [];
const localVoice = { localService: true, lang: "en-US" };
const platform = {
  fetch(path, options) {
    assert.equal(path, "/api/speak");
    const pending = deferred();
    requests.push({ options, pending });
    return pending.promise;
  },
  Audio: class {
    constructor(url) { this.url = url; this.started = deferred(); players.push(this); }
    play() { return this.started.promise; }
    pause() { this.paused = true; }
  },
  URL: {
    createObjectURL: () => "blob:test-" + players.length,
    revokeObjectURL: (url) => revoked.push(url),
  },
  speechSynthesis: {
    getVoices: () => [localVoice],
    speak: (utterance) => spoken.push(utterance),
    cancel() {},
  },
  SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
};
const out = createVoiceOutput((notice) => notices.push(notice), platform);
const mp3 = new Blob(["mock"], { type: "audio/mpeg" });
const success = { ok: true, blob: async () => mp3 };
const flush = () => new Promise((resolve) => setImmediate(resolve));

await out.say("Browser first", "browser");
assert.equal(requests.length, 0);
assert.equal(spoken[0].voice, localVoice);

const late = out.say("First", "elevenlabs");
const first = requests.at(-1);
assert.deepEqual(JSON.parse(first.options.body), { text: "First" });
const next = out.say("Second", "elevenlabs");
const second = requests.at(-1);
assert.ok(first.options.signal.aborted);
first.pending.reject(new Error("Late failure"));
second.pending.resolve(success);
await late;
await flush();
assert.equal(players.length, 1);
assert.equal(spoken.length, 1);
assert.deepEqual(notices, []);

const active = players[0];
out.stop(); // Mute, navigation, and dictation share this cancellation path.
active.started.reject(new Error("Playback interrupted"));
await next;
assert.ok(active.paused);
assert.deepEqual(revoked, [active.url]);
assert.deepEqual(notices, []);

const pendingBody = deferred();
const body = out.say("Late blob", "elevenlabs");
requests.at(-1).pending.resolve({ ok: true, blob: () => pendingBody.promise });
await flush();
await out.say("Switched provider", "browser");
pendingBody.resolve(mp3);
await body;
assert.equal(players.length, 1);
assert.equal(spoken.at(-1).text, "Switched provider");

const blocked = out.say("Use fallback", "elevenlabs");
requests.at(-1).pending.resolve(success);
await flush();
const failed = players.at(-1);
const mediaError = failed.onerror;
failed.started.reject(new Error("Autoplay denied"));
await blocked;
mediaError();
assert.ok(failed.paused);
assert.equal(spoken.filter((u) => u.text === "Use fallback").length, 1);
assert.match(notices.at(-1), /browser voice for this line/);

const cloudOnly = createVoiceOutput((text) => notices.push(text), { ...platform, speechSynthesis: undefined });
assert.equal(cloudOnly.browserAvailable, false);
const unavailable = cloudOnly.say("Read instead", "elevenlabs");
requests.at(-1).pending.resolve({ ok: false });
await unavailable;
assert.match(notices.at(-1), /continue on screen/);
const finished = cloudOnly.say("Playable", "elevenlabs");
requests.at(-1).pending.resolve(success);
await flush();
const player = players.at(-1);
player.started.resolve();
await finished;
player.onended();
assert.equal(revoked.at(-1), player.url);
assert.equal(revoked.length, players.length);
console.log("Voice output passed browser default, opt-in request, cancellation races, fallback and cleanup.");
