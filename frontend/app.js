const API = "";

function token() {
  return localStorage.getItem("doppel-token") || "";
}

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem("doppel-user") || "null");
  } catch {
    return null;
  }
}

function saveSession(data) {
  localStorage.setItem("doppel-token", data.token);
  localStorage.setItem("doppel-user", JSON.stringify(data.user));
}

function clearSession() {
  localStorage.removeItem("doppel-token");
  localStorage.removeItem("doppel-user");
}

async function request(path, body, method = "POST") {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token()) headers.Authorization = `Bearer ${token()}`;
  let response;
  try {
    response = await fetch(`${API}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("The server is not running.");
  }
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && path === "/login") throw new Error("Email or password is wrong.");
  if (response.status === 401) throw new Error("Log in again.");
  if (!response.ok) throw new Error(readable(data.error));
  return data;
}

function readable(error) {
  if (error === "email is taken") return "That email is already registered.";
  if (error === "no price") return "Nothing in that size to watch yet.";
  if (error === "name, email, password") return "Name, email, and password are required.";
  if (error === "image") return "Choose a photo first.";
  if (error === "no account") return "No account with that email.";
  if (error === "email, password") return "Email and a new password are required.";
  if (!error) return "Something went wrong.";
  const text = String(error);
  if (text.startsWith("eBay")) return "eBay did not name that photo. Try it again.";
  return text.length > 160 ? "Something went wrong." : text;
}

function paintAccount() {
  const link = document.querySelector("[data-account]");
  if (!link) return;
  const user = currentUser();
  if (!user) {
    link.textContent = "Login";
    link.href = "login.html";
    return;
  }
  link.textContent = "Log out";
  link.href = "#";
  link.addEventListener("click", (event) => {
    event.preventDefault();
    clearSession();
    location.href = "index.html";
  });
}

function formError(error) {
  const line = document.querySelector("[data-error]");
  if (line) line.textContent = error?.message || "";
}

async function continuePending() {
  const pending = sessionStorage.getItem("doppel-pending");
  if (!pending || !token()) return false;
  await recognize(pending);
  return true;
}

async function recognize(dataUrl) {
  const image = await shrink(dataUrl);
  if (!token()) {
    sessionStorage.setItem("doppel-pending", image);
    location.href = "login.html";
    return;
  }
  setBusy(true);
  try {
    const result = await request("/recognize", { image });
    try {
      sessionStorage.setItem("doppel-result", JSON.stringify({ ...result, image }));
      sessionStorage.removeItem("doppel-pending");
    } catch {
      throw new Error("That photo is too large to keep.");
    }
    location.href = "results.html";
  } finally {
    setBusy(false);
  }
}

function setBusy(on) {
  document.body.classList.toggle("is-busy", on);
  const status = document.querySelector("[data-status]");
  if (status) status.textContent = on ? "Naming the piece. This takes a moment." : "";
  document.querySelectorAll("button, .drop").forEach((node) => {
    node.toggleAttribute("disabled", on);
  });
}

function shrink(dataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const max = 1280;
      const scale = Math.min(1, max / Math.max(image.width, image.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(image.width * scale));
      canvas.height = Math.max(1, Math.round(image.height * scale));
      canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    image.onerror = () => reject(new Error("Use a JPG or PNG."));
    image.src = dataUrl;
  });
}

function readFile(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      reject(new Error("Choose a photo first."));
      return;
    }
    if (file.size > 20_000_000) {
      reject(new Error("That photo is too large."));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Could not read that photo."));
    reader.readAsDataURL(file);
  });
}

function initHome() {
  const user = currentUser();
  const note = document.querySelector("[data-note]");
  if (note && user) {
    const clothes = user.clothes_size || "—";
    const shoes = user.shoe_size || "—";
    note.textContent = `${user.name}  ·  clothes ${clothes}  ·  shoes ${shoes}`;
  }

  const file = document.querySelector("#file");
  document.querySelector("#pick")?.addEventListener("click", () => file.click());
  file?.addEventListener("change", async () => {
    try {
      await recognize(await readFile(file.files[0]));
    } catch (error) {
      const status = document.querySelector("[data-status]");
      if (status) status.textContent = error.message;
    }
    file.value = "";
  });

  const camera = document.querySelector("#camera");
  const video = document.querySelector("#video");
  let stream = null;

  function stopCamera() {
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    if (video) video.srcObject = null;
    camera.hidden = true;
  }

  document.querySelector("#shoot")?.addEventListener("click", async () => {
    const status = document.querySelector("[data-status]");
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
      file.click();
      return;
    }
    camera.hidden = false;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" } },
      });
      video.srcObject = stream;
      await video.play();
    } catch {
      stopCamera();
      if (status) status.textContent = "The camera is blocked. Use Upload image.";
    }
  });

  document.querySelector("#close-camera")?.addEventListener("click", stopCamera);
  document.querySelector("#shutter")?.addEventListener("click", async () => {
    if (!video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    stopCamera();
    try {
      await recognize(canvas.toDataURL("image/jpeg", 0.85));
    } catch (error) {
      const status = document.querySelector("[data-status]");
      if (status) status.textContent = error.message;
    }
  });
}

function initLogin() {
  if (new URLSearchParams(location.search).get("reset") === "1") {
    const notice = document.querySelector("[data-notice]");
    if (notice) notice.textContent = "Password updated. Log in with the new one.";
  }
  document.querySelector("#login-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    formError({ message: "" });
    try {
      const data = await request("/login", {
        email: form.email.value,
        password: form.password.value,
      });
      saveSession(data);
      if (!(await continuePending())) location.href = "index.html";
    } catch (error) {
      formError(error);
    }
  });
}

function initForgot() {
  document.querySelector("#forgot-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    formError({ message: "" });
    if (form.password.value !== form.again.value) {
      formError({ message: "The two passwords do not match." });
      return;
    }
    try {
      await request("/reset", { email: form.email.value, password: form.password.value });
      clearSession();
      location.href = "login.html?reset=1";
    } catch (error) {
      formError(error);
    }
  });
}

function initRegister() {
  document.querySelector("#register-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    formError({ message: "" });
    try {
      const data = await request("/register", {
        name: form.name.value,
        email: form.email.value,
        password: form.password.value,
      });
      saveSession(data);
      const clothes = form.clothes_size.value.trim();
      const shoes = form.shoe_size.value.trim();
      if (clothes || shoes) {
        const updated = await request("/profile", {
          clothes_size: clothes,
          shoe_size: shoes,
        });
        localStorage.setItem("doppel-user", JSON.stringify(updated.user));
      }
      if (!(await continuePending())) location.href = "index.html";
    } catch (error) {
      formError(error);
    }
  });
}

function money(item) {
  const amount = Number(item.price).toFixed(2);
  return item.currency ? `${item.currency} ${amount}` : amount;
}

function initResults() {
  const raw = sessionStorage.getItem("doppel-result");
  const empty = document.querySelector("#empty");
  const hit = document.querySelector("#hit");
  if (!raw) {
    empty.hidden = false;
    return;
  }
  const result = JSON.parse(raw);
  hit.hidden = false;
  const name = result.piece?.name || "Unknown";
  document.title = `Doppel — ${name}`;
  document.querySelector("#piece-name").textContent = name;
  const size = result.size || "—";
  document.querySelector("#piece-meta").innerHTML =
    `${escapeHtml(result.piece?.label || "")} &nbsp;·&nbsp; ${escapeHtml((result.piece?.kind || "").toUpperCase())} &nbsp;·&nbsp; SIZE <b>${escapeHtml(size)}</b>`;
  document.querySelector("#crop").src = result.image;
  const prices = [...(result.new || []), ...(result.used || [])].map((item) => item.price);
  const low = prices.length ? Math.min(...prices) : null;
  const lowText = low === null ? "NOTHING IN THIS SIZE" : money({ price: low, currency: result.new?.[0]?.currency || result.used?.[0]?.currency });
  document.querySelector("#readout").innerHTML =
    `&gt; NAME: ${escapeHtml(name)}<br>&gt; KIND: ${escapeHtml(result.piece?.kind || "")}<br>&gt; SIZE: ${escapeHtml(size)}<br>&gt; <em>CHEAPEST NOW: ${escapeHtml(lowText)}</em>`;
  fillList("#new-list", result.new);
  fillList("#used-list", result.used);
  const band = document.querySelector(".marquee span");
  if (band) {
    const line = `${name.toUpperCase()} / SIZE ${size} / NEW AND USED / CHEAPEST FIRST / `;
    band.textContent = `${line}${line}`;
  }

  document.querySelector("#watch")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const status = document.querySelector("[data-status]");
    button.disabled = true;
    try {
      await request("/alerts", {
        name: result.piece.name,
        kind: result.piece.kind,
        label: result.piece.label,
      });
      button.textContent = "Watching";
      if (status) status.textContent = "The alert is set at today's lowest price.";
    } catch (error) {
      button.disabled = false;
      if (status) status.textContent = error.message;
    }
  });
}

function fillList(selector, items) {
  const list = document.querySelector(selector);
  list.replaceChildren();
  if (!items?.length) {
    const note = document.createElement("p");
    note.className = "size";
    note.textContent = "Nothing in this size.";
    list.append(note);
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "card line";
    card.innerHTML = `<div><div class="who">${escapeHtml(item.size || "Size")}</div><div class="size">${escapeHtml(item.where || "eBay")}</div><div class="price">${escapeHtml(money(item))}</div></div>`;
    list.append(card);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

document.addEventListener("DOMContentLoaded", () => {
  paintAccount();
  const page = document.body.dataset.page;
  if ((page === "login" || page === "register") && token()) {
    continuePending().then((went) => {
      if (!went) location.href = "index.html";
    }).catch(formError);
    return;
  }
  if (page === "home") initHome();
  if (page === "login") initLogin();
  if (page === "forgot") initForgot();
  if (page === "register") initRegister();
  if (page === "results") initResults();
});
