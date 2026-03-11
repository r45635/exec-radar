/* Exec Radar - Dashboard client-side logic (vanilla JS, no build) */

(function () {
  "use strict";

  const USER_ID = "default";
  const API_ROOT = "/dashboard";
  const STORE_KEY_FAV = "er_favorites";
  const STORE_KEY_DISMISS = "er_dismissed";
  const CARD_ITEM_HEIGHT = 168;
  const CARD_BUFFER = 6;

  function loadSet(key) {
    try {
      return new Set(JSON.parse(localStorage.getItem(key) || "[]"));
    } catch {
      return new Set();
    }
  }

  function saveSet(key, setValue) {
    localStorage.setItem(key, JSON.stringify([...setValue]));
  }

  const favorites = loadSet(STORE_KEY_FAV);
  const dismissed = loadSet(STORE_KEY_DISMISS);

  const rows = Array.from(document.querySelectorAll(".job-row"));
  if (!rows.length) return;

  const rowsById = new Map(rows.map((row) => [row.dataset.jobId, row]));

  const searchInput = document.getElementById("search-input");
  const filterSeniority = document.getElementById("filter-seniority");
  const filterRemote = document.getElementById("filter-remote");
  const filterStatus = document.getElementById("filter-status");
  const visibleCount = document.querySelector("[data-testid='visible-count']");
  const pageSizeSelect = document.getElementById("page-size");
  const pagePrevBtn = document.getElementById("page-prev");
  const pageNextBtn = document.getElementById("page-next");
  const pageInfo = document.getElementById("page-info");
  const pagination = document.getElementById("pagination");
  const viewTableBtn = document.getElementById("view-table");
  const viewCardsBtn = document.getElementById("view-cards");
  const tableView = document.getElementById("table-view");
  const cardsView = document.getElementById("cards-view");
  const cardsViewport = document.getElementById("cards-viewport");
  const cardsList = document.getElementById("cards-list");
  const cardsSpacerTop = document.getElementById("cards-spacer-top");
  const cardsSpacerBottom = document.getElementById("cards-spacer-bottom");

  const panel = document.getElementById("detail-panel");
  const overlay = document.getElementById("detail-overlay");
  const closeBtn = document.getElementById("detail-close");

  const state = {
    sort: { col: "score", dir: "desc" },
    view: "table",
    filteredIds: [],
    page: 1,
    pageSize: Number(pageSizeSelect ? pageSizeSelect.value : 25),
    cardStart: 0,
  };

  const sortHeaders = document.querySelectorAll("th.sortable");

  function normalizeText(value) {
    return (value || "").toLowerCase();
  }

  function formatDate(value) {
    if (!value) return "-";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "-";
    return parsed.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  async function loadRemotePreferences() {
    try {
      const response = await fetch(
        `${API_ROOT}/preferences?user_id=${encodeURIComponent(USER_ID)}`
      );
      if (!response.ok) return;
      const payload = await response.json();
      favorites.clear();
      dismissed.clear();
      (payload.favorites || []).forEach((jobId) => favorites.add(jobId));
      (payload.dismissed || []).forEach((jobId) => dismissed.add(jobId));
      saveSet(STORE_KEY_FAV, favorites);
      saveSet(STORE_KEY_DISMISS, dismissed);
    } catch {
      // Keep local fallback state if backend isn't reachable.
    }
  }

  async function togglePreference(jobId, action) {
    try {
      const response = await fetch(`${API_ROOT}/preferences/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: USER_ID, job_id: jobId, action: action }),
      });
      if (!response.ok) return;
      const payload = await response.json();
      if (payload.favorited) favorites.add(jobId);
      else favorites.delete(jobId);
      if (payload.dismissed) dismissed.add(jobId);
      else dismissed.delete(jobId);
      saveSet(STORE_KEY_FAV, favorites);
      saveSet(STORE_KEY_DISMISS, dismissed);
    } catch {
      // Network failure: keep optimistic UI state already applied.
    }
  }

  function applyStateClasses() {
    rows.forEach((row) => {
      const id = row.dataset.jobId;
      row.classList.toggle("favorited", favorites.has(id));
      row.classList.toggle("dismissed", dismissed.has(id));
    });
  }

  function compareRows(a, b, sort) {
    const { col, dir } = sort;
    let va = "";
    let vb = "";

    if (col === "score") {
      va = Number(a.dataset.score || 0);
      vb = Number(b.dataset.score || 0);
    } else if (col === "date") {
      va = a.dataset.postedAt || "";
      vb = b.dataset.postedAt || "";
    } else if (col === "title") {
      va = normalizeText(a.dataset.title);
      vb = normalizeText(b.dataset.title);
    } else if (col === "company") {
      va = normalizeText(a.dataset.company);
      vb = normalizeText(b.dataset.company);
    }

    if (va < vb) return dir === "asc" ? -1 : 1;
    if (va > vb) return dir === "asc" ? 1 : -1;
    return 0;
  }

  function getFilteredIds() {
    const q = normalizeText(searchInput ? searchInput.value : "");
    const sen = filterSeniority ? filterSeniority.value : "";
    const rem = filterRemote ? filterRemote.value : "";
    const sts = filterStatus ? filterStatus.value : "active";

    const ordered = rows.slice().sort((a, b) => compareRows(a, b, state.sort));

    return ordered
      .filter((row) => {
        const id = row.dataset.jobId;
        const textMatch =
          !q ||
          normalizeText(row.dataset.title).includes(q) ||
          normalizeText(row.dataset.company).includes(q) ||
          normalizeText(row.dataset.location).includes(q);
        const senMatch = !sen || row.dataset.seniority === sen;
        const remMatch = !rem || row.dataset.remote === rem;

        let statusMatch = true;
        if (sts === "active") statusMatch = !dismissed.has(id);
        else if (sts === "favorites") statusMatch = favorites.has(id);
        else if (sts === "dismissed") statusMatch = dismissed.has(id);

        return textMatch && senMatch && remMatch && statusMatch;
      })
      .map((row) => row.dataset.jobId);
  }

  function renderTablePage() {
    const total = state.filteredIds.length;
    const pageCount = Math.max(1, Math.ceil(total / state.pageSize));
    if (state.page > pageCount) state.page = pageCount;

    const start = (state.page - 1) * state.pageSize;
    const end = start + state.pageSize;
    const visibleIds = new Set(state.filteredIds.slice(start, end));

    rows.forEach((row) => {
      row.hidden = !visibleIds.has(row.dataset.jobId);
    });

    if (pageInfo) pageInfo.textContent = `Page ${state.page} / ${pageCount}`;
    if (pagePrevBtn) pagePrevBtn.disabled = state.page <= 1;
    if (pageNextBtn) pageNextBtn.disabled = state.page >= pageCount;
    if (visibleCount) {
      visibleCount.textContent =
        total < rows.length ? `${total} of ${rows.length} shown` : "";
    }
  }

  function buildCard(jobId) {
    const row = rowsById.get(jobId);
    if (!row) return "";
    const scorePct = Math.round(Number(row.dataset.score || 0) * 100);
    const company = row.dataset.company || "-";
    const location = row.dataset.location || "-";
    const remote = row.dataset.remote || "unknown";
    const seniority = (row.dataset.seniority || "other").replace("_", " ");
    const postedAt = formatDate(row.dataset.postedAt || "");
    const source = row.dataset.source || "-";
    const cardCls = [
      "job-card",
      favorites.has(jobId) ? "favorited" : "",
      dismissed.has(jobId) ? "dismissed" : "",
    ]
      .filter(Boolean)
      .join(" ");

    return `
      <article class="${cardCls}" data-job-id="${escapeHtml(jobId)}">
        <div class="job-card-header">
          <button class="job-card-title" data-role="open-detail">${escapeHtml(
            row.dataset.title || "Untitled"
          )}</button>
          <span class="score-value">${scorePct}%</span>
        </div>
        <div class="job-card-meta">
          <div>${escapeHtml(company)} • ${escapeHtml(location)}</div>
          <div>${escapeHtml(remote)} • ${escapeHtml(seniority)} • ${escapeHtml(
      postedAt
    )}</div>
          <div>${escapeHtml(source)}</div>
        </div>
        <div class="job-card-actions">
          <div class="job-card-tags">
            <span class="badge badge-seniority">${escapeHtml(seniority)}</span>
            <span class="badge ${badgeClassForRemote(remote)}">${escapeHtml(
      remote
    )}</span>
          </div>
          <div>
            <button class="btn-icon" data-role="fav-card" title="Toggle favorite">★</button>
            <button class="btn-icon" data-role="dismiss-card" title="Dismiss">✕</button>
          </div>
        </div>
      </article>
    `;
  }

  function renderCardsPage() {
    const total = state.filteredIds.length;
    if (!cardsList) return;

    const pageCount = Math.max(1, Math.ceil(total / state.pageSize));
    if (state.page > pageCount) state.page = pageCount;

    const start = (state.page - 1) * state.pageSize;
    const end = start + state.pageSize;

    const html = state.filteredIds.slice(start, end).map(buildCard).join("");
    cardsList.innerHTML = html;

    if (pageInfo) pageInfo.textContent = `Page ${state.page} / ${pageCount}`;
    if (pagePrevBtn) pagePrevBtn.disabled = state.page <= 1;
    if (pageNextBtn) pageNextBtn.disabled = state.page >= pageCount;
    if (visibleCount) {
      visibleCount.textContent =
        total < rows.length ? `${total} of ${rows.length} shown` : "";
    }
  }

  function render() {
    state.filteredIds = getFilteredIds();

    if (state.view === "table") {
      if (tableView) tableView.hidden = false;
      if (cardsView) cardsView.hidden = true;
      if (pagination) pagination.hidden = false;
      renderTablePage();
    } else {
      rows.forEach((row) => {
        row.hidden = true;
      });
      if (tableView) tableView.hidden = true;
      if (cardsView) cardsView.hidden = false;
      if (pagination) pagination.hidden = false;
      renderCardsPage();
    }

    syncSortHeaders();
  }

  function syncSortHeaders() {
    sortHeaders.forEach((th) => {
      th.classList.remove("sort-asc", "sort-desc");
      if (th.dataset.sort === state.sort.col) {
        th.classList.add(state.sort.dir === "asc" ? "sort-asc" : "sort-desc");
      }
    });
  }

  function toggleView(view) {
    state.view = view;
    if (viewTableBtn) viewTableBtn.classList.toggle("active", view === "table");
    if (viewCardsBtn) viewCardsBtn.classList.toggle("active", view === "cards");
    state.page = 1;
    state.cardStart = 0;
    if (cardsViewport) cardsViewport.scrollTop = 0;
    render();
  }

  function openDetailByRow(row) {
    if (!row) return;

    rows.forEach((item) => item.classList.remove("active"));
    row.classList.add("active");

    document.getElementById("detail-title").textContent = row.dataset.title;
    document.getElementById("detail-company").textContent = row.dataset.company || "-";
    document.getElementById("detail-location").textContent = row.dataset.location || "-";
    document.getElementById("detail-remote").textContent = row.dataset.remote || "-";
    document.getElementById("detail-seniority").textContent = (row.dataset.seniority || "-").replace(
      "_",
      " "
    );
    document.getElementById("detail-source").textContent = row.dataset.source || "-";
    document.getElementById("detail-date").textContent = formatDate(row.dataset.postedAt);

    const salaryRow = document.getElementById("detail-salary-row");
    const salaryMin = row.dataset.salaryMin;
    const salaryMax = row.dataset.salaryMax;
    const salaryCurrency = row.dataset.salaryCurrency || "";
    if (salaryMin || salaryMax) {
      salaryRow.style.display = "";
      const parts = [];
      if (salaryMin) parts.push(Number(salaryMin).toLocaleString());
      if (salaryMax) parts.push(Number(salaryMax).toLocaleString());
      document.getElementById("detail-salary").textContent =
        parts.join(" - ") + (salaryCurrency ? ` ${salaryCurrency}` : "");
    } else {
      salaryRow.style.display = "none";
    }

    const pct = Math.round(Number(row.dataset.score || 0) * 100);
    document.getElementById("detail-score-pct").textContent = `${pct}%`;

    // 6-dimension bars (new structured scores)
    const dims = [
      { id: "dim-title", key: "dimTitle" },
      { id: "dim-seniority", key: "dimSeniority" },
      { id: "dim-industry", key: "dimIndustry" },
      { id: "dim-scope", key: "dimScope" },
      { id: "dim-geography", key: "dimGeography" },
      { id: "dim-kw", key: "dimKw" },
    ];
    dims.forEach(({ id, key }) => {
      const val = Math.round(Number(row.dataset[key] || 0) * 100);
      document.getElementById(id).style.width = `${val}%`;
      const pctEl = document.getElementById(`${id}-pct`);
      if (pctEl) pctEl.textContent = `${val}%`;
    });

    // Structured why / penalties / red flags
    const whySection = document.getElementById("detail-why-section");
    const whyMatchedEl = document.getElementById("detail-why-matched");
    const whyPenalizedEl = document.getElementById("detail-why-penalized");
    const redFlagsEl = document.getElementById("detail-red-flags");

    const whyMatched = (row.dataset.whyMatched || "").split("||").filter(Boolean);
    const whyPenalized = (row.dataset.whyPenalized || "").split("||").filter(Boolean);
    const redFlags = (row.dataset.redFlags || "").split("||").filter(Boolean);

    const hasStructured = whyMatched.length || whyPenalized.length || redFlags.length;
    whySection.style.display = hasStructured ? "" : "none";

    whyMatchedEl.innerHTML = whyMatched.length
      ? `<h4 class="why-heading why-heading-match">&#x2714; Matched</h4><ul>${whyMatched.map(w => `<li>${escapeHtml(w)}</li>`).join("")}</ul>`
      : "";
    whyPenalizedEl.innerHTML = whyPenalized.length
      ? `<h4 class="why-heading why-heading-penalty">&#x26A0; Penalized</h4><ul>${whyPenalized.map(w => `<li>${escapeHtml(w)}</li>`).join("")}</ul>`
      : "";
    redFlagsEl.innerHTML = redFlags.length
      ? `<h4 class="why-heading why-heading-red">&#x2716; Red Flags</h4><ul>${redFlags.map(w => `<li>${escapeHtml(w)}</li>`).join("")}</ul>`
      : "";

    document.getElementById("detail-explanation").textContent = row.dataset.explanation || "";

    const tagsSection = document.getElementById("detail-tags-section");
    const tagsContainer = document.getElementById("detail-tags");
    const tags = (row.dataset.tags || "").split(",").filter(Boolean);
    if (tags.length) {
      tagsSection.style.display = "";
      tagsContainer.innerHTML = tags.map((tag) => `<span class=\"tag\">${escapeHtml(tag)}</span>`).join("");
    } else {
      tagsSection.style.display = "none";
      tagsContainer.innerHTML = "";
    }

    document.getElementById("detail-description").textContent =
      row.dataset.description || "No description available.";

    const link = document.getElementById("detail-link");
    if (row.dataset.sourceUrl) {
      link.href = row.dataset.sourceUrl;
      link.style.display = "";
    } else {
      link.style.display = "none";
    }

    panel.classList.add("open");
    overlay.classList.add("open");
  }

  function closeDetail() {
    panel.classList.remove("open");
    overlay.classList.remove("open");
    rows.forEach((row) => row.classList.remove("active"));
  }

  function optimisticToggle(jobId, action) {
    if (action === "favorite") {
      if (favorites.has(jobId)) favorites.delete(jobId);
      else favorites.add(jobId);
      dismissed.delete(jobId);
    } else {
      if (dismissed.has(jobId)) dismissed.delete(jobId);
      else dismissed.add(jobId);
      favorites.delete(jobId);
    }
    saveSet(STORE_KEY_FAV, favorites);
    saveSet(STORE_KEY_DISMISS, dismissed);
    applyStateClasses();
    render();
    void togglePreference(jobId, action).then(() => {
      applyStateClasses();
      render();
    });
  }

  function badgeClassForRemote(remote) {
    if (remote === "remote") return "badge-remote";
    if (remote === "hybrid") return "badge-hybrid";
    if (remote === "onsite") return "badge-onsite";
    return "badge-unknown";
  }

  function escapeHtml(value) {
    const element = document.createElement("span");
    element.textContent = String(value || "");
    return element.innerHTML;
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.page = 1;
      state.cardStart = 0;
      render();
    });
  }
  if (filterSeniority) {
    filterSeniority.addEventListener("change", () => {
      state.page = 1;
      state.cardStart = 0;
      render();
    });
  }
  if (filterRemote) {
    filterRemote.addEventListener("change", () => {
      state.page = 1;
      state.cardStart = 0;
      render();
    });
  }
  if (filterStatus) {
    filterStatus.addEventListener("change", () => {
      state.page = 1;
      state.cardStart = 0;
      render();
    });
  }

  if (pageSizeSelect) {
    pageSizeSelect.addEventListener("change", () => {
      state.pageSize = Number(pageSizeSelect.value);
      state.page = 1;
      render();
    });
  }

  if (pagePrevBtn) {
    pagePrevBtn.addEventListener("click", () => {
      state.page = Math.max(1, state.page - 1);
      render();
    });
  }

  if (pageNextBtn) {
    pageNextBtn.addEventListener("click", () => {
      state.page += 1;
      render();
    });
  }

  if (viewTableBtn) {
    viewTableBtn.addEventListener("click", () => toggleView("table"));
  }
  if (viewCardsBtn) {
    viewCardsBtn.addEventListener("click", () => toggleView("cards"));
  }

  sortHeaders.forEach((header) => {
    header.addEventListener("click", () => {
      const column = header.dataset.sort;
      if (!column) return;
      if (state.sort.col === column) {
        state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
      } else {
        state.sort = { col: column, dir: column === "score" ? "desc" : "asc" };
      }
      state.page = 1;
      state.cardStart = 0;
      render();
    });
  });

  document.addEventListener("click", (event) => {
    const favoriteButton = event.target.closest(".btn-fav");
    if (favoriteButton) {
      event.stopPropagation();
      const row = favoriteButton.closest(".job-row");
      if (row) optimisticToggle(row.dataset.jobId, "favorite");
      return;
    }

    const dismissButton = event.target.closest(".btn-dismiss");
    if (dismissButton) {
      event.stopPropagation();
      const row = dismissButton.closest(".job-row");
      if (row) optimisticToggle(row.dataset.jobId, "dismissed");
      return;
    }

    const titleButton = event.target.closest(".job-title-btn");
    if (titleButton) {
      const row = titleButton.closest(".job-row");
      openDetailByRow(row);
      return;
    }

    const clickedRow = event.target.closest(".job-row");
    if (clickedRow && !event.target.closest(".btn-icon")) {
      openDetailByRow(clickedRow);
      return;
    }

    const cardOpen = event.target.closest("[data-role='open-detail']");
    if (cardOpen) {
      const card = cardOpen.closest(".job-card");
      if (!card) return;
      openDetailByRow(rowsById.get(card.dataset.jobId));
      return;
    }

    const cardFav = event.target.closest("[data-role='fav-card']");
    if (cardFav) {
      const card = cardFav.closest(".job-card");
      if (!card) return;
      optimisticToggle(card.dataset.jobId, "favorite");
      return;
    }

    const cardDismiss = event.target.closest("[data-role='dismiss-card']");
    if (cardDismiss) {
      const card = cardDismiss.closest(".job-card");
      if (!card) return;
      optimisticToggle(card.dataset.jobId, "dismissed");
    }
  });

  if (cardsViewport) {
    cardsViewport.addEventListener("scroll", () => {
      // Cards now use pagination; scroll handler kept for future use.
    });
  }

  if (closeBtn) closeBtn.addEventListener("click", closeDetail);
  if (overlay) overlay.addEventListener("click", closeDetail);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDetail();
  });

  (async function init() {
    await loadRemotePreferences();
    applyStateClasses();
    render();
  })();
})();
