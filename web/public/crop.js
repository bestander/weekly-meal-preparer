const CORNER_LABELS = ["Top-left", "Top-right", "Bottom-right", "Bottom-left"];
const CORNER_COLORS = ["#c45d3a", "#3d6b4f", "#2c5f8a", "#8a6b2c"];

let images = [];
let index = 0;
let corners = [];
let dragging = null;

const listEl = document.getElementById("image-list");
const labelEl = document.getElementById("image-label");
const hintEl = document.getElementById("step-hint");
const editorEl = document.getElementById("editor");
const imgEl = document.getElementById("source-img");
const overlayEl = document.getElementById("overlay");
const previewEl = document.getElementById("preview-img");

document.getElementById("btn-reset").onclick = () => {
  if (!imgEl.naturalWidth) return;
  corners = defaultCorners();
  drawOverlay();
  updateHint();
  previewEl.removeAttribute("src");
};

document.getElementById("btn-preview").onclick = () => preview();
document.getElementById("btn-save").onclick = () => save();

imgEl.addEventListener("load", () => {
  if (corners.length !== 4) corners = defaultCorners();
  drawOverlay();
  updateHint();
});

imgEl.addEventListener("error", () => {
  hintEl.textContent = "Could not load image — restart the server: npm run dev";
});

editorEl.addEventListener("click", (e) => {
  if (dragging !== null) return;
  const pt = pointerToImage(e.clientX, e.clientY);
  if (!pt) return;

  if (corners.length < 4) {
    corners.push(pt);
  } else {
    corners = [pt];
  }
  drawOverlay();
  updateHint();
});

editorEl.addEventListener("pointerdown", (e) => {
  const handle = e.target.closest(".crop-handle");
  if (!handle) return;
  dragging = Number(handle.dataset.i);
  handle.setPointerCapture(e.pointerId);
  e.preventDefault();
});

editorEl.addEventListener("pointermove", (e) => {
  if (dragging === null) return;
  const pt = pointerToImage(e.clientX, e.clientY);
  if (!pt) return;
  corners[dragging] = pt;
  drawOverlay();
});

editorEl.addEventListener("pointerup", () => {
  dragging = null;
});

window.addEventListener("keydown", (e) => {
  if (e.key === "ArrowLeft") selectImage(index - 1);
  if (e.key === "ArrowRight") selectImage(index + 1);
});

async function apiJson(url, opts) {
  const res = await fetch(url, opts);
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    if (text.trimStart().startsWith("<!")) {
      throw new Error("Crop API unavailable — restart the server: npm run dev");
    }
    throw new Error(res.ok ? "Invalid JSON response" : `Server error (${res.status})`);
  }
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

async function loadImages(selectIdx = 0) {
  images = await apiJson("/api/crop/images");
  listEl.innerHTML = images
    .map(
      (img, i) => `
    <li>
      <button type="button" class="crop-list-item${i === selectIdx ? " active" : ""}" data-i="${i}">
        ${img.name.replace(/-(ingredients|instructions)\.jpg$/, " · $1")}
      </button>
    </li>`,
    )
    .join("");

  listEl.querySelectorAll(".crop-list-item").forEach((btn) => {
    btn.onclick = () => selectImage(Number(btn.dataset.i));
  });

  if (images.length) selectImage(selectIdx);
}

function selectImage(i) {
  if (i < 0 || i >= images.length) return;
  index = i;
  const img = images[index];
  labelEl.textContent = img.name;
  corners = [];
  previewEl.removeAttribute("src");

  listEl.querySelectorAll(".crop-list-item").forEach((btn, j) => {
    btn.classList.toggle("active", j === index);
  });

  imgEl.src = `/api/crop/source?name=${encodeURIComponent(img.name)}&t=${Date.now()}`;
  overlayEl.innerHTML = "";
  updateHint();
}

function defaultCorners() {
  const w = imgEl.naturalWidth || 1000;
  const h = imgEl.naturalHeight || 1000;
  const m = 0.05;
  return [
    [w * m, h * m],
    [w * (1 - m), h * m],
    [w * (1 - m), h * (1 - m)],
    [w * m, h * (1 - m)],
  ];
}

function imageScale() {
  const rect = imgEl.getBoundingClientRect();
  const nw = imgEl.naturalWidth;
  const nh = imgEl.naturalHeight;
  if (!nw || !nh || rect.width <= 0 || rect.height <= 0) return null;
  return {
    sx: nw / rect.width,
    sy: nh / rect.height,
    dw: rect.width,
    dh: rect.height,
    rect,
  };
}

function pointerToImage(clientX, clientY) {
  const scale = imageScale();
  if (!scale) return null;
  const { sx, sy, rect } = scale;
  const x = (clientX - rect.left) * sx;
  const y = (clientY - rect.top) * sy;
  if (x < 0 || y < 0 || x > imgEl.naturalWidth || y > imgEl.naturalHeight) return null;
  return [Math.round(x), Math.round(y)];
}

function imageToDisplay(x, y) {
  const scale = imageScale();
  if (!scale) return [0, 0];
  return [x / scale.sx, y / scale.sy];
}

function drawOverlay() {
  const scale = imageScale();
  if (!scale) {
    overlayEl.removeAttribute("viewBox");
    overlayEl.innerHTML = "";
    return;
  }

  overlayEl.setAttribute("viewBox", `0 0 ${scale.dw} ${scale.dh}`);

  if (corners.length === 0) {
    overlayEl.innerHTML = "";
    return;
  }

  const pts = corners.map(([x, y]) => imageToDisplay(x, y));
  const poly = pts.map(([x, y]) => `${x},${y}`).join(" ");

  overlayEl.innerHTML = `
    ${corners.length === 4 ? `<polygon points="${poly}" class="crop-poly" />` : ""}
    ${pts
      .map(
        ([x, y], i) => `
      <circle cx="${x}" cy="${y}" r="10" class="crop-handle" data-i="${i}"
        fill="${CORNER_COLORS[i]}" stroke="white" stroke-width="2" />
      <text x="${x + 14}" y="${y + 5}" class="crop-label">${i + 1}</text>`,
      )
      .join("")}
  `;
}

function updateHint() {
  if (corners.length < 4) {
    hintEl.textContent = `Click corner ${corners.length + 1} of 4: ${CORNER_LABELS[corners.length]}`;
  } else {
    hintEl.textContent = "All four corners set — drag handles to adjust, then Preview or Save.";
  }
}

async function preview() {
  if (corners.length !== 4) {
    hintEl.textContent = "Set all four corners first.";
    return;
  }
  const name = images[index].name;
  const res = await fetch("/api/crop/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, corners }),
  });
  if (!res.ok) {
    hintEl.textContent = (await res.json().catch(() => ({}))).error || "Preview failed";
    return;
  }
  previewEl.src = URL.createObjectURL(await res.blob());
}

async function save() {
  if (corners.length !== 4) {
    hintEl.textContent = "Set all four corners first.";
    return;
  }
  const name = images[index].name;
  const res = await fetch("/api/crop/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, corners }),
  });
  if (!res.ok) {
    hintEl.textContent = (await res.json().catch(() => ({}))).error || "Save failed";
    return;
  }
  hintEl.textContent = "Saved!";
}

window.addEventListener("resize", () => {
  if (imgEl.naturalWidth) drawOverlay();
});
loadImages().catch((e) => {
  hintEl.textContent = e.message;
});
