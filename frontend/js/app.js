// App bootstrap: navigation, pipeline state, backend health.
import "./chat.js";
import "./sheet.js";
import "./build.js";
import "./gallery.js";
import "./flash.js";
import "./settings.js";
import { emit, on, showView, setPipeline, setPipelineProject, state } from "./state.js";
import { api } from "./api.js";

// rail navigation (the settings button has no data-nav — it opens the modal)
document.querySelectorAll(".rail-btn[data-nav]").forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.nav));
});

document.getElementById("newDistroBtn").addEventListener("click", () => emit("new-distro"));

// a freshly created project gets a name derived from its config later;
// until then show a placeholder in the pipeline header
on("project-created", () => setPipelineProject("new system"));

on("config", ({ config }) => {
  if (config?.hostname) {
    setPipelineProject(config.hostname);
    if (state.projectId) {
      // keep the project name in sync with the configured hostname
      api(`/api/projects/${state.projectId}`, {
        method: "PATCH", body: { name: config.hostname },
      }).catch(() => {});
    }
  }
});

// backend health dot
async function checkHealth() {
  const dot = document.getElementById("healthDot");
  try {
    const h = await api("/health");
    dot.classList.remove("down");
    dot.title = `Backend healthy · live-build ${h.live_build ? "ready" : "missing"} · QEMU ${h.qemu ? "ready" : "missing"}`;
  } catch {
    dot.classList.add("down");
    dot.title = "Backend unreachable";
  }
}
checkHealth();
setInterval(checkHealth, 30000);

setPipeline({ configure: "active" });
showView("forge");
document.getElementById("chatInput").focus();
