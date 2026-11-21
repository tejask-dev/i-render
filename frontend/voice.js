export function createVoiceOutput(notice, platform = window) {
  const synth = platform.speechSynthesis;
  const browserAvailable = Boolean(synth && platform.SpeechSynthesisUtterance);
  let generation = 0, controller, audio, url;

  function stop() {
    generation++;
    controller?.abort();
    controller = null;
    if (audio) {
      audio.onended = audio.onerror = null;
      audio.pause();
      audio = null;
    }
    if (url) platform.URL.revokeObjectURL(url);
    url = null;
    synth?.cancel();
  }

  function speakInBrowser(text) {
    if (!browserAvailable) return;
    const current = generation;
    try {
      const utterance = new platform.SpeechSynthesisUtterance(text);
      const localVoice = synth.getVoices().find((v) => v.localService && v.lang.startsWith("en"));
      if (localVoice) utterance.voice = localVoice;
      utterance.rate = 1;
      utterance.pitch = 1.08;
      utterance.onerror = () => {
        if (current === generation) notice("Browser speech could not play. You can continue on screen.");
      };
      synth.speak(utterance);
    } catch {
      notice("Browser speech could not play. You can continue on screen.");
    }
  }

  async function say(text, provider) {
    stop();
    if (provider !== "elevenlabs") {
      speakInBrowser(text);
      return;
    }
    const current = generation;
    controller = new AbortController();
    function fallback() {
      if (current !== generation) return;
      stop();
      notice(browserAvailable
        ? "ElevenLabs could not play. Using the browser voice for this line."
        : "ElevenLabs could not play. You can continue on screen.");
      speakInBrowser(text);
    }
    try {
      const response = await platform.fetch("/api/speak", {
        method: "POST",
        mode: "same-origin",
        redirect: "error",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      if (current !== generation) return;
      if (!response.ok) throw new Error("Speech unavailable");
      const blob = await response.blob();
      if (current !== generation) return;
      if (!blob.size || blob.type.split(";")[0] !== "audio/mpeg") throw new Error("Invalid speech audio");
      url = platform.URL.createObjectURL(blob);
      audio = new platform.Audio(url);
      audio.onended = () => { if (current === generation) stop(); };
      audio.onerror = fallback;
      await audio.play();
    } catch {
      fallback();
    }
  }

  return { browserAvailable, say, stop };
}
