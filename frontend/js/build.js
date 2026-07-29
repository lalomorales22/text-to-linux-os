// Build view: start builds, stream logs, show verification proof.
import { api, streamSSE } from "./api.js";
import { state, on, emit, showView, setPipeline, toast } from "./state.js";

const buildStep = document.getElementById("buildStep");
const buildEyebrow = document.getElementById("buildEyebrow");
const progressFill = document.getElementById("buildProgressFill");
const buildPercent = document.getElementById("buildPercent");
const buildTimer = document.getElementById("buildTimer");
const logBody = document.getElementById("logBody");
const verifyPanel = document.getElementById("verifyPanel");
const verifyGrid = document.getElementById("verifyGrid");
const doneRow = document.getElementById("doneRow");
const failPanel = document.getElementById("failPanel");
const failText = document.getElementById("failText");
const cancelBtn = document.getElementById("cancelBuildBtn");

let timerHandle = null;
let streamAbort = null;

function startTimer(fromIso) {
  const started = fromIso ? new Date(fromIso).getTime() : Date.now();
  clearInterval(timerHandle);
  timerHandle = setInterval(() => {
    const s = Math.floor((Date.now() - started) / 1000);
    buildTimer.textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  }, 1000);
}

function resetBuildView() {
  progressFill.style.width = "0%";
  progressFill.className = "progress-fill";
  buildPercent.textContent = "0%";
  buildTimer.textContent = "";
  logBody.textContent = "";
  verifyPanel.classList.add("hidden");
  verifyGrid.innerHTML = "";
  doneRow.classList.add("hidden");
  failPanel.classList.add("hidden");
  cancelBtn.classList.remove("hidden");
  buildEyebrow.textContent = "Building";
  buildStep.textContent = "Preparing…";
}

export async function startBuild() {
  if (!state.projectId) return;
  try {
    const res = await api("/api/builds", {
      method: "POST",
      body: { project_id: state.projectId },
    });
    monitorBuild(res.build_id);
  } catch (err) {
    toast(`Build couldn't start: ${err.message}`, "error");
  }
}

export function monitorBuild(buildId, startedAt) {
  state.activeBuildId = buildId;
  resetBuildView();
  showView("build");
  setPipeline({ configure: "done", build: "active" });
  startTimer(startedAt);

  streamAbort?.abort();
  streamAbort = new AbortController();

  streamSSE(`/api/builds/${buildId}/logs/stream`, { signal: streamAbort.signal }, (event) => {
    if (event.type === "log") {
      logBody.textContent += event.line + "\n";
      logBody.scrollTop = logBody.scrollHeight;
    } else if (event.type === "status") {
      progressFill.style.width = `${event.progress}%`;
      buildPercent.textContent = `${event.progress}%`;
      buildStep.textContent = event.step;
      if (event.status === "testing") {
        buildEyebrow.textContent = "Verifying";
        progressFill.classList.add("testing");
        setPipeline({ configure: "done", build: "done", verify: "active" });
      }
    } else if (event.type === "done") {
      finishBuild(event);
    }
  }).catch((err) => {
    if (err.name !== "AbortError") {
      toast(`Lost connection to the build stream: ${err.message}`, "error");
    }
  });
}

function finishBuild(event) {
  clearInterval(timerHandle);
  cancelBtn.classList.add("hidden");

  if (event.status === "completed") {
    buildEyebrow.textContent = "Complete";
    buildStep.textContent = "Your ISO is built and verified";
    progressFill.style.width = "100%";
    document.getElementById("logPanel").removeAttribute("open");
    renderBootProof(event.boot_test);
    doneRow.classList.remove("hidden");
    setPipeline({ configure: "done", build: "done",
                  verify: event.boot_test?.passed ? "done" : "active",
                  flash: "active" });
  } else if (event.status === "cancelled") {
    buildEyebrow.textContent = "Cancelled";
    buildStep.textContent = "Build cancelled";
    progressFill.classList.add("failed");
    doneRow.classList.remove("hidden");
    document.getElementById("openFlashBtn").classList.add("hidden");
    document.getElementById("downloadBtn").classList.add("hidden");
  } else {
    buildEyebrow.textContent = "Failed";
    buildStep.textContent = "The build hit a problem";
    progressFill.classList.add("failed");
    failText.textContent = event.error || "Unknown failure — check the build log.";
    failPanel.classList.remove("hidden");
    document.getElementById("logPanel").setAttribute("open", "");
  }
  emit("build-finished", event);
}

function renderBootProof(bootTest) {
  if (!bootTest || bootTest.available === false) {
    verifyPanel.classList.add("hidden");
    return;
  }
  verifyPanel.classList.remove("hidden");
  verifyGrid.innerHTML = "";
  for (const [mode, result] of Object.entries(bootTest.modes || {})) {
    const card = document.createElement("div");
    card.className = "boot-proof";
    const shot = result.screenshot
      ? `<img src="/api/builds/${state.activeBuildId}/screenshot/${mode}" alt="Boot screenshot (${mode})" />`
      : `<div class="no-shot">no screenshot captured</div>`;
    const verdict = result.skipped
      ? `<span class="skip">— ${mode.toUpperCase()} skipped</span>`
      : result.passed
        ? `<span class="ok">✓ boots in ${mode.toUpperCase()}</span>`
        : `<span class="bad">✗ ${mode.toUpperCase()} did not finish booting</span>`;
    card.innerHTML = `<div class="boot-bezel">${shot}</div>
                      <div class="boot-caption">${verdict}</div>`;
    if (!result.passed && !result.skipped && result.message) {
      card.title = result.message;
    }
    verifyGrid.appendChild(card);
  }
}

cancelBtn.addEventListener("click", async () => {
  if (!state.activeBuildId) return;
  try {
    await api(`/api/builds/${state.activeBuildId}/cancel`, { method: "POST" });
    toast("Cancelling build…");
  } catch (err) {
    toast(err.message, "error");
  }
});

document.getElementById("downloadBtn").addEventListener("click", () => {
  window.location.href = `/api/projects/${state.projectId}/download`;
});
document.getElementById("openFlashBtn").addEventListener("click", () => emit("open-flash"));
document.getElementById("backToForgeBtn").addEventListener("click", () => backToForge());
document.getElementById("failBackBtn").addEventListener("click", () => backToForge());
document.getElementById("retryBtn").addEventListener("click", () => {
  backToForge();
  document.getElementById("chatInput").value = "The build failed — can you adjust the configuration to fix it?";
  document.getElementById("chatInput").focus();
});

function backToForge() {
  streamAbort?.abort();
  setPipeline({ configure: "active" });
  showView("forge");
}

on("start-build", startBuild);
