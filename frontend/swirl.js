// Generation swirl: a full-screen vortex shown while Rendi builds a model, reads a drawer
// or writes a plan. It acknowledges at once, narrates stages, and collapses into the result.

const STAGES = {
  sketch: ["Reading your lines…", "Finding the parts…", "Measuring at your size…", "Shaping solids…", "Polishing the model…"],
  example: ["Unfolding the starter sketch…", "Scaling it to your size…", "Shaping solids…"],
  drawer: ["Scanning the drawer…", "Naming what I see…", "Checking what’s safe to open…"],
  plan: ["Matching parts to your model…", "Checking drawer donors…", "Writing your build steps…"],
};
const LONG = {
  sketch: "Still rendering. The first photo can take up to a minute while the on-device model wakes up.",
  drawer: "Still looking. Busy drawers take a little longer.",
  plan: "Still writing. Almost there.",
  example: "Still shaping. Almost there.",
};
const MIN_VISIBLE = 900;

const face = `<svg class="swirl-drop" viewBox="0 0 168 168" aria-hidden="true" focusable="false"><use href="#ir-drop-shape" fill="#fff" opacity=".7" filter="url(#ir-soft)"/><use href="#ir-drop-shape" fill="url(#ir-drop)"/><ellipse cx="66" cy="72" rx="5" ry="11" fill="#fff" opacity=".9" transform="rotate(24 66 72)"/><path d="M65 112 q7 -6 14 0 M89 112 q7 -6 14 0" fill="none" stroke="#0B2CB1" stroke-width="4" stroke-linecap="round"/><path class="swirl-sparkle" d="M134 40 v16 M126 48 h16 M146 70 v10 M141 75 h10" stroke="#BFD6FF" stroke-width="3" stroke-linecap="round"/></svg>`;

function vortex(canvas, still) {
  const ctx = canvas.getContext("2d");
  let w = 0, h = 0, raf = 0, collapse = 0, particles = [];
  const resize = () => {
    const ratio = Math.min(1.5, devicePixelRatio || 1);
    w = innerWidth;
    h = innerHeight;
    canvas.width = Math.round(w * ratio);
    canvas.height = Math.round(h * ratio);
    ctx?.setTransform(ratio, 0, 0, ratio, 0, 0);
  };
  const outer = () => Math.hypot(w, h) * 0.42;
  const spawn = (p, fresh) => {
    p.r = fresh ? 40 + Math.random() * outer() : outer() * (0.75 + Math.random() * 0.3);
    p.a = Math.random() * Math.PI * 2;
    p.arm = Math.floor(Math.random() * 3);
    p.size = 0.8 + Math.random() * 1.8;
    return p;
  };
  resize();
  particles = Array.from({ length: Math.min(520, Math.round((w * h) / 2600)) }, () => spawn({}, true));
  function frame() {
    raf = requestAnimationFrame(frame);
    if (!ctx) return;
    const cx = w / 2, cy = h / 2 - 20, max = outer();
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "rgba(3, 25, 91, 0.22)";
    ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = "lighter";
    for (const p of particles) {
      const inward = 0.6 + (1 - p.r / max) * 2.4 + collapse * 14;
      const spin = 0.004 + 1.6 / (p.r + 60) + collapse * 0.02;
      p.a += spin;
      p.r -= inward;
      if (p.r < 26) {
        if (collapse) p.r = -1;
        else spawn(p, false);
      }
      if (p.r < 0) continue;
      const twist = p.a + p.arm * ((Math.PI * 2) / 3) + p.r * 0.012;
      const x = cx + Math.cos(twist) * p.r, y = cy + Math.sin(twist) * p.r * 0.82;
      const t = 1 - p.r / max;
      ctx.fillStyle = `rgba(${Math.round(55 + 200 * t)}, ${Math.round(129 + 126 * t)}, 255, ${0.25 + t * 0.6})`;
      ctx.beginPath();
      ctx.arc(x, y, p.size * (0.6 + t), 0, Math.PI * 2);
      ctx.fill();
    }
    if (collapse) collapse = Math.min(collapse + 0.06, 1);
  }
  if (!still) frame();
  addEventListener("resize", resize);
  return {
    collapse() {
      collapse = 0.01;
    },
    dispose() {
      cancelAnimationFrame(raf);
      removeEventListener("resize", resize);
    },
  };
}

export function showSwirl({ status, kind }) {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const root = document.createElement("div");
  root.className = "swirl";
  root.setAttribute("role", "status");
  root.setAttribute("aria-live", "polite");
  root.innerHTML = `<canvas class="swirl-canvas" aria-hidden="true"></canvas><div class="swirl-core">${face}<strong class="swirl-status"></strong><span class="swirl-stage"></span><small class="swirl-long" hidden></small></div>`;
  root.querySelector(".swirl-status").textContent = status;
  document.body.appendChild(root);
  const fx = vortex(root.querySelector(".swirl-canvas"), still);
  const stageEl = root.querySelector(".swirl-stage"), longEl = root.querySelector(".swirl-long");
  const stages = STAGES[kind] || [];
  let n = 0;
  const showStage = () => {
    const text = stages[Math.min(n++, stages.length - 1)] || "";
    if (text === stageEl.textContent) return;
    stageEl.classList.remove("is-in");
    void stageEl.offsetWidth;
    stageEl.textContent = text;
    stageEl.classList.add("is-in");
  };
  showStage();
  const stageTimer = setInterval(showStage, 2200);
  const longTimer = setTimeout(() => {
    longEl.textContent = LONG[kind] || "Still working…";
    longEl.hidden = false;
  }, 10000);
  const started = performance.now();
  requestAnimationFrame(() => root.classList.add("is-open"));
  return {
    async finish(ok) {
      clearInterval(stageTimer);
      clearTimeout(longTimer);
      const wait = MIN_VISIBLE - (performance.now() - started);
      if (ok && wait > 0) await new Promise((r) => setTimeout(r, wait));
      if (ok) {
        stageEl.textContent = "Rendered.";
        root.classList.add("is-done");
        fx.collapse();
      }
      root.classList.add("is-closing");
      await new Promise((r) => setTimeout(r, still ? 0 : ok ? 520 : 220));
      fx.dispose();
      root.remove();
    },
  };
}
