const imports = import.meta.glob(
  "/node_modules/lucide/icons/{arrow-right,arrow-left,arrow-up-right,volume-2,volume-x,book-open,pencil-ruler,pencil,box,boxes,check,plus,x,download,mic,upload,rotate-ccw,focus,minus,search,save,triangle-alert,chevron-right,move-3d,settings-2,lightbulb,component,eye,power,wand-sparkles,pause,play}.svg",
  { eager: true, query: "?raw", import: "default" },
);
const icons = Object.fromEntries(
  Object.entries(imports).map(([path, svg]) => [
    path.split("/").pop().replace(".svg", ""),
    svg.replace("<svg", '<svg aria-hidden="true" focusable="false"'),
  ]),
);
export const icon = (name) => icons[name] || "";
export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
export const pretty = (value) => String(value ?? "").replaceAll("_", " ");
export const drop =
  '<svg class="drop" viewBox="0 0 168 168" aria-hidden="true" focusable="false"><rect x="4" y="4" width="160" height="160" rx="44" fill="url(#ir-square)"/><rect x="4" y="4" width="160" height="160" rx="44" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="2"/><use href="#ir-drop-shape" fill="#fff" opacity=".6" filter="url(#ir-soft)"/><use href="#ir-drop-shape" fill="url(#ir-drop)"/><ellipse cx="66" cy="72" rx="5" ry="11" fill="#fff" opacity=".9" transform="rotate(24 66 72)"/><ellipse cx="72" cy="110" rx="7" ry="11" fill="#0B2CB1"/><ellipse cx="96" cy="110" rx="7" ry="11" fill="#0B2CB1"/></svg>';
export const examples = [
  {
    id: "wheelbot",
    name: "Wheelbot",
    blurb: "A curious little rover",
    actions: ["drive"],
    adventure: "Roll around the desk looking for adventure.",
    vibes: ["curious", "scrappy"],
  },
  {
    id: "armbot",
    name: "Armbot",
    blurb: "A tabletop helping hand",
    actions: ["grab"],
    adventure: "Pick up little objects on the workbench.",
    vibes: ["helpful", "precise"],
  },
  {
    id: "blobbot",
    name: "Blobbot",
    blurb: "A tiny glowing companion",
    actions: ["light_up"],
    adventure: "Glow beside my bed when it gets dark.",
    vibes: ["dreamy", "gentle"],
  },
];
export const exampleCards = (label) =>
  examples
    .map(
      ({ id, name, blurb }, i) =>
        `<button class="starter" data-example="${id}" aria-label="${esc(label + " " + name)}"><span class="sketch sketch-${i}" aria-hidden="true"></span><span class="starter-info"><strong>${name}</strong><small>${blurb}</small></span><span class="round-link">${icon("arrow-up-right")}</span></button>`,
    )
    .join("");
export const actionLabels = {
  drive: "Drive",
  walk: "Walk",
  light_up: "Light up",
  make_sound: "Make sound",
  grab: "Grab",
  spin: "Spin",
  sense_distance: "Sense distance",
  display_face: "Display a face",
  fly_ish: "Move air",
};
export const scales = {
  handheld: ["Handheld", 10],
  desktop: ["Desktop", 20],
  floor: ["Floor", 45],
  wearable: ["Wearable", 12],
};
export function sameOriginURL(value) {
  const url = new URL(value, location.origin);
  if (
    url.origin !== location.origin ||
    !["http:", "https:"].includes(url.protocol)
  )
    throw new Error("The server returned an invalid file location.");
  return url.pathname + url.search;
}
export async function request(path, options) {
  let response;
  try {
    response = await fetch("/api" + path, options);
  } catch {
    throw new Error(
      "The workshop server is offline. Reconnect it, then try again.",
    );
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The workshop server did not return a result. Check the local server and try again.",
    );
  }
  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join(". ")
          : data.message;
    throw new Error(
      detail || "The request could not be completed. Please try again.",
    );
  }
  return data;
}
export const post = (path, data) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
export const multipart = (path, values) => {
  const form = new FormData();
  for (const [key, value] of Object.entries(values))
    if (value != null) form.append(key, value);
  return request(path, { method: "POST", body: form });
};
