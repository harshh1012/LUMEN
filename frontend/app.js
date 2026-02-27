const authScreen = document.getElementById("authScreen");
const chatScreen = document.getElementById("chatScreen");
const authStatusEl = document.getElementById("auth-status");
const whoamiEl = document.getElementById("whoami");
const tabRegister = document.getElementById("tab-register");
const tabLogin = document.getElementById("tab-login");
const registerView = document.getElementById("register-view");
const loginView = document.getElementById("login-view");
const registerForm = document.getElementById("register-form");
const loginForm = document.getElementById("email-login-form");
const forgotForm = document.getElementById("forgot-form");
const forgotToggle = document.getElementById("forgot-toggle");
const regPasswordEl = document.getElementById("reg-password");
const strengthBar = document.getElementById("strength-bar");
const strengthText = document.getElementById("strength-text");
const scene = document.getElementById("scene");
const pupils = Array.from(document.querySelectorAll(".pupil"));
const passwordInputs = Array.from(document.querySelectorAll('input[type="password"]'));
const modeEl = document.getElementById("mode");
const modeTextEl = document.getElementById("modeText");
const messagesEl = document.getElementById("messages");
const promptEl = document.getElementById("prompt");
const composerEl = document.getElementById("composer");
const sendBtn = document.getElementById("sendBtn");
const newChatBtn = document.getElementById("newChatBtn");
const rewardBtn = document.getElementById("rewardBtn");
const logoutBtn = document.getElementById("logoutBtn");
const uploadBtn = document.getElementById("uploadBtn");
const ingestBtn = document.getElementById("ingestBtn");
const kbFilesEl = document.getElementById("kbFiles");
const statusEl = document.getElementById("sidebarStatus");
const sourcesPanel = document.getElementById("sourcesPanel");
const sourcesList = document.getElementById("sourcesList");

let authUser = null;
let conversationId = null;

function setAuthStatus(text, type = "") {
  authStatusEl.textContent = text;
  authStatusEl.classList.remove("success", "error");
  if (type) authStatusEl.classList.add(type);
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? "#fca5a5" : "#d1d5db";
}

function showRegister() {
  tabRegister.classList.add("active");
  tabLogin.classList.remove("active");
  registerView.classList.add("active");
  loginView.classList.remove("active");
  setAuthStatus("");
}

function showLogin() {
  tabLogin.classList.add("active");
  tabRegister.classList.remove("active");
  loginView.classList.add("active");
  registerView.classList.remove("active");
  setAuthStatus("");
}

function passwordStrength(password) {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  return score;
}

function updateStrength(password) {
  const score = passwordStrength(password);
  const levels = [
    { label: "Very weak", color: "#c2410c", width: "20%" },
    { label: "Weak", color: "#b45309", width: "35%" },
    { label: "Fair", color: "#ca8a04", width: "55%" },
    { label: "Good", color: "#15803d", width: "75%" },
    { label: "Strong", color: "#166534", width: "100%" },
  ];
  const level = password ? levels[Math.max(0, score - 1)] : null;
  strengthBar.style.setProperty("--strength-width", level ? level.width : "0%");
  strengthBar.style.setProperty("--strength-color", level ? level.color : "#d2c4b7");
  strengthText.textContent = `Strength: ${level ? level.label : "-"}`;
  scene.classList.remove("mood-weak", "mood-strong");
  if (!password) return;
  if (score <= 2) scene.classList.add("mood-weak");
  if (score >= 4) scene.classList.add("mood-strong");
}

function setupSceneAnimation() {
  document.addEventListener("mousemove", (e) => {
    const maxShift = 5;
    pupils.forEach((pupil) => {
      const bbox = pupil.getBoundingClientRect();
      const cx = bbox.left + bbox.width / 2;
      const cy = bbox.top + bbox.height / 2;
      const angle = Math.atan2(e.clientY - cy, e.clientX - cx);
      pupil.style.transform = `translate(${Math.cos(angle) * maxShift}px, ${Math.sin(angle) * maxShift}px)`;
    });
  });
  passwordInputs.forEach((input) => {
    input.addEventListener("focus", () => scene.classList.add("password-mode"));
    input.addEventListener("blur", () => scene.classList.remove("password-mode"));
  });
}

function setModeText() {
  modeTextEl.textContent =
    modeEl.value === "mental"
      ? "Supportive conversations with safety-aware tone."
      : "General legal information with optional document grounding.";
}

function appendMessage(sender, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender === "user" ? "user" : "bot"}`;
  bubble.textContent = text;
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderSources(sources) {
  sourcesList.innerHTML = "";
  if (!sources || !sources.length) {
    sourcesPanel.classList.add("hidden");
    return;
  }
  sourcesPanel.classList.remove("hidden");
  sources.forEach((s) => {
    const item = document.createElement("div");
    item.className = "source-item";
    const src = s.source || "unknown";
    const score = typeof s.score === "number" ? s.score.toFixed(3) : "0.000";
    const snippet = (s.text || "").slice(0, 500);
    item.innerHTML = `<strong>${src}</strong> | score: ${score}<br>${snippet}`;
    sourcesList.appendChild(item);
  });
}

function setAuthUser(user) {
  authUser = user;
  if (user) {
    localStorage.setItem("authUser", JSON.stringify(user));
    whoamiEl.textContent = `Signed in as ${user.full_name}`;
    authScreen.classList.add("hidden");
    chatScreen.classList.remove("hidden");
    setStatus(`Welcome ${user.full_name}`);
    if (!messagesEl.children.length) appendMessage("bot", "How can I help you today?");
  } else {
    localStorage.removeItem("authUser");
    whoamiEl.textContent = "";
    chatScreen.classList.add("hidden");
    authScreen.classList.remove("hidden");
    messagesEl.innerHTML = "";
    conversationId = null;
  }
}

async function sendMessage(message) {
  sendBtn.disabled = true;
  appendMessage("user", message);
  renderSources([]);
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: modeEl.value,
        message,
        username: authUser ? authUser.full_name : null,
        auth_user_id: authUser ? authUser.id : null,
        conversation_id: conversationId,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");
    conversationId = data.conversation_id;
    appendMessage("bot", data.reply);
    if (modeEl.value === "legal") renderSources(data.sources || []);
    setStatus(`Conversation #${conversationId}`);
  } catch (err) {
    appendMessage("bot", "Sorry, I could not process that right now.");
    setStatus(err.message || "Unknown error", true);
  } finally {
    sendBtn.disabled = false;
  }
}

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    full_name: document.getElementById("full-name").value.trim(),
    phone: document.getElementById("reg-phone").value.trim(),
    email: document.getElementById("reg-email").value.trim(),
    password: regPasswordEl.value,
  };
  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Registration failed");
    setAuthStatus("Account created successfully. You can now log in.", "success");
    registerForm.reset();
    updateStrength("");
    showLogin();
  } catch (err) {
    setAuthStatus(err.message || "Registration failed", "error");
  }
});

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    identifier: document.getElementById("login-email").value.trim(),
    password: document.getElementById("login-password").value,
  };
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    setAuthUser(data.user);
    setAuthStatus("");
  } catch (err) {
    setAuthStatus(err.message || "Login failed", "error");
  }
});

forgotForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    email: document.getElementById("forgot-email").value.trim(),
    phone: document.getElementById("forgot-phone").value.trim(),
    new_password: document.getElementById("forgot-password").value,
    confirm_password: document.getElementById("forgot-confirm-password").value,
  };
  try {
    const res = await fetch("/api/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Password reset failed");
    setAuthStatus(data.message || "Password reset successful. Please log in.", "success");
    forgotForm.reset();
    forgotForm.classList.add("hidden");
  } catch (err) {
    setAuthStatus(err.message || "Password reset failed", "error");
  }
});

tabRegister.addEventListener("click", showRegister);
tabLogin.addEventListener("click", showLogin);
forgotToggle.addEventListener("click", () => forgotForm.classList.toggle("hidden"));
regPasswordEl.addEventListener("input", (e) => updateStrength(e.target.value));

composerEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = promptEl.value.trim();
  if (!message) return;
  promptEl.value = "";
  await sendMessage(message);
});

promptEl.addEventListener("input", () => {
  promptEl.style.height = "auto";
  promptEl.style.height = `${Math.min(promptEl.scrollHeight, 180)}px`;
});

modeEl.addEventListener("change", setModeText);
newChatBtn.addEventListener("click", () => {
  conversationId = null;
  messagesEl.innerHTML = "";
  renderSources([]);
  appendMessage("bot", "New chat started. How can I help?");
  setStatus("New conversation");
});

rewardBtn.addEventListener("click", async () => {
  if (!conversationId) return setStatus("No active conversation yet.", true);
  try {
    const res = await fetch("/api/session/reward", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Reward request failed");
    setStatus(`Reward: ${data.badge} | ${data.score} points`);
  } catch (err) {
    setStatus(err.message || "Reward failed", true);
  }
});

logoutBtn.addEventListener("click", () => {
  setAuthUser(null);
  setStatus("");
  setAuthStatus("Logged out successfully.", "success");
  showLogin();
});

uploadBtn.addEventListener("click", async () => {
  const files = kbFilesEl.files;
  if (!files || !files.length) return setStatus("Select one or more .pdf/.txt files first.", true);
  const formData = new FormData();
  Array.from(files).forEach((f) => formData.append("files", f));
  try {
    const res = await fetch("/api/kb/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    setStatus(`Uploaded ${data.count} file(s).`);
  } catch (err) {
    setStatus(err.message || "Upload failed", true);
  }
});

ingestBtn.addEventListener("click", async () => {
  try {
    setStatus("Ingesting knowledge base...");
    const res = await fetch("/api/kb/ingest", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Ingestion failed");
    setStatus(`Ingested ${data.chunks} chunks.`);
  } catch (err) {
    setStatus(err.message || "Ingestion failed", true);
  }
});

setModeText();
setupSceneAnimation();

try {
  const stored = localStorage.getItem("authUser");
  if (stored) setAuthUser(JSON.parse(stored));
  else {
    setAuthUser(null);
    showLogin();
  }
} catch {
  setAuthUser(null);
  showLogin();
}
