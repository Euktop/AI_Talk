"use strict";

// AI_Talk CUSTOM UI — список запросов, копирование, автообновление.
// Модалка [?], вставка [📥] и горячие клавиши — в следующих фазах.

const REFRESH_INTERVAL_MS = 2000;
const FLASH_DURATION_MS = 1500;

const els = {
  requests: document.getElementById("requests"),
  counter: document.getElementById("counter"),
  empty: document.getElementById("empty"),
};

let lastRenderedIds = "";

// -------- API --------

async function fetchRequests() {
  const r = await fetch("/api/requests", { cache: "no-store" });
  if (!r.ok) throw new Error("GET /api/requests failed: " + r.status);
  return await r.json();
}

async function fetchRaw(id) {
  const r = await fetch(
    "/api/requests/" + encodeURIComponent(id) + "/raw",
    { cache: "no-store" }
  );
  if (!r.ok) throw new Error("GET raw failed: " + r.status);
  return await r.text();
}

// -------- Clipboard --------

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    console.warn("clipboard.writeText failed", e);
    return false;
  }
}

// -------- UI helpers --------

function flash(el, cls) {
  el.classList.remove("flash-ok", "flash-err");
  el.classList.add(cls);
  setTimeout(() => el.classList.remove(cls), FLASH_DURATION_MS);
}

function setCounter(n) {
  els.counter.textContent = n + " " + plural(n, ["активный", "активных", "активных"]);
}

function plural(n, forms) {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return forms[0];
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
  return forms[2];
}

// -------- Render --------

function createRow(req) {
  const li = document.createElement("li");
  li.className = "row";
  li.dataset.id = req.id;

  const text = document.createElement("div");
  text.className = "text";
  text.textContent = req.preview;
  text.title = "Клик — скопировать полный текст";
  text.addEventListener("click", () => handleCopy(li, req.id));

  const copyBtn = document.createElement("button");
  copyBtn.className = "btn btn-copy";
  copyBtn.type = "button";
  copyBtn.textContent = "📋";
  copyBtn.title = "Копировать";
  copyBtn.setAttribute("aria-label", "Копировать");
  copyBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    handleCopy(li, req.id);
  });

  li.appendChild(text);
  li.appendChild(copyBtn);
  return li;
}

async function handleCopy(rowEl, requestId) {
  try {
    const full = await fetchRaw(requestId);
    const ok = await copyToClipboard(full);
    flash(rowEl, ok ? "flash-ok" : "flash-err");
  } catch (e) {
    console.error(e);
    flash(rowEl, "flash-err");
  }
}

function render(reqs) {
  setCounter(reqs.length);

  if (reqs.length === 0) {
    if (lastRenderedIds !== "") {
      els.requests.innerHTML = "";
      lastRenderedIds = "";
    }
    els.empty.classList.add("visible");
    return;
  }
  els.empty.classList.remove("visible");

  const idsKey = reqs.map((r) => r.id).join(",");
  if (idsKey === lastRenderedIds) return;
  lastRenderedIds = idsKey;

  const frag = document.createDocumentFragment();
  for (const r of reqs) frag.appendChild(createRow(r));
  els.requests.innerHTML = "";
  els.requests.appendChild(frag);
}

// -------- Loop --------

async function tick() {
  try {
    const reqs = await fetchRequests();
    render(reqs);
  } catch (e) {
    console.error("tick failed", e);
  }
}

tick();
setInterval(tick, REFRESH_INTERVAL_MS);
