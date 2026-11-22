// Landing page motion: ASCII particle network behind glass, typed headline, rotating line.
// Every loop stops on dispose(), on pause, when the tab is hidden, and under reduced motion.

const GLYPHS = ".:+*#=~/\\<>01{}[]";
const LINK = 132; // px: max distance for a connecting line
const POINTER = 150; // px: pointer influence radius
const FRAME = 1000 / 30; // 30 fps cap

function network(canvas, still) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return { setPaused() {}, dispose() {} };
  const fine = matchMedia("(pointer: fine)").matches;
  let w = 0, h = 0, ratio = 1, nodes = [], raf = 0, last = 0, paused = still;
  const pointer = { x: -9999, y: -9999, on: false };

  function seed() {
    const box = canvas.getBoundingClientRect();
    ratio = Math.min(1.5, devicePixelRatio || 1);
    w = box.width;
    h = box.height;
    canvas.width = Math.round(w * ratio);
    canvas.height = Math.round(h * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const count = Math.max(28, Math.min(110, Math.round((w * h) / 13000)));
    nodes = Array.from({ length: count }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      g: GLYPHS[Math.floor(Math.random() * GLYPHS.length)],
      s: 11 + Math.random() * 7,
      a: 0.45 + Math.random() * 0.45,
    }));
    draw();
  }

  function step() {
    for (const n of nodes) {
      if (pointer.on) {
        const dx = n.x - pointer.x, dy = n.y - pointer.y, d = Math.hypot(dx, dy);
        if (d < POINTER && d > 0.1) {
          const push = (1 - d / POINTER) * 0.9;
          n.vx += (dx / d) * push;
          n.vy += (dy / d) * push;
        }
      }
      n.vx *= 0.94;
      n.vy *= 0.94;
      n.vx += (Math.random() - 0.5) * 0.03;
      n.vy += (Math.random() - 0.5) * 0.03;
      n.x += n.vx + Math.sign(n.vx) * 0.12;
      n.y += n.vy + Math.sign(n.vy) * 0.12;
      if (n.x < -20) n.x = w + 20;
      if (n.x > w + 20) n.x = -20;
      if (n.y < -20) n.y = h + 20;
      if (n.y > h + 20) n.y = -20;
    }
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    ctx.lineWidth = 1;
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j], d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d > LINK) continue;
        ctx.strokeStyle = `rgba(127, 169, 255, ${(1 - d / LINK) * 0.42})`;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      if (pointer.on) {
        const d = Math.hypot(a.x - pointer.x, a.y - pointer.y);
        if (d < POINTER * 1.3) {
          ctx.strokeStyle = `rgba(255, 255, 255, ${(1 - d / (POINTER * 1.3)) * 0.45})`;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(pointer.x, pointer.y);
          ctx.stroke();
        }
      }
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const n of nodes) {
      ctx.font = `500 ${n.s}px ui-monospace, "SF Mono", Menlo, monospace`;
      ctx.fillStyle = `rgba(217, 228, 255, ${n.a})`;
      ctx.fillText(n.g, n.x, n.y);
    }
  }

  function loop(t) {
    raf = requestAnimationFrame(loop);
    if (t - last < FRAME) return;
    last = t;
    step();
    draw();
  }
  function start() {
    if (!raf && !paused && !document.hidden) raf = requestAnimationFrame(loop);
  }
  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
  }
  const move = (e) => {
    const box = canvas.getBoundingClientRect();
    pointer.x = e.clientX - box.left;
    pointer.y = e.clientY - box.top;
    pointer.on = true;
  };
  const leave = () => (pointer.on = false);
  const visibility = () => (document.hidden ? stop() : start());
  const resize = new ResizeObserver(() => seed());
  const host = canvas.parentElement;
  if (fine) {
    host.addEventListener("pointermove", move);
    host.addEventListener("pointerleave", leave);
  }
  document.addEventListener("visibilitychange", visibility);
  resize.observe(canvas);
  seed();
  start();
  return {
    setPaused(value) {
      paused = value;
      paused ? stop() : start();
    },
    dispose() {
      stop();
      resize.disconnect();
      host.removeEventListener("pointermove", move);
      host.removeEventListener("pointerleave", leave);
      document.removeEventListener("visibilitychange", visibility);
    },
  };
}

function typer(el, words, still) {
  let timer = 0, paused = still, word = 0, chars = 0, deleting = false;
  if (still) {
    el.textContent = words[0];
    return { setPaused() {}, dispose() {} };
  }
  function tick() {
    const text = words[word];
    if (!deleting && chars < text.length) {
      el.textContent = text.slice(0, ++chars);
      return (timer = setTimeout(tick, 85 + Math.random() * 60));
    }
    if (!deleting) {
      deleting = true;
      return (timer = setTimeout(tick, word === 0 ? 1600 : 2400));
    }
    if (chars > 0) {
      el.textContent = text.slice(0, --chars);
      return (timer = setTimeout(tick, 42));
    }
    deleting = false;
    word = (word + 1) % words.length;
    timer = setTimeout(tick, 320);
  }
  el.textContent = "";
  timer = setTimeout(tick, 500);
  return {
    setPaused(value) {
      paused = value;
      clearTimeout(timer);
      if (paused) {
        chars = words[word].length;
        deleting = false;
        el.textContent = words[word];
      } else timer = setTimeout(tick, 1200);
    },
    dispose() {
      clearTimeout(timer);
    },
  };
}

function rotator(el, lines, still) {
  let i = 0, timer = 0;
  const show = (n) => {
    el.classList.remove("is-in");
    setTimeout(() => {
      el.textContent = lines[n];
      el.classList.add("is-in");
    }, still ? 0 : 260);
  };
  el.textContent = lines[0];
  el.classList.add("is-in");
  const run = () => (timer = setInterval(() => show((i = (i + 1) % lines.length)), 3200));
  if (!still) run();
  return {
    setPaused(value) {
      clearInterval(timer);
      if (!value && !still) run();
    },
    dispose() {
      clearInterval(timer);
    },
  };
}

export function mountLanding(root, { words, lines, icons = {} }) {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const parts = [
    network(root.querySelector(".landing-net"), still),
    typer(root.querySelector("[data-type]"), words, still),
    rotator(root.querySelector("[data-rotate]"), lines, still),
  ];
  const toggle = root.querySelector("[data-motion-toggle]");
  let paused = still;
  const label = () => {
    toggle.setAttribute("aria-pressed", String(paused));
    root.classList.toggle("is-paused", paused);
    toggle.innerHTML = `${(paused ? icons.play : icons.pause) || ""}<span>${paused ? "Play motion" : "Pause motion"}</span>`;
  };
  if (still) toggle.hidden = true;
  toggle.onclick = () => {
    paused = !paused;
    parts.forEach((p) => p.setPaused(paused));
    label();
  };
  label();
  return () => parts.forEach((p) => p.dispose());
}
