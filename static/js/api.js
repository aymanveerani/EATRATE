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
    window.currentUser = user; // lets renderPostCard show a delete button only on the viewer's own posts
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
  const isMine = window.currentUser && post.user_id === window.currentUser.id;
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
          <div style="display:flex; align-items:center; gap:8px;">
            <div class="rating-pill">${post.rating}/10</div>
            ${isMine ? `<button class="delete-post-btn" data-delete-post-id="${post.id}" title="Delete this post">🗑</button>` : ""}
          </div>
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

function wireDeleteButtons(container) {
  container.addEventListener("click", async (e) => {
    const btn = e.target.closest(".delete-post-btn");
    if (!btn) return;
    if (!confirm("Delete this post? This can't be undone.")) return;
    const postId = btn.dataset.deletePostId;
    btn.disabled = true;
    try {
      await api.del(`/api/posts/${postId}`);
      const card = container.querySelector(`[data-post-id="${postId}"]`);
      if (card) card.remove();
    } catch (err) {
      alert(err.message);
      btn.disabled = false;
    }
  });
}

const CUISINE_ICONS = {
  italian: "🍝",
  pizza: "🍕",
  japanese: "🍣",
  sushi: "🍣",
  mexican: "🌮",
  indian: "🍛",
  chinese: "🥡",
  thai: "🍜",
  american: "🍔",
  burger: "🍔",
  french: "🥐",
  coffee_shop: "☕",
  coffee: "☕",
  cafe: "☕",
  bakery: "🥐",
  seafood: "🦞",
  steak_house: "🥩",
  korean: "🍱",
  mediterranean: "🥙",
  vegan: "🥗",
  vegetarian: "🥗",
  breakfast: "🥞",
  bar: "🍸",
  vietnamese: "🍜",
  greek: "🥙",
  spanish: "🥘",
  argentinian: "🥩",
};

function cuisineIcon(cuisine) {
  if (!cuisine) return "🍽️";
  const key = cuisine.toLowerCase().split(/[;,\s]+/)[0];
  return CUISINE_ICONS[key] || "🍽️";
}

// Cascading image sources for a nearby card, best first.
//   1. The restaurant's actual logo, scraped server-side from its own
//      website (GET /api/restaurants/:id/logo) — the real brand mark,
//      not a favicon-service guess.
//   2. Google's favicon lookup at a real size (128px, not the 64px used
//      before) as a fallback when the site has no discoverable icon —
//      still crisp for known chains, just not guaranteed to be the exact
//      logo.
//   3. A real photo (user's own post, or the source's photo via our
//      proxy) for places without a discoverable website/logo at all.
//   4. The cuisine icon, last resort.
function nearbyImageCandidates(r) {
  const candidates = [];
  // Always try our own /logo endpoint, even if this restaurant has no
  // website_domain on file — the server can still resolve a domain via
  // its curated chain list (server/chain_logos.py) purely from the name,
  // independent of whatever (if anything) the data source returned for
  // its website. Gating this on website_domain meant a known chain like
  // Domino's showed no logo at all whenever the specific franchise
  // location Google/Yelp returned happened to have no website on file —
  // the client just never asked. The endpoint 404s fast if there's truly
  // nothing to resolve, so this is always safe to attempt.
  candidates.push({ cls: "logo", src: `/api/restaurants/${r.id}/logo` });
  if (r.website_domain) {
    candidates.push({
      cls: "logo",
      src: `https://www.google.com/s2/favicons?domain=${encodeURIComponent(r.website_domain)}&sz=128`,
    });
  }
  if (r.photo_url) candidates.push({ cls: "photo", src: r.photo_url });
  if (r.osm_image) candidates.push({ cls: "photo", src: r.osm_image });
  return candidates;
}

function nearbyPhotoError(img) {
  const candidates = JSON.parse(decodeURIComponent(img.dataset.candidates || "[]"));
  const idx = parseInt(img.dataset.idx || "0", 10) + 1;
  if (idx < candidates.length) {
    img.dataset.idx = idx;
    img.className = candidates[idx].cls;
    img.src = candidates[idx].src;
  } else {
    img.replaceWith(
      Object.assign(document.createElement("span"), {
        className: "nearby-photo-fallback",
        textContent: img.dataset.cuisineIcon,
      })
    );
  }
}

function renderNearbyPhoto(r) {
  const icon = cuisineIcon(r.cuisine);
  const candidates = nearbyImageCandidates(r);
  if (candidates.length === 0) {
    return `<span class="nearby-photo-fallback">${icon}</span>`;
  }
  const encodedCandidates = encodeURIComponent(JSON.stringify(candidates));
  return `<img class="${candidates[0].cls}" src="${candidates[0].src}" data-candidates="${encodedCandidates}" data-idx="0" data-cuisine-icon="${escapeHtml(icon)}" loading="lazy" onerror="nearbyPhotoError(this)" />`;
}

function renderNearbyCard(r) {
  const ratingHtml =
    r.post_count > 0
      ? `<div class="nearby-rating">${r.avg_rating}<span>/10</span></div>`
      : `<div class="nearby-rating empty">New</div>`;
  return `
    <a href="/restaurant.html?id=${r.id}" class="nearby-card">
      <div class="nearby-photo">${renderNearbyPhoto(r)}</div>
      <div class="nearby-info">
        <div class="nearby-name">${escapeHtml(r.name)}</div>
        <div class="nearby-meta">${escapeHtml(r.cuisine || "Restaurant")}</div>
      </div>
      ${ratingHtml}
      <span class="nearby-chevron">›</span>
    </a>`;
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
  // "regardless of the rating given" is load-bearing for FTC Consumer
  // Review Rule compliance — it ties the disclosure to the incentive
  // being sentiment-independent. Keep it intact when editing this copy.
  return `
    <div class="ftc-banner">
      ⚠️ Reviews on EatRate may be incentivized: every 5th review a user posts earns them a
      $10 gift card, redeemable at certain restaurants, regardless of the rating given.
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
