// Central app state + tiny pub/sub, plus shared UI helpers (views, pipeline, toasts).

const listeners = {};

export const state = {
  projectId: null,
  projectName: null,
  config: null,
  theme: null,
  activeBuildId: null,
};

export function on(event, fn) {
  (listeners[event] ||= []).push(fn);
}

export function emit(event, payload) {
  for (const fn of listeners[event] || []) fn(payload);
}

// ------------------------------------------------------------------- views
export function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.getElementById(`view-${name}`)?.classList.add("active");
  document.querySelectorAll(".rail-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.nav === name || (name === "build" && b.dataset.nav === "forge"));
  });
  emit("view", name);
}

// ---------------------------------------------------------------- pipeline
// stageStates: { configure: "active"|"done"|"", build: ..., verify: ..., flash: ... }
export function setPipeline(stageStates) {
  document.querySelectorAll(".stage").forEach((el) => {
    const s = stageStates[el.dataset.stage] || "";
    el.classList.toggle("active", s === "active");
    el.classList.toggle("done", s === "done");
  });
}

export function setPipelineProject(name) {
  state.projectName = name;
  document.getElementById("pipelineProject").textContent = name || "";
}

// ------------------------------------------------------------------ toasts
export function toast(message, kind = "info", ms = 4000) {
  const el = document.createElement("div");
  el.className = `toast${kind === "error" ? " error" : ""}`;
  el.textContent = message;
  document.getElementById("toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
}
