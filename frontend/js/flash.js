// Flash drawer: talks to the host-side flash helper on 127.0.0.1:8765.
import { api, formatBytes } from "./api.js";
import { state, on, toast } from "./state.js";

const HELPER = "http://127.0.0.1:8765";

const backdrop = document.getElementById("flashBackdrop");
const drawer = document.getElementById("flashDrawer");
const steps = {
  helper: document.getElementById("flashStepHelper"),
  pair: document.getElementById("flashStepPair"),
  drive: document.getElementById("flashStepDrive"),
  progress: document.getElementById("flashStepProgress"),
  done: document.getElementById("flashStepDone"),
};

let token = localStorage.getItem("flashToken") || null;
let helperPoll = null;
let progressPoll = null;
let isoInfo = null;
let selectedDrive = null;

function showStep(name) {
  Object.entries(steps).forEach(([k, el]) => el.classList.toggle("hidden", k !== name));
}

async function helperFetch(path, options = {}) {
  const res = await fetch(HELPER + path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { "X-Flash-Token": token } : {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) { token = null; localStorage.removeItem("flashToken"); throw new Error("pairing required"); }
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

export async function openFlash() {
  if (!state.projectId) return;
  try {
    isoInfo = await api(`/api/projects/${state.projectId}/iso-info`);
  } catch (err) {
    toast(`No ISO to flash yet: ${err.message}`, "error");
    return;
  }
  backdrop.classList.remove("hidden");
  drawer.classList.remove("hidden");
  connectHelper();
}

function closeFlash() {
  backdrop.classList.add("hidden");
  drawer.classList.add("hidden");
  clearInterval(helperPoll);
  clearInterval(progressPoll);
}

async function connectHelper() {
  showStep("helper");
  clearInterval(helperPoll);
  const attempt = async () => {
    try {
      await fetch(HELPER + "/health").then((r) => r.json());
      clearInterval(helperPoll);
      if (token) {
        try { await showDrives(); return; } catch { /* token stale -> pair */ }
      }
      showStep("pair");
      document.getElementById("pairCode").focus();
    } catch { /* helper not up yet */ }
  };
  attempt();
  helperPoll = setInterval(attempt, 2500);
}

async function showDrives() {
  const summary = document.getElementById("flashIsoSummary");
  summary.innerHTML = `Flashing <strong>${isoInfo.filename}</strong> · ${formatBytes(isoInfo.size_bytes)} · verified sha-256`;
  await refreshDrives();
  showStep("drive");
}

async function refreshDrives() {
  const list = document.getElementById("driveList");
  const none = document.getElementById("driveNone");
  const confirmBtn = document.getElementById("confirmFlashBtn");
  selectedDrive = null;
  confirmBtn.classList.add("hidden");

  const { drives } = await helperFetch("/drives");
  list.innerHTML = "";
  none.classList.toggle("hidden", drives.length > 0);

  for (const d of drives) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "drive-card";
    card.innerHTML = `
      <svg class="drive-icon" viewBox="0 0 24 24" width="26" height="26"><rect x="4" y="7" width="13" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M17 10h3v4h-3" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="8" cy="12" r="1.4" fill="currentColor"/></svg>
      <div>
        <div class="drive-name">${escapeHtml(d.name)}</div>
        <div class="drive-size">${d.device} · ${formatBytes(d.size_bytes)}</div>
      </div>`;
    card.addEventListener("click", () => {
      selectedDrive = d;
      list.querySelectorAll(".drive-card").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
      confirmBtn.textContent = `Erase ${d.name} and flash`;
      confirmBtn.classList.remove("hidden");
    });
    list.appendChild(card);
  }
}

async function startFlash() {
  if (!selectedDrive || !isoInfo) return;
  try {
    await helperFetch("/flash", {
      method: "POST",
      body: {
        device: selectedDrive.device,
        download_url: `http://127.0.0.1:8000${isoInfo.download_path}`,
        sha256: isoInfo.sha256,
        size_bytes: isoInfo.size_bytes,
      },
    });
  } catch (err) {
    toast(`Flash couldn't start: ${err.message}`, "error");
    return;
  }
  showStep("progress");
  watchProgress();
}

function watchProgress() {
  clearInterval(progressPoll);
  const phaseEl = document.getElementById("flashPhase");
  const msgEl = document.getElementById("flashMessage");
  const fill = document.getElementById("flashFill");
  const pctEl = document.getElementById("flashPercent");
  const bytesEl = document.getElementById("flashBytes");

  const labels = {
    unmounting: ["Preparing", "Unmounting drive…"],
    writing: ["Writing", "Writing ISO to drive…"],
    verifying: ["Verifying", "Reading back and checking every byte…"],
    ejecting: ["Ejecting", "Ejecting drive…"],
  };

  progressPoll = setInterval(async () => {
    let p;
    try { p = await helperFetch("/progress"); } catch { return; }

    if (labels[p.state]) {
      phaseEl.textContent = labels[p.state][0];
      msgEl.textContent = labels[p.state][1];
      fill.style.width = `${p.percent || 0}%`;
      pctEl.textContent = `${p.percent || 0}%`;
      bytesEl.textContent = p.total_bytes
        ? `${formatBytes(p.bytes_done)} / ${formatBytes(p.total_bytes)}` : "";
    } else if (p.state === "done") {
      clearInterval(progressPoll);
      document.getElementById("flashDoneText").textContent = p.message;
      showStep("done");
    } else if (p.state === "error" || p.state === "cancelled") {
      clearInterval(progressPoll);
      toast(p.message || "Flash failed", "error", 8000);
      showDrives().catch(() => showStep("helper"));
    }
  }, 900);
}

// ------------------------------------------------------------------ wiring
document.getElementById("pairForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const code = document.getElementById("pairCode").value.trim();
  const errEl = document.getElementById("pairError");
  errEl.classList.add("hidden");
  try {
    const res = await helperFetch("/pair", { method: "POST", body: { code } });
    token = res.token;
    localStorage.setItem("flashToken", token);
    await showDrives();
  } catch (err) {
    errEl.textContent = err.message === "wrong pairing code"
      ? "That code doesn't match — check the helper terminal." : err.message;
    errEl.classList.remove("hidden");
  }
});

document.getElementById("refreshDrives").addEventListener("click", () =>
  refreshDrives().catch((err) => toast(err.message, "error")));
document.getElementById("confirmFlashBtn").addEventListener("click", startFlash);
document.getElementById("cancelFlashBtn").addEventListener("click", async () => {
  try { await helperFetch("/cancel", { method: "POST" }); } catch { /* ignore */ }
});
document.getElementById("closeFlashBtn").addEventListener("click", closeFlash);
document.getElementById("flashCloseDoneBtn").addEventListener("click", closeFlash);
backdrop.addEventListener("click", closeFlash);

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

on("open-flash", openFlash);
