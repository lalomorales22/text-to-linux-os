// Settings modal: Anthropic API key management.
import { api } from "./api.js";
import { toast } from "./state.js";

const modal = document.getElementById("settingsModal");
const statusEl = document.getElementById("apiKeyStatus");
const input = document.getElementById("apiKeyInput");
const saveBtn = document.getElementById("saveApiKeyBtn");

async function refreshStatus() {
  statusEl.className = "modal-status";
  statusEl.textContent = "Checking…";
  try {
    const s = await api("/api/settings");
    if (!s.api_key_set) {
      statusEl.classList.add("missing");
      statusEl.textContent = "No key configured — the wizard can't respond until you add one.";
    } else {
      statusEl.classList.add("ok");
      const source = s.api_key_source === "app" ? "saved in the app" : "from .env";
      statusEl.textContent = `Key ${s.api_key_hint} active (${source}) · model ${s.chat_model}`;
    }
  } catch {
    statusEl.textContent = "Couldn't reach the backend.";
  }
}

export function openSettings() {
  modal.classList.remove("hidden");
  refreshStatus();
  input.focus();
}

function closeSettings() {
  modal.classList.add("hidden");
  input.value = "";
}

async function saveKey() {
  const key = input.value.trim();
  if (!key) { input.focus(); return; }
  saveBtn.disabled = true;
  saveBtn.textContent = "Verifying…";
  try {
    const res = await api("/api/settings/api-key", { method: "POST", body: { api_key: key } });
    toast(`API key ${res.api_key_hint} verified and saved`, "info");
    input.value = "";
    refreshStatus();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save";
  }
}

document.getElementById("settingsBtn").addEventListener("click", openSettings);
document.getElementById("closeSettingsBtn").addEventListener("click", closeSettings);
saveBtn.addEventListener("click", saveKey);
input.addEventListener("keydown", (e) => { if (e.key === "Enter") saveKey(); });
modal.addEventListener("click", (e) => { if (e.target === modal) closeSettings(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !modal.classList.contains("hidden")) closeSettings();
});
