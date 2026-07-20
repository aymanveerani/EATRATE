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
    { href: "/map.html", icon: "🗺️", label: "Map" },
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
          <div style="display:flex; gap:8px;">
            <button class="cheer-btn ${post.cheered_by_me ? "active" : ""}" data-cheer-post-id="${post.id}">
              <span>🙌</span><span class="cheer-count">${post.cheers_count}</span> Cheers
            </button>
            <button class="report-btn" data-report-post-id="${post.id}" title="Report this post">🚩</button>
          </div>
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

function ftcBanner() {
  return `
    <div class="ftc-banner">
      ⚠️ Reviews on EatRate may be incentivized: every 5th review a user posts earns them a
      $10 gift card, regardless of the rating given.
    </div>`;
}

function initReportModal(container) {
  if (document.getElementById("report-modal")) {
    // Already injected on this page (e.g. wireCheerButtons + initReportModal
    // both called on the same container) — just rewire the click delegation.
  } else {
    document.body.insertAdjacentHTML(
      "beforeend",
      `
      <div id="report-modal-backdrop" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:3000;"></div>
      <div id="report-modal" style="display:none; position:fixed; bottom:0; left:50%; transform:translateX(-50%); width:100%; max-width:430px; background:var(--card); border:1px solid var(--border); border-bottom:none; border-radius:18px 18px 0 0; padding:20px; z-index:3001;">
        <h3 style="margin-top:0;">Report this post</h3>
        <p style="color:var(--muted); font-size:14px; margin-top:-8px;">Let us know what's wrong — we review every report.</p>
        <div id="report-error" style="display:none;" class="error-msg"></div>
        <div id="report-success" style="display:none;" class="success-msg"></div>
        <textarea id="report-reason" placeholder="What's the issue? (optional)"></textarea>
        <div style="display:flex; gap:8px; margin-top:12px;">
          <button class="secondary" id="report-cancel" style="flex:1;">Cancel</button>
          <button class="primary" id="report-submit" style="flex:1;">Submit report</button>
        </div>
      </div>`
    );

    const backdrop = document.getElementById("report-modal-backdrop");
    const modal = document.getElementById("report-modal");
    const reasonBox = document.getElementById("report-reason");
    const errorBox = document.getElementById("report-error");
    const successBox = document.getElementById("report-success");

    const closeReportModal = () => {
      backdrop.style.display = "none";
      modal.style.display = "none";
      reasonBox.value = "";
      errorBox.style.display = "none";
      successBox.style.display = "none";
      window.__activeReportPostId = null;
    };

    backdrop.addEventListener("click", closeReportModal);
    document.getElementById("report-cancel").addEventListener("click", closeReportModal);

    document.getElementById("report-submit").addEventListener("click", async () => {
      const btn = document.getElementById("report-submit");
      errorBox.style.display = "none";
      btn.disabled = true;
      try {
        await api.post(`/api/posts/${window.__activeReportPostId}/report`, { reason: reasonBox.value });
        successBox.textContent = "Report submitted — thank you.";
        successBox.style.display = "block";
        setTimeout(closeReportModal, 1200);
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
      } finally {
        btn.disabled = false;
      }
    });
  }

  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".report-btn");
    if (!btn) return;
    window.__activeReportPostId = btn.dataset.reportPostId;
    document.getElementById("report-modal-backdrop").style.display = "block";
    document.getElementById("report-modal").style.display = "block";
  });
}
