const api = {
  async request(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      credentials: "same-origin",
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      data = {};
    }
    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  },
  get(path) {
    return this.request("GET", path);
  },
  post(path, body) {
    return this.request("POST", path, body || {});
  },
  del(path) {
    return this.request("DELETE", path);
  },
};

function centsToDollars(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

function timeAgo(isoString) {
  const then = new Date(isoString.replace(" ", "T") + "Z");
  const diffMs = Date.now() - then.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : str;
  return div.innerHTML;
}

async function requireAuth() {
  try {
    const { user } = await api.get("/api/me");
    return user;
  } catch (e) {
    window.location.href = "/login.html";
    return null;
  }
}

function renderTabbar(active) {
  const left = [
    { href: "/index.html", icon: "🍽️", label: "Feed" },
    { href: "/friends.html", icon: "🧑‍🤝‍🧑", label: "Friends" },
  ];
  const right = [
    { href: "/rewards.html", icon: "🎁", label: "Rewards" },
    { href: "/profile.html", icon: "👤", label: "Profile" },
  ];
  const renderTab = (t) => `
    <a href="${t.href}" class="${active === t.label ? "active" : ""}">
      <span class="icon">${t.icon}</span>${t.label}
    </a>`;
  return `
    <a href="/capture.html" class="fab">📸</a>
    <nav class="tabbar">
      ${left.map(renderTab).join("")}
      <span style="width:56px;"></span>
      ${right.map(renderTab).join("")}
    </nav>`;
}

function renderPostCard(post) {
  return `
    <div class="card post-card" data-post-id="${post.id}">
      <img class="post-photo" src="${post.photo_url}" loading="lazy" />
      <div class="post-body">
        <div class="post-head">
          <div>
            <div class="post-who">${escapeHtml(post.user_name)}</div>
            <div class="post-where">
              <a href="/restaurant.html?id=${post.restaurant_id}" style="color:inherit; text-decoration:none; border-bottom:1px dotted var(--muted);">
                ${escapeHtml(post.restaurant_name)}
              </a>
            </div>
          </div>
          <div class="rating-pill">${post.rating}/10</div>
        </div>
        ${post.caption ? `<div class="post-caption">${escapeHtml(post.caption)}</div>` : ""}
        <div class="post-foot">
          <button class="cheer-btn ${post.cheered_by_me ? "active" : ""}" data-cheer-post-id="${post.id}">
            <span>🙌</span><span class="cheer-count">${post.cheers_count}</span> Cheers
          </button>
          <span class="when">${timeAgo(post.created_at)}</span>
        </div>
      </div>
    </div>`;
}

function wireCheerButtons(container) {
  container.addEventListener("click", async (e) => {
    const btn = e.target.closest(".cheer-btn");
    if (!btn) return;
    const postId = btn.dataset.cheerPostId;
    btn.disabled = true;
    try {
      const result = await api.post(`/api/posts/${postId}/cheer`);
      btn.classList.toggle("active", result.cheered);
      btn.querySelector(".cheer-count").textContent = result.cheers_count;
    } catch (err) {
      console.error(err);
    } finally {
      btn.disabled = false;
    }
  });
}
