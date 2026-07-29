// Chat column: streaming conversation with the wizard.
import { streamSSE, api } from "./api.js";
import { state, emit, toast } from "./state.js";

const scroll = document.getElementById("chatScroll");
const messagesEl = document.getElementById("chatMessages");
const intro = document.getElementById("chatIntro");
const form = document.getElementById("chatForm");
const input = document.getElementById("chatInput");
const sendBtn = document.getElementById("chatSend");

let busy = false;

function scrollDown() {
  scroll.scrollTop = scroll.scrollHeight;
}

function addMessage(role, text = "") {
  const el = document.createElement("div");
  el.className = `msg msg-${role}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  scrollDown();
  return el;
}

export function resetChat() {
  messagesEl.innerHTML = "";
  intro.classList.remove("hidden");
}

export function loadHistory(messages) {
  messagesEl.innerHTML = "";
  intro.classList.toggle("hidden", messages.length > 0);
  for (const m of messages) {
    addMessage(m.role === "assistant" ? "assistant" : "user", m.content);
  }
}

export async function sendMessage(text) {
  const message = text.trim();
  if (!message || busy) return;
  busy = true;
  sendBtn.disabled = true;
  input.value = "";
  intro.classList.add("hidden");
  addMessage("user", message);

  const assistantEl = addMessage("assistant", "");
  assistantEl.classList.add("streaming");

  try {
    await streamSSE("/api/chat/message", {
      method: "POST",
      body: { message, project_id: state.projectId },
    }, (event) => {
      switch (event.type) {
        case "project":
          if (!state.projectId) {
            state.projectId = event.project_id;
            emit("project-created", event.project_id);
          }
          break;
        case "text":
          assistantEl.textContent += event.delta;
          scrollDown();
          break;
        case "config":
          state.config = event.config;
          emit("config", { config: event.config, ready: event.ready });
          break;
        case "tool":
          break; // silent — the sheet updating IS the feedback
        case "error":
          addMessage("error", event.message);
          break;
        case "done":
          emit("chat-done", event);
          break;
      }
    });
  } catch (err) {
    addMessage("error", `Couldn't reach the wizard: ${err.message}`);
  } finally {
    assistantEl.classList.remove("streaming");
    if (!assistantEl.textContent) assistantEl.remove();
    busy = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

export async function openProject(projectId) {
  const data = await api(`/api/chat/history/${projectId}`);
  state.projectId = projectId;
  state.config = data.draft_config;
  state.theme = data.theme_config;
  loadHistory(data.messages);
  if (data.draft_config) {
    emit("config", { config: data.draft_config, ready: !!data.draft_config.ready });
  }
  if (data.theme_config) emit("theme", data.theme_config);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(input.value);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => sendMessage(chip.dataset.prompt));
});
