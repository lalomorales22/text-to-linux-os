// Gallery: every system you've made, with live build reattach.
import { api, formatBytes } from "./api.js";
import { state, on, emit, showView, setPipeline, setPipelineProject, toast } from "./state.js";
import { openProject, resetChat } from "./chat.js";
import { resetSheet } from "./sheet.js";
import { monitorBuild } from "./build.js";

const grid = document.getElementById("galleryGrid");
const empty = document.getElementById("galleryEmpty");

export async function loadGallery() {
  let projects = [];
  try {
    ({ projects } = await api("/api/projects"));
  } catch (err) {
    toast(`Couldn't load projects: ${err.message}`, "error");
    return;
  }
  empty.classList.toggle("hidden", projects.length > 0);
  grid.innerHTML = "";
  for (const p of projects) grid.appendChild(renderCard(p));
}

function renderCard(p) {
  const card = document.createElement("div");
  card.className = "project-card";

  const created = new Date(p.created_at).toLocaleDateString();
  const size = p.latest_version?.iso_size ? formatBytes(p.latest_version.iso_size) : null;
  const themeColors = p.theme_config
    ? ["primary", "secondary", "accent", "background"]
        .map((k) => p.theme_config[k]).filter(Boolean)
    : [];

  card.innerHTML = `
    <div class="project-card-top">
      <div class="project-name" data-role="name">${escapeHtml(p.name)}</div>
      <span class="status-pill ${p.status}">${p.status}</span>
    </div>
    <div class="project-meta">
      <span>created ${created}</span>
      ${p.latest_version ? `<span>v${p.latest_version.version_number}</span>` : ""}
      ${size ? `<span>${size}</span>` : ""}
    </div>
    ${themeColors.length ? `<div class="theme-dots">${themeColors.map((c) => `<span style="background:${c}"></span>`).join("")}</div>` : ""}
    ${p.active_build_id ? `
      <div class="card-progress">
        <div class="progress-track"><div class="progress-fill" style="width:0%"></div></div>
        <span data-role="pct">…</span>
      </div>` : ""}
    <div class="project-actions">
      <button class="btn btn-ghost btn-sm" data-act="open">Open</button>
      ${p.active_build_id ? `<button class="btn btn-ghost btn-sm" data-act="watch">Watch build</button>` : ""}
      ${p.has_iso ? `<button class="btn btn-primary btn-sm" data-act="download">Download ISO</button>` : ""}
      ${p.has_iso ? `<button class="btn btn-flash btn-sm" data-act="flash">Flash</button>` : ""}
      <button class="btn btn-ghost btn-sm" data-act="rename">Rename</button>
      <button class="btn btn-ghost btn-sm" data-act="delete">Delete</button>
    </div>`;

  card.querySelector('[data-act="open"]').addEventListener("click", () => openInForge(p));
  card.querySelector('[data-act="watch"]')?.addEventListener("click", async () => {
    await openInForge(p, { silent: true });
    monitorBuild(p.active_build_id);
  });
  card.querySelector('[data-act="download"]')?.addEventListener("click", () => {
    window.location.href = `/api/projects/${p.id}/download`;
  });
  card.querySelector('[data-act="flash"]')?.addEventListener("click", async () => {
    await openInForge(p, { silent: true });
    emit("open-flash");
  });
  card.querySelector('[data-act="rename"]').addEventListener("click", () => beginRename(card, p));
  card.querySelector('[data-act="delete"]').addEventListener("click", async () => {
    if (!confirm(`Delete "${p.name}" and its builds? This can't be undone.`)) return;
    await api(`/api/projects/${p.id}`, { method: "DELETE" });
    if (state.projectId === p.id) {
      state.projectId = null; state.config = null; state.theme = null;
      resetChat(); resetSheet(); setPipelineProject("");
    }
    loadGallery();
  });

  if (p.active_build_id) pollCardProgress(card, p.active_build_id);
  return card;
}

async function openInForge(p, { silent = false } = {}) {
  try {
    await openProject(p.id);
    setPipelineProject(p.name);
    setPipeline({ configure: "active" });
    if (!silent) showView("forge");
  } catch (err) {
    toast(err.message, "error");
  }
}

function beginRename(card, p) {
  const nameEl = card.querySelector('[data-role="name"]');
  const input = document.createElement("input");
  input.value = p.name;
  nameEl.replaceChildren(input);
  input.focus();
  input.select();
  const commit = async () => {
    const name = input.value.trim();
    if (name && name !== p.name) {
      await api(`/api/projects/${p.id}`, { method: "PATCH", body: { name } });
      p.name = name;
      if (state.projectId === p.id) setPipelineProject(name);
    }
    nameEl.textContent = p.name;
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") input.blur();
    if (e.key === "Escape") { input.value = p.name; input.blur(); }
  });
  input.addEventListener("blur", commit);
}

function pollCardProgress(card, buildId) {
  const fill = card.querySelector(".card-progress .progress-fill");
  const pct = card.querySelector('[data-role="pct"]');
  const tick = async () => {
    if (!document.body.contains(card)) return;
    try {
      const b = await api(`/api/builds/${buildId}`);
      if (fill) fill.style.width = `${b.progress}%`;
      if (pct) pct.textContent = `${b.progress}%`;
      if (["queued", "running", "testing"].includes(b.status)) {
        setTimeout(tick, 4000);
      } else {
        loadGallery();
      }
    } catch { /* project may have been deleted */ }
  };
  tick();
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

document.getElementById("newSystemBtn").addEventListener("click", () => {
  state.projectId = null; state.config = null; state.theme = null;
  resetChat(); resetSheet(); setPipelineProject("");
  setPipeline({ configure: "active" });
  showView("forge");
  document.getElementById("chatInput").focus();
});

on("view", (name) => { if (name === "gallery") loadGallery(); });
