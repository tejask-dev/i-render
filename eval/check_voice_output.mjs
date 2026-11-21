import assert from "node:assert/strict";
import { createVoiceOutput } from "../frontend/voice.js";

function deferred() {
  let resolve, reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

const requests = [], players = [], revoked = [], spoken = [], notices = [], states = [];
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
    getVoices: () => [],
    speak: (utterance) => spoken.push(utterance),
    cancel() {},
  },
  SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
};
const out = createVoiceOutput((text) => notices.push(text), platform, (state) => states.push(state));
const mp3 = new Blob(["mock"], { type: "audio/mpeg" });
const success = { ok: true, blob: async () => mp3 };
const flush = () => new Promise((resolve) => setImmediate(resolve));
// Asserts the transitions since the previous call, so silence is checked too.
function expect(...next) {
  assert.deepEqual(states.splice(0), next);
}

// Browser voice: queued text is not speech; only the utterance's own start is.
await out.say("Hello", "browser");
const hello = spoken.at(-1);
expect();
hello.onstart();
expect("speaking");
hello.onstart();
expect();
hello.onend();
expect("idle");

// Replacing a line mid-speech goes idle, and the cancelled utterance stays silent.
await out.say("Replaced", "browser");
const replaced = spoken.at(-1);
replaced.onstart();
expect("speaking");
await out.say("Replacement", "browser");
const replacement = spoken.at(-1);
expect("idle");
replaced.onstart();
replaced.onerror();
replaced.onend();
expect();
assert.deepEqual(notices, []);
replacement.onstart();
expect("speaking");
out.stop({ type: "pagehide" }); // Registered directly as an event listener.
expect("idle");
replacement.onend();
replacement.onstart();
expect();

// A browser speech error returns to idle and still tells the user.
await out.say("Broken", "browser");
spoken.at(-1).onstart();
spoken.at(-1).onerror();
expect("speaking", "idle");
assert.match(notices.pop(), /Browser speech could not play/);

// ElevenLabs: thinking through fetch and load, speaking only once playback starts.
const played = out.say("Cloud", "elevenlabs");
expect("thinking");
requests.at(-1).pending.resolve(success);
await flush();
const player = players.at(-1);
expect();
player.started.resolve();
await played;
expect("speaking");
player.onended();
expect("idle");
assert.equal(revoked.at(-1), player.url);

// Cancelling while thinking goes idle; the late response starts nothing.
const cancelled = out.say("Cancelled", "elevenlabs");
const cancelledRequest = requests.at(-1);
expect("thinking");
out.stop();
expect("idle");
assert.ok(cancelledRequest.options.signal.aborted);
cancelledRequest.pending.resolve(success);
await cancelled;
await flush();
expect();
assert.equal(players.length, 1);

// Out of order: the superseded request fails late while its replacement loads.
const older = out.say("Older", "elevenlabs");
const olderRequest = requests.at(-1);
const newer = out.say("Newer", "elevenlabs");
const newerRequest = requests.at(-1);
expect("thinking");
olderRequest.pending.reject(new Error("Late failure"));
await older;
expect();
newerRequest.pending.resolve(success);
await flush();
const loading = players.at(-1);

// Playback that starts after the line was replaced never reports speaking.
await out.say("Interrupt", "browser");
expect("idle");
loading.started.resolve();
await newer;
loading.onended?.();
expect();
assert.ok(loading.paused);
assert.equal(revoked.at(-1), loading.url);
spoken.at(-1).onstart();
expect("speaking");

// Stopping during load, then a late playback rejection, stays idle with no fallback.
const stopped = out.say("Stopped", "elevenlabs");
expect("thinking"); // Straight from speaking, with no idle flicker.
requests.at(-1).pending.resolve(success);
await flush();
const interrupted = players.at(-1);
out.stop();
expect("idle");
interrupted.started.reject(new Error("Playback interrupted"));
await stopped;
expect();
assert.deepEqual(notices, []);

// Fallback: thinking ends with the failure, and speaking waits for the browser voice.
const lineCount = spoken.length;
const blocked = out.say("Fallback", "elevenlabs");
requests.at(-1).pending.resolve(success);
await flush();
const denied = players.at(-1);
const mediaError = denied.onerror;
denied.started.reject(new Error("Autoplay denied"));
await blocked;
mediaError();
expect("thinking", "idle");
assert.equal(spoken.length, lineCount + 1);
assert.match(notices.pop(), /browser voice for this line/);
spoken.at(-1).onstart();
spoken.at(-1).onend();
expect("speaking", "idle");

// Invalid audio is rejected before any player exists.
const playerCount = players.length;
const invalid = out.say("Not audio", "elevenlabs");
requests.at(-1).pending.resolve({ ok: true, blob: async () => new Blob(["<html>"], { type: "text/html" }) });
await invalid;
expect("thinking", "idle");
assert.equal(players.length, playerCount);
assert.match(notices.pop(), /browser voice for this line/);
assert.equal(revoked.length, players.length);

// Without a browser voice a cloud failure still ends idle.
const cloudStates = [];
const cloudOnly = createVoiceOutput((text) => notices.push(text), { ...platform, speechSynthesis: undefined }, (state) => cloudStates.push(state));
const unavailable = cloudOnly.say("Read instead", "elevenlabs");
requests.at(-1).pending.resolve({ ok: false });
await unavailable;
assert.deepEqual(cloudStates, ["thinking", "idle"]);
assert.match(notices.pop(), /continue on screen/);
await cloudOnly.say("Nothing to play", "browser");
assert.deepEqual(cloudStates, ["thinking", "idle"]);

// The callback is optional, and a throwing one cannot break playback or cleanup.
const plain = createVoiceOutput((text) => notices.push(text), platform);
await plain.say("No callback", "browser");
spoken.at(-1).onstart();
plain.stop();
const fragile = createVoiceOutput((text) => notices.push(text), platform, () => { throw new Error("UI bug"); });
const survived = fragile.say("Survives", "elevenlabs");
requests.at(-1).pending.resolve(success);
await flush();
players.at(-1).started.resolve();
await survived;
fragile.stop();
assert.ok(players.at(-1).paused);
assert.equal(revoked.length, players.length);
assert.deepEqual(notices, []);
console.log("Voice activity passed start-gated speaking, thinking during load, cancellation, stale events and fallback.");
