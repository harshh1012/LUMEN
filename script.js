const scene = document.getElementById("scene");
const statusBox = document.getElementById("status");

const registerTab = document.getElementById("tab-register");
const loginTab = document.getElementById("tab-login");
const registerView = document.getElementById("register-view");
const loginView = document.getElementById("login-view");

const registerForm = document.getElementById("register-form");
const emailLoginForm = document.getElementById("email-login-form");

const fullNameInput = document.getElementById("full-name");
const regPhoneInput = document.getElementById("reg-phone");
const regEmailInput = document.getElementById("reg-email");
const regPasswordInput = document.getElementById("reg-password");

const loginEmailInput = document.getElementById("login-email");
const loginPasswordInput = document.getElementById("login-password");
const rememberMeInput = document.getElementById("remember-me");
const forgotToggleBtn = document.getElementById("forgot-toggle");
const forgotForm = document.getElementById("forgot-form");
const forgotEmailInput = document.getElementById("forgot-email");
const forgotPhoneInput = document.getElementById("forgot-phone");
const forgotPasswordInput = document.getElementById("forgot-password");
const forgotConfirmPasswordInput = document.getElementById("forgot-confirm-password");

const strengthBar = document.getElementById("strength-bar");
const strengthText = document.getElementById("strength-text");

const authActions = document.getElementById("auth-actions");
const logoutBtn = document.getElementById("logout-btn");

const STORAGE_KEY = "registered_users_v2";
const SESSION_KEY = "active_user_session_v1";
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const eyeData = [...document.querySelectorAll(".eye")].map((eye) => {
  const sclera = eye.querySelector(".sclera");
  const pupil = eye.querySelector(".pupil");
  const radius = Number(eye.dataset.radius || 8);
  return { sclera, pupil, radius };
});

const tracker = {
  x: window.innerWidth / 2,
  y: window.innerHeight / 2
};

function setStatus(message, type) {
  statusBox.textContent = message;
  statusBox.className = `status ${type || ""}`.trim();
}

function normalizePhone(value) {
  return value.replace(/\D/g, "");
}

function isValidEmail(email) {
  return EMAIL_REGEX.test(email);
}

function isValidPhone(phone) {
  return /^\d{10}$/.test(phone);
}

function getUsers() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

function saveUsers(users) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(users));
}

function getSession() {
  try {
    const localSession = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    if (localSession) return localSession;
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

function saveSession(sessionData, remember) {
  if (remember) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
    sessionStorage.removeItem(SESSION_KEY);
  } else {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
    localStorage.removeItem(SESSION_KEY);
  }
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(SESSION_KEY);
}

function switchView(view) {
  const isRegister = view === "register";
  registerTab.classList.toggle("active", isRegister);
  loginTab.classList.toggle("active", !isRegister);
  registerView.classList.toggle("active", isRegister);
  loginView.classList.toggle("active", !isRegister);
  setStatus("", "");
}

function getPasswordStrength(password) {
  let score = 0;

  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  if (score <= 1) return { label: "Weak", color: "#c33f3f", width: "25%", score };
  if (score === 2) return { label: "Medium", color: "#d48a1f", width: "50%", score };
  if (score === 3) return { label: "Good", color: "#3f8f4a", width: "75%", score };

  return { label: "Strong", color: "#1f7a4a", width: "100%", score };
}

function renderStrength(password) {
  if (!password) {
    strengthBar.style.setProperty("--strength-width", "0%");
    strengthBar.style.setProperty("--strength-color", "#d2c4b7");
    strengthText.textContent = "Strength: -";
    scene.classList.remove("mood-weak", "mood-strong", "mood-excited");
    return { score: 0 };
  }

  const strength = getPasswordStrength(password);
  strengthBar.style.setProperty("--strength-width", strength.width);
  strengthBar.style.setProperty("--strength-color", strength.color);
  strengthText.textContent = `Strength: ${strength.label}`;

  scene.classList.remove("mood-weak", "mood-strong", "mood-excited");
  if (strength.label === "Weak") {
    scene.classList.add("mood-weak");
  } else if (strength.label === "Strong") {
    scene.classList.add("mood-excited");
  }

  return strength;
}

function setAuthUI(user) {
  const loggedIn = Boolean(user);
  authActions.classList.toggle("hidden", !loggedIn);
  registerTab.disabled = loggedIn;
  loginTab.disabled = loggedIn;
  registerForm.querySelectorAll("input, button").forEach((el) => {
    el.disabled = loggedIn;
  });
  emailLoginForm.querySelectorAll("input, button").forEach((el) => {
    el.disabled = loggedIn;
  });
  forgotToggleBtn.disabled = loggedIn;
  forgotForm.querySelectorAll("input, button").forEach((el) => {
    el.disabled = loggedIn;
  });

  if (loggedIn) {
    switchView("login");
    setStatus(`Logged in as ${user.fullName}.`, "success");
  }
}

async function sha256Hex(text) {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = [...new Uint8Array(hashBuffer)];
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

function randomSalt() {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function hashPassword(password, salt) {
  return sha256Hex(`${salt}:${password}`);
}

registerTab.addEventListener("click", () => switchView("register"));
loginTab.addEventListener("click", () => switchView("login"));

regPhoneInput.addEventListener("input", () => {
  regPhoneInput.value = normalizePhone(regPhoneInput.value).slice(0, 10);
});
forgotPhoneInput.addEventListener("input", () => {
  forgotPhoneInput.value = normalizePhone(forgotPhoneInput.value).slice(0, 10);
});

regPasswordInput.addEventListener("input", () => {
  renderStrength(regPasswordInput.value);
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const fullName = fullNameInput.value.trim();
  const email = regEmailInput.value.trim().toLowerCase();
  const phone = normalizePhone(regPhoneInput.value);
  const password = regPasswordInput.value;

  if (!fullName || !email || !phone || !password) {
    setStatus("Please fill full name, phone number, email, and password.", "error");
    return;
  }

  if (!isValidEmail(email)) {
    setStatus("Please enter a valid email address.", "error");
    return;
  }

  if (!isValidPhone(phone)) {
    setStatus("Phone number must be exactly 10 digits.", "error");
    return;
  }

  const strength = getPasswordStrength(password);
  if (strength.score < 2) {
    setStatus("Password is too weak. Use at least 8 chars with letters and numbers.", "error");
    return;
  }

  const users = getUsers();
  const exists = users.some((user) => user.email === email || user.phone === phone);
  if (exists) {
    setStatus("User already registered with this email or phone.", "error");
    return;
  }

  const salt = randomSalt();
  const passwordHash = await hashPassword(password, salt);

  users.push({
    id: crypto.randomUUID(),
    fullName,
    email,
    phone,
    passwordHash,
    passwordSalt: salt,
    createdAt: new Date().toISOString()
  });

  saveUsers(users);
  setStatus("Registration successful. You can log in now.", "success");

  loginEmailInput.value = email;
  loginPasswordInput.value = "";
  registerForm.reset();
  renderStrength("");
  switchView("login");
});

emailLoginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const email = loginEmailInput.value.trim().toLowerCase();
  const password = loginPasswordInput.value;
  const remember = rememberMeInput.checked;

  if (!email || !password) {
    setStatus("Enter both email and password to log in.", "error");
    return;
  }

  if (!isValidEmail(email)) {
    setStatus("Please enter a valid email address.", "error");
    return;
  }

  const user = getUsers().find((item) => item.email === email);
  if (!user) {
    setStatus("No account found. Please register first.", "error");
    return;
  }

  const attemptedHash = await hashPassword(password, user.passwordSalt);
  if (user.passwordHash !== attemptedHash) {
    setStatus("Invalid password. Please try again.", "error");
    return;
  }

  saveSession(
    {
      id: user.id,
      fullName: user.fullName,
      email: user.email,
      loginAt: new Date().toISOString()
    },
    remember
  );

  setAuthUI(user);
  setStatus(`Logged in successfully. Welcome, ${user.fullName}.`, "success");
});

forgotToggleBtn.addEventListener("click", () => {
  forgotForm.classList.toggle("hidden");
});

forgotForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const email = forgotEmailInput.value.trim().toLowerCase();
  const phone = normalizePhone(forgotPhoneInput.value);
  const newPassword = forgotPasswordInput.value;
  const confirmPassword = forgotConfirmPasswordInput.value;

  if (!email || !phone || !newPassword || !confirmPassword) {
    setStatus("Fill all forgot password fields.", "error");
    return;
  }
  if (!isValidEmail(email)) {
    setStatus("Please enter a valid email address.", "error");
    return;
  }
  if (!isValidPhone(phone)) {
    setStatus("Phone number must be exactly 10 digits.", "error");
    return;
  }
  if (newPassword !== confirmPassword) {
    setStatus("New password and confirm password do not match.", "error");
    return;
  }

  const strength = getPasswordStrength(newPassword);
  if (strength.score < 2) {
    setStatus("New password is too weak.", "error");
    return;
  }

  const users = getUsers();
  const userIndex = users.findIndex((item) => item.email === email && item.phone === phone);
  if (userIndex < 0) {
    setStatus("No matching account found for email and phone.", "error");
    return;
  }

  const salt = randomSalt();
  const passwordHash = await hashPassword(newPassword, salt);

  users[userIndex].passwordHash = passwordHash;
  users[userIndex].passwordSalt = salt;
  users[userIndex].updatedAt = new Date().toISOString();
  saveUsers(users);

  forgotForm.reset();
  forgotForm.classList.add("hidden");
  loginEmailInput.value = email;
  setStatus("Password reset successful. Please log in with your new password.", "success");
});

logoutBtn.addEventListener("click", () => {
  clearSession();
  setAuthUI(null);
  registerForm.querySelectorAll("input, button").forEach((el) => {
    el.disabled = false;
  });
  emailLoginForm.querySelectorAll("input, button").forEach((el) => {
    el.disabled = false;
  });
  registerTab.disabled = false;
  loginTab.disabled = false;
  setStatus("Logged out successfully.", "success");
});

loginPasswordInput.addEventListener("focus", () => {
  scene.classList.add("password-mode");
});

loginPasswordInput.addEventListener("blur", () => {
  scene.classList.remove("password-mode");
});

forgotPasswordInput.addEventListener("focus", () => {
  scene.classList.add("password-mode");
});

forgotPasswordInput.addEventListener("blur", () => {
  scene.classList.remove("password-mode");
});

function movePupilTowards(pointX, pointY) {
  eyeData.forEach((item) => {
    const rect = item.sclera.getBoundingClientRect();
    const eyeCenterX = rect.left + rect.width / 2;
    const eyeCenterY = rect.top + rect.height / 2;

    const dx = pointX - eyeCenterX;
    const dy = pointY - eyeCenterY;
    const angle = Math.atan2(dy, dx);
    const travel = Math.min(item.radius, Math.hypot(dx, dy));

    item.pupil.style.transform = `translate(${Math.cos(angle) * travel}px, ${Math.sin(angle) * travel}px)`;
  });
}

document.addEventListener("mousemove", (event) => {
  tracker.x = event.clientX;
  tracker.y = event.clientY;
});

function animate() {
  if (!scene.classList.contains("password-mode")) {
    movePupilTowards(tracker.x, tracker.y);
  }
  requestAnimationFrame(animate);
}

(function init() {
  renderStrength("");
  animate();

  const session = getSession();
  if (!session) return;

  const matchedUser = getUsers().find((user) => user.id === session.id);
  if (!matchedUser) {
    clearSession();
    return;
  }

  setAuthUI(matchedUser);
})();
