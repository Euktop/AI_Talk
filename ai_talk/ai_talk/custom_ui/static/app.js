"use strict";

// AI_Talk CUSTOM UI.
// Ф5: lifecycle — браузер открывает сервер, клиент перепроверяет /health.
// Ф6: текущая строка + горячие клавиши A (Ctrl+Shift+C) и B (Ctrl+Shift+V).

const REFRESH_INTERVAL_MS = 2000;
const FLASH_DURATION_MS = 1500;

const els = {
  requests: document.getElementById("requests"),
  counter: document.getElementById("counter"),
  empty: document.getElementById("empty"),
  modal: document.getElementById("modal"),
  modalText: document.getElementById("modal-text"),
  modalClose: document.getElementById("modal-close"),
  modalCopy: document.getElementById("modal-copy"),
  modalDownload: document.getElementById("modal-download"),
};

let lastRenderedIds = "";
let rowsCache = [];
let currentIndex = 0;

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

async function postAnswer(id, answer) {
  const r = await fetch(
    "/api/requests/" + encodeURIComponent(id) + "/answer",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer: answer }),
    }
  );
  return r.ok;
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

async function readFromClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    return text || "";
  } catch (e) {
    console.warn("clipboard.readText failed", e);
    return null;
  }
}

// -------- UI helpers --------

function flash(el, cls) {
  if (!el) return;
  el.classList.remove("flash-ok", "flash-err");
  el.classList.add(cls);
  setTimeout(() => el.classList.remove(cls), FLASH_DURATION_MS);
}

function setCounter(n) {
  els.counter.textContent =
    n + " " + plural(n, ["активный", "активных", "активных"]);
}

function plural(n, forms) {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return forms[0];
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
  return forms[2];
}

function rowAt(idx) {
  return els.requests.querySelectorAll(".row")[idx];
}

function applyCurrentHighlight() {
  const rows = els.requests.querySelectorAll(".row");
  rows.forEach((row, idx) => {
    row.classList.toggle("current", idx === currentIndex);
  });
}

function setCurrentIndex(i) {
  const n = rowsCache.length;
  if (n === 0) {
    currentIndex = 0;
    return;
  }
  if (i < 0) i = n - 1;
  if (i >= n) i = 0;
  currentIndex = i;
  applyCurrentHighlight();
}

// -------- Actions --------

async function handleCopy(rowEl, requestId, rowIndex, isHotkey) {
  setCurrentIndex(rowIndex);
  const isLast = rowIndex === rowsCache.length - 1;
  let text;
  if (isHotkey && isLast) {
    // Спека: на горячей клавише A на последней строке копируется пустая строка.
    text = "";
  } else {
    text = await fetchRaw(requestId);
  }
  const ok = await copyToClipboard(text);
  flash(rowEl, ok ? "flash-ok" : "flash-err");
  setCurrentIndex(isLast ? 0 : rowIndex + 1);
}

async function handlePaste(rowEl, requestId, rowIndex) {
  setCurrentIndex(rowIndex);
  const text = await readFromClipboard();
  if (text === null || !text.trim()) {
    flash(rowEl, "flash-err");
    return;
  }
  const ok = await postAnswer(requestId, text);
  flash(rowEl, ok ? "flash-ok" : "flash-err");
  // После успеха следующий tick уберёт строку.
  // currentIndex остаётся тем же — теперь указывает на следующую строку.
}

async function handleOpenModal(requestId) {
  try {
    const full = await fetchRaw(requestId);
    els.modalText.textContent = full;
    els.modalText.dataset.requestId = requestId;
    els.modal.showModal();
  } catch (e) {
    console.error(e);
  }
}

// -------- Hotkeys --------

async function copyCurrent() {
  if (rowsCache.length === 0) return;
  const req = rowsCache[currentIndex];
  await handleCopy(rowAt(currentIndex), req.id, currentIndex, true);
}

async function pasteIntoCurrent() {
  if (rowsCache.length === 0) return;
  const req = rowsCache[currentIndex];
  await handlePaste(rowAt(currentIndex), req.id, currentIndex);
}

// e.code — физическая клавиша (KeyC, KeyV), не зависит от раскладки.
// e.key на русской раскладке даёт "С"/"В" (кириллица).
document.addEventListener("keydown", (e) => {
  if (els.modal.open) return;
  if (e.ctrlKey && e.shiftKey && e.code === "KeyC") {
    e.preventDefault();
    e.stopPropagation();
    copyCurrent();
  } else if (e.ctrlKey && e.shiftKey && e.code === "KeyV") {
    e.preventDefault();
    e.stopPropagation();
    pasteIntoCurrent();
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    setCurrentIndex(currentIndex + 1);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    setCurrentIndex(currentIndex - 1);
  }
});

// -------- Render --------

function createRow(req, idx) {
  const li = document.createElement("li");
  li.className = "row";
  li.dataset.id = req.id;

  const questionBtn = document.createElement("button");
  questionBtn.className = "btn btn-question";
  questionBtn.type = "button";
  questionBtn.textContent = "?";
  questionBtn.title = "Показать полный запрос";
  questionBtn.setAttribute("aria-label", "Полный запрос");
  questionBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    handleOpenModal(req.id);
  });

  const text = document.createElement("div");
  text.className = "text";
  text.textContent = req.preview;
  text.title = "Клик — сделать текущим и скопировать";
  text.addEventListener("click", () => handleCopy(li, req.id, idx, false));

  const copyBtn = document.createElement("button");
  copyBtn.className = "btn btn-copy";
  copyBtn.type = "button";
  copyBtn.textContent = "📋";
  copyBtn.title = "Копировать";
  copyBtn.setAttribute("aria-label", "Копировать");
  copyBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    handleCopy(li, req.id, idx, false);
  });

  const pasteBtn = document.createElement("button");
  pasteBtn.className = "btn btn-paste";
  pasteBtn.type = "button";
  pasteBtn.textContent = "📥";
  pasteBtn.title = "Вставить ответ из буфера";
  pasteBtn.setAttribute("aria-label", "Вставить ответ");
  pasteBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    handlePaste(li, req.id, idx);
  });

  li.appendChild(questionBtn);
  li.appendChild(text);
  li.appendChild(copyBtn);
  li.appendChild(pasteBtn);
  return li;
}

function render(reqs) {
  rowsCache = reqs;
  setCounter(reqs.length);

  if (reqs.length === 0) {
    if (lastRenderedIds !== "") {
      els.requests.innerHTML = "";
      lastRenderedIds = "";
    }
    els.empty.classList.add("visible");
    currentIndex = 0;
    return;
  }
  els.empty.classList.remove("visible");

  if (currentIndex >= reqs.length) currentIndex = 0;

  const idsKey = reqs.map((r) => r.id).join(",");
  if (idsKey === lastRenderedIds) {
    applyCurrentHighlight();
    return;
  }
  lastRenderedIds = idsKey;

  const frag = document.createDocumentFragment();
  reqs.forEach((r, idx) => frag.appendChild(createRow(r, idx)));
  els.requests.innerHTML = "";
  els.requests.appendChild(frag);
  applyCurrentHighlight();
}

// -------- Modal wiring --------

els.modalClose.addEventListener("click", () => els.modal.close());

els.modalCopy.addEventListener("click", async () => {
  const ok = await copyToClipboard(els.modalText.textContent);
  flash(els.modalCopy, ok ? "flash-ok" : "flash-err");
});

els.modalDownload.addEventListener("click", () => {
  const rid = (els.modalText.dataset.requestId || "request").slice(0, 8);
  const blob = new Blob([els.modalText.textContent], {
    type: "text/plain;charset=utf-8",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "request-" + rid + ".txt";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
});

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
