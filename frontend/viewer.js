import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

export function mountViewer(element, url, parts, selectPart) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch {
    element.querySelector(".viewer-status").textContent =
      "3D preview needs WebGL. The parts list and downloadable model are available.";
    return;
  }
  const canvas = renderer.domElement;
  canvas.tabIndex = 0;
  canvas.setAttribute("role", "group");
  canvas.setAttribute(
    "aria-label",
    "3D robot model. Arrow keys rotate. Plus and minus zoom. Click or use the part buttons to inspect.",
  );
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  element.prepend(canvas);
  const scene = new THREE.Scene(),
    camera = new THREE.PerspectiveCamera(38, 1, 0.001, 20);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.autoRotate = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const spinButton = element.querySelector("[data-spin]");
  const setSpin = (on) => {
    controls.autoRotate = on;
    spinButton.textContent = on ? "Pause orbit" : "Auto-orbit";
    spinButton.setAttribute("aria-pressed", String(on));
  };
  spinButton.onclick = () => setSpin(!controls.autoRotate);
  setSpin(controls.autoRotate);
  controls.autoRotateSpeed = 0.8;
  controls.maxPolarAngle = Math.PI * 0.54;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x3a4f8f, 2.4));
  const light = new THREE.DirectionalLight(0xf2f6ff, 2.8);
  light.position.set(2, 4, 3);
  scene.add(light);
  const center = new THREE.Vector3();
  let radius = 0.2,
    model,
    stopped = false,
    active,
    hovered,
    focus = new Set();
  const allParts = new Set(parts.map((part) => part.id)),
    meshes = [];
  const fit = () => {
    const distance =
      (radius * 1.23) /
      Math.sin(
        Math.min(
          (camera.fov * Math.PI) / 360,
          Math.atan(Math.tan((camera.fov * Math.PI) / 360) * camera.aspect),
        ),
      );
    camera.position
      .copy(center)
      .add(
        new THREE.Vector3(1.1, 0.67, 1.45).normalize().multiplyScalar(distance),
      );
    camera.near = Math.max(radius / 1000, 0.00005);
    camera.far = distance * 12;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.minDistance = radius * 0.65;
    controls.maxDistance = distance * 5;
    controls.update();
  };
  const resize = new ResizeObserver(() => {
    const w = element.clientWidth,
      h = element.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (model) fit();
  });
  resize.observe(element);
  function highlight() {
    for (const mesh of meshes) {
      const id = mesh.userData.partId,
        on = id === active,
        hover = id === hovered,
        step = focus.has(id),
        faded = focus.size > 0 && !step && !on && !hover;
      if (mesh.material.emissive) {
        mesh.material.emissive.setHex(on ? 0x1951fc : hover ? 0x0b2cb1 : step ? 0x3781fc : 0);
        mesh.material.emissiveIntensity = on ? 0.45 : step ? 0.35 : 0.27;
      }
      mesh.material.transparent = faded || mesh.userData.baseTransparent;
      mesh.material.opacity = faded ? 0.28 : mesh.userData.baseOpacity;
      mesh.material.depthWrite = !faded;
    }
  }
  function releaseModel(root) {
    root?.traverse((o) => {
      o.geometry?.dispose();
      if (o.material) {
        for (const m of Array.isArray(o.material) ? o.material : [o.material])
          m.dispose();
      }
    });
  }
  new GLTFLoader().load(
    url,
    (gltf) => {
      if (stopped) {
        releaseModel(gltf.scene);
        return;
      }
      model = gltf.scene;
      scene.add(model);
      model.traverse((mesh) => {
        if (!mesh.isMesh) return;
        let node = mesh;
        while (node && !allParts.has(node.name)) node = node.parent;
        mesh.userData.partId =
          node?.name ||
          (allParts.has(mesh.geometry?.name) ? mesh.geometry.name : null);
        mesh.material = (
          Array.isArray(mesh.material) ? mesh.material[0] : mesh.material
        ).clone();
        mesh.userData.baseOpacity = mesh.material.opacity;
        mesh.userData.baseTransparent = mesh.material.transparent;
        meshes.push(mesh);
      });
      const box = new THREE.Box3().setFromObject(model);
      if (box.isEmpty()) {
        element.querySelector(".viewer-status").textContent =
          "This model has no visible parts.";
        return;
      }
      const sphere = box.getBoundingSphere(new THREE.Sphere());
      center.copy(sphere.center);
      radius = Math.max(sphere.radius, 0.005);
      const side = Math.max(0.1, Math.ceil(radius * 640) / 100);
      const grid = new THREE.GridHelper(
        side,
        Math.min(300, Math.round(side / 0.01)),
        0x3781fc,
        0x1b3a8c,
      );
      grid.position.set(center.x, box.min.y - 0.0003, center.z);
      scene.add(grid);
      fit();
      highlight();
      element.querySelector(".viewer-status").hidden = true;
      spinButton.hidden = false;
    },
    undefined,
    () => {
      if (!stopped)
        element.querySelector(".viewer-status").textContent =
          "Model preview failed to load. Download the GLB or choose another sketch.";
    },
  );
  const ray = new THREE.Raycaster(),
    pointer = new THREE.Vector2();
  let start;
  function hit(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.set(
      (2 * (event.clientX - rect.left)) / rect.width - 1,
      1 - (2 * (event.clientY - rect.top)) / rect.height,
    );
    ray.setFromCamera(pointer, camera);
    return ray.intersectObjects(meshes, false)[0]?.object.userData.partId;
  }
  canvas.addEventListener("pointerdown", (e) => {
    start = [e.clientX, e.clientY];
    setSpin(false);
  });
  canvas.addEventListener("pointerup", (e) => {
    if (!start || Math.hypot(start[0] - e.clientX, start[1] - e.clientY) > 5)
      return;
    const id = hit(e);
    if (id) selectPart(id);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (e.buttons) return;
    hovered = hit(e);
    canvas.style.cursor = hovered ? "pointer" : "grab";
    highlight();
  });
  canvas.addEventListener("pointerleave", () => {
    hovered = null;
    highlight();
  });
  canvas.addEventListener("keydown", (event) => {
    const actions = {
      ArrowLeft: () => controls.rotateLeft(0.14),
      ArrowRight: () => controls.rotateLeft(-0.14),
      ArrowUp: () => controls.rotateUp(0.12),
      ArrowDown: () => controls.rotateUp(-0.12),
      "+": () => controls.dollyIn(0.9),
      "=": () => controls.dollyIn(0.9),
      "-": () => controls.dollyOut(0.9),
      Home: fit,
    };
    if (!actions[event.key]) return;
    event.preventDefault();
    setSpin(false);
    actions[event.key]();
  });
  element.querySelector("[data-fit]").onclick = fit;
  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });
  return {
    select(id) {
      active = id;
      highlight();
    },
    focus(ids) {
      focus = new Set(ids || []);
      highlight();
    },
    dispose() {
      stopped = true;
      resize.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      releaseModel(scene);
      renderer.dispose();
      renderer.forceContextLoss();
    },
  };
}
