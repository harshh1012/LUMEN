/* ═══════════════════════════════════════════════════════════════════════════
   Soulful — app.js  |  v2.0
   ═══════════════════════════════════════════════════════════════════════════ */

"use strict";

// ─── Constants ────────────────────────────────────────────────────────────────
const MAX_CHARS = 2000;
const TOAST_DURATION = 3500;
const STORAGE_KEY = "soulful_auth";

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// Auth
const authScreen       = $("authScreen");
const chatScreen       = $("chatScreen");
const tabRegister      = $("tab-register");
const tabLogin         = $("tab-login");
const registerView     = $("register-view");
const loginView        = $("login-view");
const registerForm     = $("register-form");
const loginForm        = $("email-login-form");
const forgotForm       = $("forgot-form");
const forgotToggle     = $("forgot-toggle");
const forgotPanel      = $("forgot-panel");
const authStatusEl     = $("auth-status");
const regPasswordEl    = $("reg-password");
const strengthFill     = $("strength-fill");
const strengthText     = $("strength-text");
const scene            = $("scene");
const pupils           = Array.from(document.querySelectorAll(".pupil"));
const allPasswordInputs = Array.from(document.querySelectorAll('input[type="password"]'));

// Chat
const chatTitle        = $("chatTitle");
const chatSubtitle     = $("chatSubtitle");
const messagesEl       = $("messages");
const promptEl         = $("prompt");
const composerEl       = $("composer");
const sendBtn          = $("sendBtn");
const charCount        = $("charCount");
const newChatBtn       = $("newChatBtn");
const rewardBtn        = $("rewardBtn");
const logoutBtn        = $("logoutBtn");
const userAvatar       = $("userAvatar");
const userName         = $("userName");
const userEmail        = $("userEmail");
const sidebarToggle    = $("sidebarToggle");
const navRail          = document.querySelector(".nav-rail");
const modeChips        = Array.from(document.querySelectorAll(".mode-chip"));
const convList         = $("convList");

// Sources
const sourcesPanel     = $("sourcesPanel");
const sourcesToggle    = $("sourcesToggle");
const sourcesToggleText = $("sourcesToggleText");
const sourcesCount     = $("sourcesCount");
const sourcesList      = $("sourcesList");

// KB panel
const kbPanel          = $("kbPanel");
const kbToggle         = $("kbToggle");
const kbClose          = $("kbClose");
const kbFilesEl        = $("kbFiles");
const fileDrop         = $("fileDrop");
const fileList         = $("fileList");
const uploadBtn        = $("uploadBtn");
const ingestBtn        = $("ingestBtn");
const kbStatus         = $("kbStatus");

// Toast
const toastContainer   = $("toastContainer");

// ─── State ────────────────────────────────────────────────────────────────────
let authUser       = null;
let authToken      = null;
let conversationId = null;
let currentMode    = "mental";
let conversations  = [];
let sourcesOpen    = false;

// ─── Auth helpers ─────────────────────────────────────────────────────────────
function saveSession(user, token) {
  authUser  = user;
  authToken = token;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ user, token }));
}

function clearSession() {
  authUser  = null;
  authToken = null;
  conversationId = null;
  conversations  = [];
  sessionStorage.removeItem(STORAGE_KEY);
}

function loadSession() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const { user, token } = JSON.parse(raw);
    if (!user || !token) return false;
    authUser  = user;
    authToken = token;
    return true;
  } catch {
    return false;
  }
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };
}

// ─── Toast notifications ──────────────────────────────────────────────────────
function toast(message, type = "info", duration = TOAST_DURATION) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  toastContainer.appendChild(el);
  setTimeout(() => {
    el.style.animation = "toastOut 0.3s ease forwards";
    el.addEventListener("animationend", () => el.remove());
  }, duration);
}

// ─── Auth status message ──────────────────────────────────────────────────────
function setAuthStatus(text, type = "") {
  authStatusEl.textContent = text;
  authStatusEl.className = "auth-msg" + (type ? ` ${type}` : "");
}

// ─── Tab switching ────────────────────────────────────────────────────────────
function showRegister() {
  tabRegister.classList.add("active");
  tabLogin.classList.remove("active");
  registerView.classList.add("active");
  loginView.classList.remove("active");
  tabRegister.setAttribute("aria-selected", "true");
  tabLogin.setAttribute("aria-selected", "false");
  setAuthStatus("");
}

function showLogin() {
  tabLogin.classList.add("active");
  tabRegister.classList.remove("active");
  loginView.classList.add("active");
  registerView.classList.remove("active");
  tabLogin.setAttribute("aria-selected", "true");
  tabRegister.setAttribute("aria-selected", "false");
  setAuthStatus("");
}

// ─── Password strength ────────────────────────────────────────────────────────
function passwordStrength(pw) {
  let score = 0;
  if (pw.length >= 8)             score++;
  if (/[A-Z]/.test(pw))          score++;
  if (/[a-z]/.test(pw))          score++;
  if (/[0-9]/.test(pw))          score++;
  if (/[^A-Za-z0-9]/.test(pw))   score++;
  return score;
}

function updateStrength(pw) {
  const score = passwordStrength(pw);
  const levels = [
    { label: "Very weak", color: "#ff5c7d", width: "15%" },
    { label: "Weak",      color: "#ff8c42", width: "32%" },
    { label: "Fair",      color: "#f5c518", width: "55%" },
    { label: "Good",      color: "#3ecf8e", width: "78%" },
    { label: "Strong",    color: "#3ecf8e", width: "100%" },
  ];
  const level = pw ? levels[Math.max(0, score - 1)] : null;
  strengthFill.style.width           = level ? level.width : "0%";
  strengthFill.style.backgroundColor = level ? level.color : "transparent";
  strengthText.textContent = `Strength: ${level ? level.label : "—"}`;

  scene.classList.remove("mood-weak", "mood-strong");
  if (pw && score <= 2) scene.classList.add("mood-weak");
  if (pw && score >= 4) scene.classList.add("mood-strong");
}

// ─── Eye / pupil tracking ─────────────────────────────────────────────────────
function setupSceneAnimation() {
  document.addEventListener("mousemove", (e) => {
    pupils.forEach((pupil) => {
      const bbox = pupil.getBoundingClientRect();
      const cx   = bbox.left + bbox.width / 2;
      const cy   = bbox.top  + bbox.height / 2;
      const angle = Math.atan2(e.clientY - cy, e.clientX - cx);
      const r = 5;
      pupil.style.transform = `translate(${Math.cos(angle) * r}px, ${Math.sin(angle) * r}px)`;
    });
  });

  allPasswordInputs.forEach((inp) => {
    inp.addEventListener("focus", () => scene.classList.add("password-mode"));
    inp.addEventListener("blur",  () => scene.classList.remove("password-mode"));
  });
}

// ─── Password visibility toggle ───────────────────────────────────────────────
document.querySelectorAll(".eye-toggle").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = document.getElementById(btn.dataset.target);
    if (!target) return;
    const isHidden = target.type === "password";
    target.type = isHidden ? "text" : "password";
    btn.querySelector(".show-icon").style.display = isHidden ? "none" : "";
    btn.querySelector(".hide-icon").style.display = isHidden ? "" : "none";
  });
});

// ─── Simple Markdown renderer (safe subset) ───────────────────────────────────
function renderMarkdown(text) {
  const div = document.createElement("div");

  // Escape HTML first
  let safe = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold **text**
  safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic *text*
  safe = safe.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Inline code `code`
  safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Links [text](url) — only https
  safe = safe.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  // Bullet lists: lines starting with • or -
  safe = safe.replace(/^[•\-] (.+)$/gm, "<li>$1</li>");
  safe = safe.replace(/(<li>.*<\/li>(\n|$))+/g, (m) => `<ul>${m}</ul>`);
  // Newlines to <br>
  safe = safe.replace(/\n/g, "<br>");

  div.innerHTML = safe;
  return div;
}

// ─── Append message bubble ────────────────────────────────────────────────────
function appendMessage(sender, text, options = {}) {
  // Remove welcome state if present
  const welcome = messagesEl.querySelector(".welcome-state");
  if (welcome) welcome.remove();

  const wrapper = document.createElement("div");
  wrapper.className = "bubble-wrapper";
  wrapper.style.display = "flex";
  wrapper.style.flexDirection = "column";
  wrapper.style.alignItems = sender === "user" ? "flex-end" : "flex-start";

  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender === "user" ? "user" : "bot"}${options.crisis ? " crisis" : ""}`;

  if (sender === "bot") {
    bubble.appendChild(renderMarkdown(text));
  } else {
    bubble.textContent = text;
  }

  wrapper.appendChild(bubble);

  // Sentiment badge (mental mode, bot messages)
  if (sender === "bot" && options.sentiment) {
    const { label, score } = options.sentiment;
    const badge = document.createElement("span");
    badge.className = `sentiment-badge ${label}`;
    const emoji = {
      VERY_POSITIVE: "😊", POSITIVE: "🙂",
      NEUTRAL: "😐", NEGATIVE: "😟", VERY_NEGATIVE: "😢",
    }[label] || "🔵";
    badge.textContent = `${emoji} ${label.replace("_", " ").toLowerCase()} · ${(score * 100).toFixed(0)}%`;
    wrapper.appendChild(badge);
  }

  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
function showTyping() {
  const el = document.createElement("div");
  el.className = "typing-indicator";
  el.id = "typingIndicator";
  [1, 2, 3].forEach(() => {
    const dot = document.createElement("div");
    dot.className = "typing-dot";
    el.appendChild(dot);
  });
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function removeTyping() {
  const el = $("typingIndicator");
  if (el) el.remove();
}

// ─── Sources panel ────────────────────────────────────────────────────────────
function renderSources(sources) {
  sourcesList.innerHTML = "";
  if (!sources || !sources.length) {
    sourcesPanel.classList.add("hidden");
    sourcesOpen = false;
    return;
  }

  sourcesPanel.classList.remove("hidden");
  sourcesCount.textContent = sources.length;

  sources.forEach((s) => {
    const card = document.createElement("div");
    card.className = "source-card";

    const header = document.createElement("div");
    header.className = "source-header";

    const name = document.createElement("span");
    name.className = "source-name";
    name.textContent = s.source || "unknown";

    const score = document.createElement("span");
    score.className = "source-score";
    score.textContent = `${((s.score || 0) * 100).toFixed(1)}% match`;

    header.appendChild(name);
    header.appendChild(score);

    const snippet = document.createElement("p");
    snippet.className = "source-snippet";
    snippet.textContent = (s.text || "").slice(0, 400) + (s.text && s.text.length > 400 ? "…" : "");

    card.appendChild(header);
    card.appendChild(snippet);
    sourcesList.appendChild(card);
  });

  // Auto-open
  sourcesList.classList.remove("hidden");
  sourcesToggleText.textContent = "Hide sources";
  sourcesOpen = true;
}

sourcesToggle.addEventListener("click", () => {
  sourcesOpen = !sourcesOpen;
  sourcesList.classList.toggle("hidden", !sourcesOpen);
  sourcesToggleText.textContent = sourcesOpen ? "Hide sources" : "Show sources";
});

// ─── Mode management ──────────────────────────────────────────────────────────
const MODE_META = {
  mental: {
    title: "Mental Health Support",
    subtitle: "Supportive conversations with safety-aware tone",
  },
  legal: {
    title: "Legal Assistance",
    subtitle: "General legal information with document grounding",
  },
};

function setMode(mode) {
  currentMode = mode;
  const meta = MODE_META[mode];
  chatTitle.textContent    = meta.title;
  chatSubtitle.textContent = meta.subtitle;

  modeChips.forEach((chip) => {
    const active = chip.dataset.mode === mode;
    chip.classList.toggle("active", active);
    chip.setAttribute("aria-pressed", String(active));
  });

  // KB toggle button only visible in legal mode
  kbToggle.classList.toggle("hidden", mode !== "legal");

  // Hide sources panel when switching to mental
  if (mode !== "legal") {
    sourcesPanel.classList.add("hidden");
    kbPanel.classList.add("hidden");
  }
}

modeChips.forEach((chip) => {
  chip.addEventListener("click", () => setMode(chip.dataset.mode));
});

// ─── Conversation list ────────────────────────────────────────────────────────
async function loadConversations() {
  if (!authToken) return;
  try {
    const res = await fetch("/api/conversations", { headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    conversations = data.conversations || [];
    renderConvList();
  } catch {
    // silently fail
  }
}

function renderConvList() {
  convList.innerHTML = "";
  if (!conversations.length) {
    const empty = document.createElement("p");
    empty.className = "conv-empty";
    empty.textContent = "No conversations yet";
    convList.appendChild(empty);
    return;
  }

  conversations.forEach((conv) => {
    const item = document.createElement("div");
    item.className = "conv-item" + (conv.id === conversationId ? " active" : "");
    item.dataset.id = conv.id;

    const icon = document.createElement("span");
    icon.className = "conv-icon";
    icon.textContent = conv.section === "mental" ? "🧠" : "⚖️";

    const title = document.createElement("span");
    title.className = "conv-title";
    title.textContent = conv.title || `Conversation #${conv.id}`;
    title.title = conv.title || `Conversation #${conv.id}`;

    const delBtn = document.createElement("button");
    delBtn.className = "conv-delete";
    delBtn.setAttribute("aria-label", "Delete conversation");
    delBtn.innerHTML = `<svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`;
    delBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await deleteConversation(conv.id);
    });

    item.appendChild(icon);
    item.appendChild(title);
    item.appendChild(delBtn);

    item.addEventListener("click", () => loadConversation(conv.id, conv.section));
    convList.appendChild(item);
  });
}

async function loadConversation(id, section) {
  if (!authToken) return;
  try {
    const res = await fetch(`/api/conversations/${id}/messages`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Failed to load conversation");
    const data = await res.json();

    // Set mode
    setMode(data.mode || section || "mental");
    conversationId = id;

    // Clear and replay messages
    messagesEl.innerHTML = "";
    renderSources([]);

    data.messages.forEach((m) => {
      appendMessage(m.sender, m.text, {
        sentiment: m.sentiment,
        crisis: m.is_crisis,
      });
    });

    renderConvList();
  } catch (err) {
    toast("Could not load conversation", "error");
  }
}

async function deleteConversation(id) {
  if (!authToken) return;
  try {
    const res = await fetch(`/api/conversations/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error("Delete failed");

    if (conversationId === id) {
      startNewChat();
    }
    conversations = conversations.filter((c) => c.id !== id);
    renderConvList();
    toast("Conversation deleted", "success");
  } catch {
    toast("Could not delete conversation", "error");
  }
}

// ─── Chat ─────────────────────────────────────────────────────────────────────
async function sendMessage(message) {
  sendBtn.disabled = true;
  promptEl.disabled = true;
  appendMessage("user", message);
  renderSources([]);

  const typingEl = showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        mode: currentMode,
        message,
        conversation_id: conversationId,
      }),
    });

    const data = await res.json();
    removeTyping();

    if (res.status === 429) {
      toast(data.detail || "Rate limit reached. Please wait.", "warning");
      appendMessage("bot", data.detail || "Too many messages. Please slow down.");
      return;
    }
    if (!res.ok) {
      if (res.status === 401) {
        toast("Session expired. Please sign in again.", "error");
        signOut();
        return;
      }
      throw new Error(data.detail || "Request failed");
    }

    conversationId = data.conversation_id;

    appendMessage("bot", data.reply, {
      sentiment: currentMode === "mental" ? data.sentiment : null,
      crisis: data.is_crisis,
    });

    if (currentMode === "legal") renderSources(data.sources || []);
    if (data.is_crisis) toast("🚨 Crisis resources have been shared above.", "warning", 6000);

    // Refresh conversation list (new conv may have been created)
    await loadConversations();
    renderConvList();

  } catch (err) {
    removeTyping();
    appendMessage("bot", "Sorry, I couldn't process that. Please try again.");
    toast(err.message || "Something went wrong", "error");
  } finally {
    sendBtn.disabled = false;
    promptEl.disabled = false;
    promptEl.focus();
  }
}

// ─── New chat ─────────────────────────────────────────────────────────────────
function startNewChat() {
  conversationId = null;
  messagesEl.innerHTML = `
    <div class="welcome-state">
      <div class="welcome-icon">✦</div>
      <h2 class="welcome-heading">How are you feeling today?</h2>
      <p class="welcome-body">I'm here to listen and support you — no judgment, just presence.</p>
      <div class="welcome-chips">
        <button class="prompt-chip" data-prompt="I've been feeling anxious lately and don't know why.">I've been feeling anxious</button>
        <button class="prompt-chip" data-prompt="I need help understanding my tenant rights.">Tenant rights question</button>
        <button class="prompt-chip" data-prompt="I'm having trouble sleeping because of stress.">Trouble sleeping</button>
        <button class="prompt-chip" data-prompt="What are my rights if I'm fired without notice?">Wrongful termination</button>
      </div>
    </div>`;
  bindPromptChips();
  renderSources([]);
  renderConvList();
  promptEl.focus();
}

function bindPromptChips() {
  document.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      promptEl.value = chip.dataset.prompt;
      promptEl.dispatchEvent(new Event("input"));
      promptEl.focus();
    });
  });
}

// ─── Auth: enter chat ─────────────────────────────────────────────────────────
function enterChat(user, token) {
  saveSession(user, token);
  authScreen.classList.add("hidden");
  chatScreen.classList.remove("hidden");

  // Update user chip in rail
  const initials = user.full_name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
  userAvatar.textContent = initials;
  userName.textContent   = user.full_name;
  userEmail.textContent  = user.email;

  setMode("mental");
  startNewChat();
  loadConversations();

  toast(`Welcome back, ${user.full_name.split(" ")[0]}!`, "success");
}

function signOut() {
  clearSession();
  chatScreen.classList.add("hidden");
  authScreen.classList.remove("hidden");
  showLogin();
  setAuthStatus("You've been signed out.", "success");
}

// ─── Auth forms ───────────────────────────────────────────────────────────────
registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = registerForm.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = "Creating account…";
  setAuthStatus("");

  const payload = {
    full_name: $("full-name").value.trim(),
    phone:     $("reg-phone").value.trim(),
    email:     $("reg-email").value.trim(),
    password:  regPasswordEl.value,
  };

  try {
    const res  = await fetch("/api/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Registration failed");

    // Auto-login after register
    enterChat(data.user, data.token);
    registerForm.reset();
    updateStrength("");
  } catch (err) {
    setAuthStatus(err.message || "Registration failed", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Create account";
  }
});

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = loginForm.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = "Signing in…";
  setAuthStatus("");

  const payload = {
    identifier: $("login-email").value.trim(),
    password:   $("login-password").value,
  };

  try {
    const res  = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    enterChat(data.user, data.token);
    loginForm.reset();
  } catch (err) {
    setAuthStatus(err.message || "Login failed", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
});

forgotForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = forgotForm.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = "Resetting…";

  const payload = {
    email:            $("forgot-email").value.trim(),
    phone:            $("forgot-phone").value.trim(),
    new_password:     $("forgot-password").value,
    confirm_password: $("forgot-confirm-password").value,
  };

  try {
    const res  = await fetch("/api/auth/forgot-password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Reset failed");
    setAuthStatus(data.message || "Password reset. Please sign in.", "success");
    forgotPanel.classList.add("hidden");
    forgotForm.reset();
  } catch (err) {
    setAuthStatus(err.message || "Reset failed", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Reset password";
  }
});

// ─── KB panel ─────────────────────────────────────────────────────────────────
function setKbStatus(text, type = "") {
  kbStatus.textContent = text;
  kbStatus.className   = "kb-status" + (type ? ` ${type}` : "");
}

// Drag-and-drop support
fileDrop.addEventListener("dragover", (e) => {
  e.preventDefault();
  fileDrop.style.borderColor = "var(--accent)";
});
fileDrop.addEventListener("dragleave", () => {
  fileDrop.style.borderColor = "";
});
fileDrop.addEventListener("drop", (e) => {
  e.preventDefault();
  fileDrop.style.borderColor = "";
  const dt = e.dataTransfer;
  if (dt && dt.files.length) {
    kbFilesEl.files = dt.files; // NOTE: this may not work in all browsers; graceful
    renderFileList(dt.files);
  }
});

kbFilesEl.addEventListener("change", () => renderFileList(kbFilesEl.files));

function renderFileList(files) {
  fileList.innerHTML = "";
  Array.from(files).forEach((f) => {
    const tag  = document.createElement("div");
    tag.className = "file-tag";
    const name = document.createElement("span");
    name.className = "file-tag-name";
    name.textContent = f.name;
    const size = document.createElement("span");
    size.className = "file-tag-size";
    size.textContent = f.size < 1024 * 1024
      ? `${(f.size / 1024).toFixed(1)} KB`
      : `${(f.size / (1024 * 1024)).toFixed(1)} MB`;
    tag.appendChild(name);
    tag.appendChild(size);
    fileList.appendChild(tag);
  });
}

uploadBtn.addEventListener("click", async () => {
  const files = kbFilesEl.files;
  if (!files || !files.length) {
    setKbStatus("Select one or more .pdf/.txt files first.", "err");
    return;
  }
  uploadBtn.disabled = true;
  uploadBtn.textContent = "Uploading…";
  setKbStatus("Uploading…");

  const formData = new FormData();
  Array.from(files).forEach((f) => formData.append("files", f));

  try {
    const res  = await fetch("/api/kb/upload", { method: "POST", headers: { Authorization: `Bearer ${authToken}` }, body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    setKbStatus(`✓ Uploaded ${data.count} file(s).`, "ok");
    toast(`Uploaded ${data.count} file(s)`, "success");
    fileList.innerHTML = "";
  } catch (err) {
    setKbStatus(err.message || "Upload failed", "err");
    toast(err.message || "Upload failed", "error");
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = "Upload files";
  }
});

ingestBtn.addEventListener("click", async () => {
  ingestBtn.disabled = true;
  ingestBtn.textContent = "Ingesting…";
  setKbStatus("Building knowledge base index…");

  try {
    const res  = await fetch("/api/kb/ingest", { method: "POST", headers: authHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Ingestion failed");
    setKbStatus(`✓ Indexed ${data.chunks} chunks.`, "ok");
    toast(`Knowledge base ready — ${data.chunks} chunks indexed`, "success");
  } catch (err) {
    setKbStatus(err.message || "Ingestion failed", "err");
    toast(err.message || "Ingestion failed", "error");
  } finally {
    ingestBtn.disabled = false;
    ingestBtn.textContent = "⚡ Ingest knowledge base";
  }
});

// ─── Composer ─────────────────────────────────────────────────────────────────
composerEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = promptEl.value.trim();
  if (!message) return;
  promptEl.value = "";
  promptEl.style.height = "auto";
  charCount.textContent = `0 / ${MAX_CHARS}`;
  charCount.className   = "char-count";
  await sendMessage(message);
});

promptEl.addEventListener("input", () => {
  // Auto-resize
  promptEl.style.height = "auto";
  promptEl.style.height = `${Math.min(promptEl.scrollHeight, 180)}px`;

  // Char count
  const len = promptEl.value.length;
  charCount.textContent = `${len} / ${MAX_CHARS}`;
  charCount.className   = len >= MAX_CHARS ? "char-count at-limit" : len >= MAX_CHARS * 0.85 ? "char-count near-limit" : "char-count";
  sendBtn.disabled = len === 0 || len > MAX_CHARS;
});

// Keyboard shortcuts
promptEl.addEventListener("keydown", (e) => {
  // Enter to send (Shift+Enter = newline)
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composerEl.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
  }
});

// Global keyboard shortcut: / to focus composer
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== promptEl && !authScreen.contains(document.activeElement)) {
    e.preventDefault();
    promptEl.focus();
  }
});

// ─── Reward ───────────────────────────────────────────────────────────────────
rewardBtn.addEventListener("click", async () => {
  if (!conversationId) {
    toast("Start a conversation first.", "warning");
    return;
  }
  try {
    const res  = await fetch("/api/session/reward", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ conversation_id: conversationId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Reward failed");
    toast(`🏅 ${data.badge} — ${data.score} points earned!`, "success", 5000);
  } catch (err) {
    toast(err.message || "Reward unavailable", "warning");
  }
});

// ─── Sidebar toggle (mobile) ──────────────────────────────────────────────────
sidebarToggle.addEventListener("click", () => {
  navRail.classList.toggle("open");
});

// Close sidebar when clicking outside on mobile
document.addEventListener("click", (e) => {
  if (window.innerWidth <= 768 && navRail.classList.contains("open")) {
    if (!navRail.contains(e.target) && e.target !== sidebarToggle) {
      navRail.classList.remove("open");
    }
  }
});

// ─── KB panel toggle ──────────────────────────────────────────────────────────
kbToggle.addEventListener("click", () => {
  kbPanel.classList.toggle("hidden");
});
kbClose.addEventListener("click", () => {
  kbPanel.classList.add("hidden");
});

// ─── New chat / logout ────────────────────────────────────────────────────────
newChatBtn.addEventListener("click", () => {
  startNewChat();
  if (window.innerWidth <= 768) navRail.classList.remove("open");
});

logoutBtn.addEventListener("click", signOut);

// ─── Tab / forgot toggle ──────────────────────────────────────────────────────
tabRegister.addEventListener("click", showRegister);
tabLogin.addEventListener("click", showLogin);
forgotToggle.addEventListener("click", () => forgotPanel.classList.toggle("hidden"));

// ─── Password strength ────────────────────────────────────────────────────────
regPasswordEl.addEventListener("input", (e) => updateStrength(e.target.value));

// ─── Prompt chips on initial load ─────────────────────────────────────────────
bindPromptChips();

// ─── Boot ─────────────────────────────────────────────────────────────────────
function boot() {
  setupSceneAnimation();

  if (loadSession()) {
    enterChat(authUser, authToken);
  } else {
    authScreen.classList.remove("hidden");
    chatScreen.classList.add("hidden");
    showLogin();
  }
}

boot();