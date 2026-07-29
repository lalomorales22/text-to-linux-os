// Build sheet: the live configuration summary + theme panel + build button.
import { api } from "./api.js";
import { state, on, emit, toast } from "./state.js";

const sheetStatus = document.getElementById("sheetStatus");
const sheetEmpty = document.getElementById("sheetEmpty");
const sheetBody = document.getElementById("sheetBody");
const buildBtn = document.getElementById("buildBtn");
const buildHint = document.getElementById("buildHint");
const swatchRow = document.getElementById("swatchRow");

const MAX_MB = 3 * 1024;
const SWATCH_KEYS = ["primary", "secondary", "accent", "background"];

function renderConfig(config, ready) {
  sheetEmpty.classList.add("hidden");
  sheetBody.classList.remove("hidden");

  document.getElementById("sheetHostname").textContent = config.hostname || "—";
  document.getElementById("sheetUsername").textContent = config.username || "—";
  document.getElementById("sheetUseCase").textContent = config.use_case || "—";

  const hw = config.hardware || {};
  document.getElementById("sheetHardware").textContent =
    [hw.ram_gb && `${hw.ram_gb} GB RAM`, hw.cpu && `${hw.cpu} CPU`,
     hw.storage && hw.storage.toUpperCase(), hw.boot && `${hw.boot} boot`]
      .filter(Boolean).join(" · ") || "—";

  const packages = config.packages || [];
  document.getElementById("sheetPkgCount").textContent = packages.length ? `(${packages.length})` : "";
  const pkgList = document.getElementById("sheetPackages");
  pkgList.innerHTML = "";
  if (packages.length) {
    for (const p of packages) {
      const el = document.createElement("span");
      el.className = "pkg";
      el.textContent = p;
      pkgList.appendChild(el);
    }
  } else {
    pkgList.textContent = "base system only";
  }

  const mb = config.size_estimate_mb || 0;
  const fill = document.getElementById("sizeFill");
  const pct = Math.min(100, (mb / MAX_MB) * 100);
  fill.style.width = `${pct}%`;
  fill.classList.toggle("warn", pct > 70 && pct <= 95);
  fill.classList.toggle("over", pct > 95);
  document.getElementById("sizeLabel").textContent = mb
    ? `~${mb >= 1024 ? (mb / 1024).toFixed(1) + " GB" : mb + " MB"}` : "—";

  sheetStatus.textContent = ready ? "ready" : "configuring";
  sheetStatus.className = `sheet-status ${ready ? "ready" : "configuring"}`;

  buildBtn.disabled = false;
  buildHint.textContent = ready
    ? "Configuration confirmed. Ready when you are."
    : "You can build now, or keep refining in chat.";
}

export function resetSheet() {
  sheetEmpty.classList.remove("hidden");
  sheetBody.classList.add("hidden");
  sheetStatus.textContent = "empty";
  sheetStatus.className = "sheet-status";
  buildBtn.disabled = true;
  buildHint.textContent = "The build button unlocks once the configuration is confirmed.";
  renderTheme(null);
}

// ------------------------------------------------------------------- theme
function renderTheme(theme) {
  swatchRow.innerHTML = "";
  for (const key of SWATCH_KEYS) {
    const wrap = document.createElement("div");
    wrap.className = "swatch-wrap";
    const color = theme?.[key] || "#242c38";
    wrap.innerHTML = `
      <span class="swatch" style="background:${color}"></span>
      <input type="color" value="${color}" aria-label="${key} color" />
      <span class="swatch-label">${key}</span>`;
    wrap.querySelector("input").addEventListener("input", (e) => {
      const updated = { ...(state.theme || {}), [key]: e.target.value, terminal: null };
      saveTheme(updated);
    });
    swatchRow.appendChild(wrap);
  }
}

async function saveTheme(theme) {
  state.theme = theme;
  renderTheme(theme);
  if (state.projectId) {
    try {
      const res = await api(`/api/projects/${state.projectId}/theme`, {
        method: "PUT", body: { theme: { ...theme, terminal: theme.terminal || {} } },
      });
      state.theme = res.theme;
      renderTheme(res.theme);
    } catch (err) {
      toast(`Couldn't save theme: ${err.message}`, "error");
    }
  }
}

document.getElementById("randomizeTheme").addEventListener("click", async () => {
  const res = await api("/api/projects/theme/randomize", { method: "POST" });
  saveTheme(res.theme);
});

buildBtn.addEventListener("click", () => emit("start-build"));

on("config", ({ config, ready }) => renderConfig(config, ready));
on("theme", (theme) => renderTheme(theme));

renderTheme(null);
