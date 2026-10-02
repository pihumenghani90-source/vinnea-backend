const API ="https://vinnea-backend-hu6y.onrender.com";

const $ = (id) => document.getElementById(id);
const token = () => localStorage.getItem("token");
let me = null;

function say(el, text, ok) {
  el.textContent = text;
  el.hidden = !text;
  el.classList.toggle("ok", !!ok);
}

async function api(path, opts = {}) {
  opts.headers = { "ngrok-skip-browser-warning": "1", ...(opts.headers || {}) };
  if (token()) opts.headers.Authorization = "Bearer " + token();
  let res;
  try { res = await fetch(API + path, opts); }
  catch { throw new Error("Can't reach the server. Check that uvicorn and ngrok are running."); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : JSON.stringify(d || data));
  }
  return data;
}

// ---------- auth ----------
async function login(username, password) {
  const data = await api("/login", { method: "POST", body: new URLSearchParams({ username, password }) });
  localStorage.setItem("token", data.access_token);
  me = await api("/me");
  location.hash = "#/";
  refresh();
}

$("loginForm").onsubmit = async (e) => {
  e.preventDefault();
  try { await login($("lUser").value, $("lPass").value); }
  catch (err) { say($("msg"), err.message); }
};

$("signupForm").onsubmit = async (e) => {
  e.preventDefault();
  if ($("sPass").value !== $("sPass2").value) return say($("msg"), "Passwords don't match.");
  try {
    await api("/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("sUser").value, email: $("sEmail").value, password: $("sPass").value }),
    });
    await login($("sUser").value, $("sPass").value);
  } catch (err) { say($("msg"), err.message); }
};

$("logoutBtn").onclick = () => {
  localStorage.removeItem("token");
  me = null;
  location.hash = "#/";
  refresh();
};

// ---------- feed ----------
const mediaUrl = (p) => {
  const u = p.url || p.file_url || p.media_url || p.image_url || p.file_path || p.filename || p.path || "";
  return u.startsWith("http") ? u : API + (u.startsWith("/") ? u : "/" + u);
};
const isVideo = (p, u) => /video/i.test(p.file_type || p.media_type || p.type || "") || /\.(mp4|mov|webm)$/i.test(u);
const ownerOf = (p) => p.username || p.owner || (p.user && p.user.username) || "";

async function loadFeed(path) {
  const grid = $("grid");
  grid.innerHTML = "";
  try {
    const data = await api(path);
    const posts = Array.isArray(data) ? data : (data.posts || data.items || []);
    $("empty").hidden = posts.length > 0;
    posts.forEach((p) => grid.appendChild(pinEl(p, path)));
  } catch (err) { say($("msg"), err.message); }
}

function pinEl(p, path) {
  const u = mediaUrl(p);
  const fig = document.createElement("figure");
  fig.className = "pin";
  const m = document.createElement(isVideo(p, u) ? "video" : "img");
  m.src = u;
  if (m.tagName === "VIDEO") { m.controls = true; m.muted = true; } else { m.loading = "lazy"; m.alt = p.caption || "pin"; }
  fig.appendChild(m);

  const over = document.createElement("figcaption");
  over.className = "over";
  const who = document.createElement("b"); who.textContent = "@" + ownerOf(p);
  const cap = document.createElement("span"); cap.textContent = p.caption || "";
  over.append(who, cap);
  fig.appendChild(over);

  if (me && ownerOf(p) === me.username) {
    const d = document.createElement("button");
    d.className = "del"; d.textContent = "Delete";
    d.onclick = async () => {
      if (!confirm("Delete this pin?")) return;
      try { await api("/posts/" + p.id, { method: "DELETE" }); loadFeed(path); }
      catch (err) { say($("msg"), err.message); }
    };
    fig.appendChild(d);
  }
  return fig;
}

// ---------- upload ----------
$("fab").onclick = () => $("uploadDlg").showModal();
$("cancelUp").onclick = () => $("uploadDlg").close();
$("uploadForm").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData();
  fd.append("file", $("file").files[0]);
  fd.append("caption", $("caption").value);
  try {
    await api("/upload", { method: "POST", body: fd });
    $("uploadForm").reset();
    say($("upMsg"), "");
    $("uploadDlg").close();
    route();
  } catch (err) { say($("upMsg"), err.message); }
};

// ---------- routing ----------
function refresh() {
  const on = !!me;
  $("navIn").hidden = !on;
  $("navOut").hidden = on;
  $("fab").hidden = !on;
  route();
}

function route() {
  const r = location.hash.replace("#/", "");
  const auth = r === "login" || r === "signup";
  say($("msg"), "");
  $("authView").hidden = !auth;
  $("feedView").hidden = auth;
  $("hero").hidden = r !== "";
  if (auth) {
    $("loginForm").hidden = r !== "login";
    $("signupForm").hidden = r !== "signup";
    $("tabLogin").classList.toggle("on", r === "login");
    $("tabSignup").classList.toggle("on", r === "signup");
    return;
  }
  if (r === "mine") {
    if (!me) { location.hash = "#/login"; return; }
    $("feedTitle").hidden = false;
    loadFeed("/posts/me");
  } else {
    $("feedTitle").hidden = true;
    loadFeed("/posts");
  }
}

window.addEventListener("hashchange", route);

(async () => {
  if (token()) {
    try { me = await api("/me"); } catch { localStorage.removeItem("token"); }
  }
  refresh();
})();
