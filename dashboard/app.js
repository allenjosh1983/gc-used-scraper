(function () {
  const $ = (id) => document.getElementById(id);

  const dateSelect = $("date-select");
  const sourceSelect = $("source-select");
  const filterSearch = $("filter-search");
  const filterMinPrice = $("filter-min-price");
  const filterMaxPrice = $("filter-max-price");
  const filterMinDiscount = $("filter-min-discount");
  const filterPriceDrop = $("filter-price-drop");
  const btnReset = $("btn-reset");
  const statusEl = $("status");
  const statCount = $("stat-count");
  const statUpdated = $("stat-updated");
  const statRuns = $("stat-runs");
  const statsPanel = $("stats-panel");
  const statsGrid = $("stats-grid");
  const runHistoryList = $("run-history-list");
  const tbody = $("listings-body");
  const table = $("listings-table");

  let allItems = [];
  let sortKey = "created_at";
  let sortDir = "desc";

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  async function api(path) {
    const res = await fetch(path);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  function formatMoney(n) {
    if (n == null || n === "") return "—";
    return "$" + Number(n).toFixed(2);
  }

  function formatDate(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  }

  function formatUpdated(iso) {
    if (!iso) return "—";
    try {
      return "Updated " + new Date(iso).toLocaleString();
    } catch {
      return "Updated " + iso;
    }
  }

  function haystack(item) {
    return [
      item.title,
      item.brand,
      item.store,
      item.condition,
      item.sku_id,
      item.category,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  }

  function passesFilters(item) {
    const q = filterSearch.value.trim().toLowerCase();
    if (q && !haystack(item).includes(q)) return false;

    const minP = filterMinPrice.value.trim();
    if (minP !== "" && (item.price == null || item.price < Number(minP))) return false;

    const maxP = filterMaxPrice.value.trim();
    if (maxP !== "" && (item.price == null || item.price > Number(maxP))) return false;

    const minD = filterMinDiscount.value.trim();
    if (minD !== "") {
      const d = item.discount_percent != null ? Number(item.discount_percent) : 0;
      if (d < Number(minD)) return false;
    }

    if (filterPriceDrop.checked && !item.is_price_drop) return false;
    return true;
  }

  function compare(a, b, key) {
    const va = a[key];
    const vb = b[key];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "number" && typeof vb === "number") return va - vb;
    return String(va).localeCompare(String(vb));
  }

  function filteredSorted() {
    return allItems
      .filter(passesFilters)
      .sort((a, b) => {
        const c = compare(a, b, sortKey);
        return sortDir === "asc" ? c : -c;
      });
  }

  function updateSortHeaders() {
    table.querySelectorAll("th[data-sort]").forEach((th) => {
      th.classList.remove("sorted-asc", "sorted-desc");
      if (th.dataset.sort === sortKey) {
        th.classList.add(sortDir === "asc" ? "sorted-asc" : "sorted-desc");
      }
    });
  }

  function renderTable(rows) {
    tbody.innerHTML = "";
    if (!rows.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 8;
      td.className = "empty";
      td.textContent = allItems.length
        ? "No listings match your filters."
        : "No listings in this dataset.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    for (const item of rows) {
      const tr = document.createElement("tr");
      if (item.is_price_drop) tr.classList.add("drop");
      tr.title = "Open on Guitar Center";
      tr.addEventListener("click", () => {
        if (item.url) window.open(item.url, "_blank", "noopener,noreferrer");
      });

      const disc =
        item.discount_percent != null && item.discount_percent > 0
          ? item.discount_percent
          : null;

      tr.innerHTML = `
        <td class="title">${escapeHtml(item.title || "—")}
          ${item.is_price_drop ? '<span class="badge">Drop</span>' : ""}
        </td>
        <td>${escapeHtml(item.brand || "—")}</td>
        <td class="num">${formatMoney(item.price)}</td>
        <td class="num">${formatMoney(item.list_price)}</td>
        <td class="num ${disc >= 15 ? "discount-high" : ""}">${disc != null ? disc.toFixed(1) + "%" : "—"}</td>
        <td>${escapeHtml(item.condition || "—")}</td>
        <td>${escapeHtml(item.store || "—")}</td>
        <td>${formatDate(item.created_at)}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function refreshView() {
    const rows = filteredSorted();
    const total = allItems.length;
    statusEl.textContent =
      rows.length === total
        ? `Showing ${total.toLocaleString()} listing${total === 1 ? "" : "s"}`
        : `Showing ${rows.length.toLocaleString()} of ${total.toLocaleString()}`;
    statCount.textContent = statusEl.textContent;
    updateSortHeaders();
    renderTable(rows);
  }

  function resetFilters() {
    filterSearch.value = "";
    filterMinPrice.value = "";
    filterMaxPrice.value = "";
    filterMinDiscount.value = "";
    filterPriceDrop.checked = false;
    refreshView();
  }

  async function loadStats() {
    const data = await api("/api/stats");
    const latest = data.latest_run;
    statRuns.textContent = `${data.completed_runs} completed run${data.completed_runs === 1 ? "" : "s"} · ${data.data_days} data day${data.data_days === 1 ? "" : "s"}`;

    statsGrid.innerHTML = `
      <div class="stat-card"><span class="label">Run days</span><span class="value">${data.total_run_days}</span></div>
      <div class="stat-card"><span class="label">Completed</span><span class="value">${data.completed_runs}</span></div>
      <div class="stat-card"><span class="label">Data days</span><span class="value">${data.data_days}</span></div>
      <div class="stat-card"><span class="label">Latest</span><span class="value">${latest ? latest.date : "—"}</span></div>
    `;

    runHistoryList.innerHTML = "";
    for (const run of data.runs || []) {
      const li = document.createElement("li");
      li.className = run.completed ? "ok" : "warn";
      li.textContent = `${run.date} — ${run.completed ? "completed" : "incomplete"}${run.started_at ? ` (${run.started_at})` : ""}`;
      runHistoryList.appendChild(li);
    }
    statsPanel.hidden = false;
  }

  async function loadDates() {
    const { dates } = await api("/api/dates");
    dateSelect.innerHTML = "";
    if (!dates.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(no daily output yet)";
      dateSelect.appendChild(opt);
      statusEl.textContent = "Run scripts/run-daily.ps1 to generate output/daily/ dates.";
      return null;
    }
    for (const d of dates) {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = d;
      dateSelect.appendChild(opt);
    }
    return dates[0];
  }

  async function loadSources(date) {
    const data = await api(`/api/sources?date=${encodeURIComponent(date)}`);
    sourceSelect.innerHTML = "";
    for (const j of data.json || []) {
      const opt = document.createElement("option");
      opt.value = j.id;
      opt.textContent = j.label;
      sourceSelect.appendChild(opt);
    }
    for (const cat of data.categories || []) {
      const opt = document.createElement("option");
      opt.value = `category:${cat}`;
      opt.textContent = `Category: ${cat}`;
      sourceSelect.appendChild(opt);
    }
    if (!sourceSelect.options.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(no files for this date)";
      sourceSelect.appendChild(opt);
    }
    return sourceSelect.value || "new-all";
  }

  async function loadListings(date, source) {
    if (!date || !source) {
      allItems = [];
      statUpdated.textContent = "—";
      refreshView();
      return;
    }
    statusEl.textContent = "Loading listings…";
    const data = await api(
      `/api/listings?date=${encodeURIComponent(date)}&source=${encodeURIComponent(source)}`
    );
    allItems = data.items || [];
    statUpdated.textContent = formatUpdated(data.updated_at);
    refreshView();
  }

  async function onDateChange() {
    const date = dateSelect.value;
    if (!date) return;
    try {
      const source = await loadSources(date);
      await loadListings(date, source);
    } catch (e) {
      statusEl.textContent = "Error: " + e.message;
    }
  }

  async function init() {
    table.querySelectorAll("th[data-sort]").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.sort;
        if (sortKey === key) {
          sortDir = sortDir === "asc" ? "desc" : "asc";
        } else {
          sortKey = key;
          sortDir = key === "title" || key === "brand" || key === "store" ? "asc" : "desc";
        }
        refreshView();
      });
    });

    const debouncedRefresh = debounce(refreshView, 150);
    [
      filterSearch,
      filterMinPrice,
      filterMaxPrice,
      filterMinDiscount,
      filterPriceDrop,
    ].forEach((el) => el.addEventListener("input", debouncedRefresh));
    filterPriceDrop.addEventListener("change", refreshView);
    btnReset.addEventListener("click", resetFilters);

    dateSelect.addEventListener("change", onDateChange);
    sourceSelect.addEventListener("change", () => {
      loadListings(dateSelect.value, sourceSelect.value).catch((e) => {
        statusEl.textContent = "Error: " + e.message;
      });
    });

    try {
      await loadStats();
      const first = await loadDates();
      if (first) {
        dateSelect.value = first;
        await onDateChange();
      }
    } catch (e) {
      statusEl.textContent = "Error: " + e.message;
    }
  }

  init();
})();
