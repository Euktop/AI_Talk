"use strict";

// AI_Talk CUSTOM UI.
// Ф5 lifecycle; Ф6 hotkeys; Ф7 PiP + звуки; Ф8 server-status + PiP bridge;
// Ф9 diff-render + stable current by id.

const REFRESH_INTERVAL_MS = 2000;
const FLASH_DURATION_MS = 1500;
const POST_PASTE_DELAY_MS = 250;
const MAX_FAILURES = 3;

const els = {
  requests: document.getElementById("requests"),
  counter: document.getElementById("counter"),
  empty: document.getElementById("empty"),
  modal: document.getElementById("modal"),
  modalText: document.getElementById("modal-text"),
  modalClose: document.getElementById("modal-close"),
  modalCopy: document.getElementById("modal-copy"),
  modalDownload: document.getElementById("modal-download"),
  pipBtn: document.getElementById("pip-btn"),
  serverStatus: document.getElementById("server-status"),
};

let lastRenderedIds = "";
let rowsCache = [];
let currentIndex = 0;
let currentId = null;
let consecutiveFailures = 0;

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

// -------- Sound (Web Audio API, без файлов) --------

let audioCtx = null;

function _ensureAudioCtx() {
  if (!audioCtx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    audioCtx = new Ctx();
  }
  return audioCtx;
}

function playTone(freq, durationMs) {
  const ctx = _ensureAudioCtx();
  if (!ctx) return;
  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    osc.connect(gain);
    gain.connect(ctx.destination);
    const now = ctx.currentTime;
    const dur = durationMs / 1000;
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.linearRampToValueAtTime(0.12, now + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + dur);
    osc.start(now);
    osc.stop(now + dur);
  } catch (e) {
    console.warn("playTone failed", e);
  }
}

function soundCopy() { playTone(880, 100); }
function soundPaste() { playTone(660, 100); }
function soundError() { playTone(220, 180); }

// -------- Clipboard --------
// PiP — отдельный browsing context со своим transient activation.
// Клик в PiP активирует PiP, но не main. Поэтому clipboard-вызовы
// исполняем внутри PiP через мост `window.__aiTalkPip`, который
// инжектится в PiP при открытии.

function _pipBridge() {
  if (!document.body.classList.contains("pip-active")) return null;
  if (!("documentPictureInPicture" in window)) return null;
  const pipWin = window.documentPictureInPicture.window;
  if (!pipWin || !pipWin.__aiTalkPip) return null;
  return pipWin.__aiTalkPip;
}

async function copyToClipboard(text) {
  const bridge = _pipBridge();
  if (bridge) return await bridge.copy(text);
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    console.warn("clipboard.writeText failed", e);
    return false;
  }
}

async function readFromClipboard() {
  const bridge = _pipBridge();
  if (bridge) return await bridge.paste();
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

function findIndexById(id) {
  for (let i = 0; i < rowsCache.length; i++) {
    if (rowsCache[i].id === id) return i;
  }
  return -1;
}

function applyCurrentHighlight() {
  const rows = els.requests.querySelectorAll(".row");
  rows.forEach((row) => {
    row.classList.toggle("current", row.dataset.id === currentId);
  });
}

function setCurrentIndex(i) {
  const n = rowsCache.length;
  if (n === 0) {
    currentIndex = 0;
    currentId = null;
    return;
  }
  if (i < 0) i = n - 1;
  if (i >= n) i = 0;
  currentIndex = i;
  currentId = rowsCache[i].id;
  applyCurrentHighlight();
}

// -------- Actions --------

async function handleCopy(rowEl, requestId, isHotkey) {
  const idx = findIndexById(requestId);
  if (idx >= 0) setCurrentIndex(idx);

  const isLast = idx === rowsCache.length - 1;
  let text;
  try {
    if (isHotkey && isLast) {
      // Спека: на горячей клавише A на последней строке копируется пустая строка.
      text = "";
    } else {
      text = await fetchRaw(requestId);
    }
  } catch (e) {
    console.error("handleCopy fetch failed", e);
    flash(rowEl, "flash-err");
    soundError();
    return;
  }
  const ok = await copyToClipboard(text);
  flash(rowEl, ok ? "flash-ok" : "flash-err");
  if (ok) soundCopy(); else soundError();
  if (isLast) {
    setCurrentIndex(0);
  } else {
    setCurrentIndex(idx + 1);
  }
}

async function handlePaste(rowEl, requestId) {
  const idx = findIndexById(requestId);
  if (idx >= 0) setCurrentIndex(idx);

  const text = await readFromClipboard();
  if (text === null || !text.trim()) {
    flash(rowEl, "flash-err");
    soundError();
    return;
  }
  let ok;
  try {
    ok = await postAnswer(requestId, text);
  } catch (e) {
    console.error("postAnswer failed", e);
    ok = false;
  }
  flash(rowEl, ok ? "flash-ok" : "flash-err");
  if (ok) {
    soundPaste();
    // Не ждём REFRESH_INTERVAL_MS: обновляем список почти сразу,
    // чтобы задача не «висела» 2 секунды после ответа.
    setTimeout(tick, POST_PASTE_DELAY_MS);
  } else {
    soundError();
  }
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
  const req = rowsCache.find((r) => r.id === currentId) || rowsCache[currentIndex];
  if (!req) return;
  await handleCopy(rowAt(currentIndex), req.id, true);
}

async function pasteIntoCurrent() {
  if (rowsCache.length === 0) return;
  const req = rowsCache.find((r) => r.id === currentId) || rowsCache[currentIndex];
  if (!req) return;
  await handlePaste(rowAt(currentIndex), req.id);
}

function installKeydown(doc) {
  doc.addEventListener("keydown", (e) => {
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
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      copyCurrent();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      pasteIntoCurrent();
    }
  });
}

installKeydown(document);

// -------- PiP --------

function _copyStylesToPip(pipWin) {
  const link = pipWin.document.createElement("link");
  link.rel = "stylesheet";
  link.href = "/static/style.css";
  pipWin.document.head.appendChild(link);
}

function _installPiPClipboardBridge(pipWin) {
  const src = [
    "(function(){",
    "  window.__aiTalkPip = {",
    "    copy: function(text){",
    "      return navigator.clipboard.writeText(text).then(",
    "        function(){ return true; },",
    "        function(e){ console.warn('pip clipboard.writeText', e); return false; }",
    "      );",
    "    },",
    "    paste: function(){",
    "      return navigator.clipboard.readText().then(",
    "        function(t){ return t || ''; },",
    "        function(e){ console.warn('pip clipboard.readText', e); return null; }",
    "      );",
    "    }",
    "  };",
    "})();",
  ].join("\n");
  const s = pipWin.document.createElement("script");
  s.textContent = src;
  pipWin.document.head.appendChild(s);
}

async function togglePiP() {
  if (!("documentPictureInPicture" in window)) {
    flash(els.pipBtn, "flash-err");
    soundError();
    return;
  }
  const existing = window.documentPictureInPicture.window;
  if (existing) {
    existing.close();
    return;
  }
  try {
    const pipWin = await window.documentPictureInPicture.requestWindow({
      width: 420,
      height: 600,
    });
    _copyStylesToPip(pipWin);
    _installPiPClipboardBridge(pipWin);
    pipWin.document.title = "AI_Talk";

    pipWin.document.body.append(els.requests, els.empty);
    document.body.classList.add("pip-active");
    els.pipBtn.classList.add("active");

    installKeydown(pipWin.document);

    pipWin.addEventListener("pagehide", () => {
      document.body.classList.remove("pip-active");
      els.pipBtn.classList.remove("active");
      const main = document.querySelector("main.main");
      if (main) {
        main.append(els.requests, els.empty);
      }
    });
  } catch (e) {
    console.error("PiP failed", e);
    flash(els.pipBtn, "flash-err");
    soundError();
  }
}

els.pipBtn.addEventListener("click", togglePiP);

// -------- Render (diff) --------

function createRow(req) {
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
  text.addEventListener("click", () => handleCopy(li, req.id, false));

  const copyBtn = document.createElement("button");
  copyBtn.className = "btn btn-copy";
  copyBtn.type = "button";
  copyBtn.textContent = "📋";
  copyBtn.title = "Копировать";
  copyBtn.setAttribute("aria-label", "Копировать");
  copyBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    handleCopy(li, req.id, false);
  });

  const pasteBtn = document.createElement("button");
  pasteBtn.className = "btn btn-paste";
  pasteBtn.type = "button";
  pasteBtn.textContent = "📥";
  pasteBtn.title = "Вставить ответ из буфера";
  pasteBtn.setAttribute("aria-label", "Вставить ответ");
  pasteBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    handlePaste(li, req.id);
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
    els.requests.innerHTML = "";
    els.empty.classList.add("visible");
    currentIndex = 0;
    currentId = null;
    lastRenderedIds = "";
    return;
  }
  els.empty.classList.remove("visible");

  // Подсветка по id: если текущая задача исчезла — привязываемся к той,
  // что теперь стоит на той же позиции (или к началу, если ушли за край).
  if (currentId === null || findIndexById(currentId) < 0) {
    if (currentIndex >= reqs.length) currentIndex = 0;
    if (currentIndex < 0) currentIndex = 0;
    currentId = reqs[currentIndex].id;
  } else {
    currentIndex = findIndexById(currentId);
  }

  const idsKey = reqs.map((r) => r.id).join(",");
  if (idsKey === lastRenderedIds) {
    applyCurrentHighlight();
    return;
  }
  lastRenderedIds = idsKey;

  // Diff-render: переиспользуем DOM-элементы, не пересоздаём список
  // целиком. Так не сбрасываются hover, flash-анимация, scroll.
  const existing = Array.from(els.requests.children);
  const byId = new Map();
  existing.forEach((li) => byId.set(li.dataset.id, li));

  // Удалить исчезнувшие
  existing.forEach((li) => {
    if (!reqs.find((r) => r.id === li.dataset.id)) {
      li.remove();
    }
  });

  // Вставить/переставить/обновить превью
  reqs.forEach((r, idx) => {
    let li = byId.get(r.id);
    if (!li) {
      li = createRow(r);
    } else {
      const textEl = li.querySelector(".text");
      if (textEl && textEl.textContent !== r.preview) {
        textEl.textContent = r.preview;
      }
    }
    const currentAtIdx = els.requests.children[idx];
    if (currentAtIdx !== li) {
      els.requests.insertBefore(li, currentAtIdx || null);
    }
  });

  applyCurrentHighlight();
}

// -------- Modal wiring --------

els.modalClose.addEventListener("click", () => els.modal.close());

els.modalCopy.addEventListener("click", async () => {
  const ok = await copyToClipboard(els.modalText.textContent);
  flash(els.modalCopy, ok ? "flash-ok" : "flash-err");
  if (ok) soundCopy(); else soundError();
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

// -------- Server status --------

function setServerStatus(online) {
  if (!els.serverStatus) return;
  if (online) {
    els.serverStatus.classList.remove("visible");
    els.serverStatus.textContent = "";
  } else {
    els.serverStatus.textContent = "Сервер AI_Talk отключён. Закройте вкладку.";
    els.serverStatus.classList.add("visible");
  }
}

function closePiPIfOpen() {
  if (!("documentPictureInPicture" in window)) return;
  const pipWin = window.documentPictureInPicture.window;
  if (pipWin) {
    try { pipWin.close(); } catch (e) { /* ignore */ }
  }
}

window.addEventListener("pagehide", closePiPIfOpen);

// -------- Loop --------

async function tick() {
  try {
    const reqs = await fetchRequests();
    consecutiveFailures = 0;
    setServerStatus(true);
    render(reqs);
  } catch (e) {
    consecutiveFailures++;
    console.error("tick failed", e);
    if (consecutiveFailures >= MAX_FAILURES) {
      setServerStatus(false);
      closePiPIfOpen();
    }
  }
}

tick();
setInterval(tick, REFRESH_INTERVAL_MS);
