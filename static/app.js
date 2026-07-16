const state = {
  config: null,
  statusTimer: null,
  checking: false,
  listings: [],
  notifiedIds: new Set(),
  lastWatchResultKey: null,
};

const els = {
  city: document.querySelector("#city"),
  propertyType: document.querySelector("#propertyType"),
  maxRent: document.querySelector("#maxRent"),
  minRooms: document.querySelector("#minRooms"),
  minArea: document.querySelector("#minArea"),
  keyword: document.querySelector("#keyword"),
  pollSeconds: document.querySelector("#pollSeconds"),
  sources: document.querySelector("#sources"),
  cityNote: document.querySelector("#city-note"),
  checkNow: document.querySelector("#checkNow"),
  startWatch: document.querySelector("#startWatch"),
  stopWatch: document.querySelector("#stopWatch"),
  enableNotifications: document.querySelector("#enableNotifications"),
  markSeen: document.querySelector("#markSeen"),
  notice: document.querySelector("#notice"),
  watchIndicator: document.querySelector("#watch-indicator"),
  watchLabel: document.querySelector("#watch-label"),
  resultCount: document.querySelector("#result-count"),
  newCount: document.querySelector("#new-count"),
  fetchedCount: document.querySelector("#fetched-count"),
  lastCheck: document.querySelector("#last-check"),
  sourceStatus: document.querySelector("#source-status"),
  listings: document.querySelector("#listings"),
  sortMode: document.querySelector("#sortMode"),
};

function showNotice(message, isError = false) {
  els.notice.textContent = message;
  els.notice.className = `notice show${isError ? " error" : ""}`;
}

function clearNoticeSoon() {
  window.setTimeout(() => {
    els.notice.className = "notice";
    els.notice.textContent = "";
  }, 6000);
}

function setWatchState(kind, label) {
  els.watchIndicator.className = `dot ${kind}`;
  els.watchLabel.textContent = label;
}

function option(value, label) {
  const node = document.createElement("option");
  node.value = value;
  node.textContent = label;
  return node;
}

function populateConfig(config) {
  state.config = config;
  for (const city of config.cities) {
    els.city.append(option(city.id, city.name));
  }
  for (const type of config.propertyTypes) {
    els.propertyType.append(option(type.id, type.name));
  }
  for (const source of config.sources) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "source";
    input.value = source.id;
    input.checked = config.defaults.sources.includes(source.id);
    label.append(input, source.name);
    els.sources.append(label);
  }
  els.city.value = config.defaults.city;
  els.propertyType.value = config.defaults.propertyType;
  els.pollSeconds.value = config.defaults.pollSeconds ?? 30;
  updateCityNote();
}

function updateCityNote() {
  const city = state.config?.cities.find((item) => item.id === els.city.value);
  els.cityNote.textContent = city ? city.pressureNote : "Local watcher for difficult student rental markets.";
}

function numericValue(input) {
  return input.value === "" ? "" : Number(input.value);
}

function buildFilters() {
  const sources = [...document.querySelectorAll("input[name='source']:checked")].map((input) => input.value);
  return {
    city: els.city.value,
    sources,
    propertyType: els.propertyType.value,
    maxRent: numericValue(els.maxRent),
    minRooms: numericValue(els.minRooms),
    minArea: numericValue(els.minArea),
    keyword: els.keyword.value.trim(),
  };
}

async function getJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok || data.error) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.error) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

function formatTime(value) {
  if (!value) return "Never";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], { dateStyle: "short", timeStyle: "short" });
}

function formatClock(value) {
  if (!value) return "Never";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatNumber(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "Unknown";
  return `${Number(value).toLocaleString()}${suffix}`;
}

function thumbnailFallback(listing) {
  const source = listing.source_label || listing.source || "Rent";
  const type = listing.listing_type || "rental";
  return `${source.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase()}\n${type}`;
}

function resultKey(data) {
  return [data?.checkedAt || "", data?.fetched || 0, data?.newListingIds?.join(",") || ""].join("|");
}

function renderStatuses(statuses) {
  els.sourceStatus.innerHTML = "";
  if (!statuses?.length) {
    els.sourceStatus.className = "source-status empty";
    els.sourceStatus.textContent = "No checks yet.";
    return;
  }
  els.sourceStatus.className = "source-status";
  for (const status of statuses) {
    const card = document.createElement("div");
    card.className = `source-card ${status.ok ? "ok" : "fail"}`;
    const title = document.createElement("strong");
    title.textContent = status.source_label;
    const message = document.createElement("span");
    message.textContent = status.ok ? `OK · ${status.fetched} found` : status.message;
    card.append(title, message);
    if (status.url) {
      const link = document.createElement("a");
      link.href = status.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = "Open source search";
      card.append(link);
    }
    els.sourceStatus.append(card);
  }
}

function sortedListings() {
  const listings = [...state.listings];
  if (els.sortMode.value === "rent") {
    return listings.sort((a, b) => (a.rent_eur ?? 999999) - (b.rent_eur ?? 999999));
  }
  if (els.sortMode.value === "size") {
    return listings.sort((a, b) => (b.area_sqm ?? 0) - (a.area_sqm ?? 0));
  }
  return listings.sort((a, b) => String(b.last_seen).localeCompare(String(a.last_seen)));
}

function renderListings() {
  els.listings.innerHTML = "";
  const listings = sortedListings();
  if (!listings.length) {
    els.listings.className = "listing-list empty";
    els.listings.textContent = "No matching listings yet.";
    return;
  }
  els.listings.className = "listing-list";
  for (const listing of listings) {
    const row = document.createElement("article");
    row.className = `listing${listing.is_new ? " is-new" : ""}`;

    const thumb = document.createElement("a");
    thumb.className = "thumb";
    thumb.href = listing.url;
    thumb.target = "_blank";
    thumb.rel = "noreferrer";
    thumb.setAttribute("aria-label", `Open ${listing.title || "listing"}`);
    if (listing.image_url) {
      const img = document.createElement("img");
      img.src = listing.image_url;
      img.alt = "";
      img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      img.addEventListener("error", () => {
        img.remove();
        thumb.classList.add("fallback");
        thumb.textContent = thumbnailFallback(listing);
      }, { once: true });
      thumb.append(img);
    } else {
      thumb.classList.add("fallback");
      thumb.textContent = thumbnailFallback(listing);
    }

    const body = document.createElement("div");
    body.className = "listing-body";
    const title = document.createElement("h3");
    const link = document.createElement("a");
    link.href = listing.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = listing.title || "Rental listing";
    title.append(link);

    const meta = document.createElement("div");
    meta.className = "meta";
    const values = [
      listing.source_label,
      listing.location,
      listing.listing_type,
      listing.rooms ? `${listing.rooms} rooms` : null,
      listing.area_sqm ? `${listing.area_sqm} m2` : null,
      `seen ${formatTime(listing.first_seen)}`,
    ].filter(Boolean);
    for (const value of values) {
      const pill = document.createElement("span");
      pill.className = "pill";
      pill.textContent = value;
      meta.append(pill);
    }
    body.append(title, meta);

    const rent = document.createElement("div");
    rent.className = "rent";
    rent.textContent = listing.rent_eur ? `${formatNumber(listing.rent_eur)} EUR` : "Rent unknown";

    row.append(thumb, body, rent);
    els.listings.append(row);
  }
}

function renderSummary(data) {
  els.resultCount.textContent = String(data.listings?.length || 0);
  els.newCount.textContent = String(data.newCount || 0);
  els.fetchedCount.textContent = String(data.fetched || 0);
  els.lastCheck.textContent = formatClock(data.checkedAt);
}

function renderResult(data) {
  state.listings = data.listings || [];
  state.lastWatchResultKey = resultKey(data);
  renderSummary(data);
  renderStatuses(data.statuses);
  renderListings();
}

function beep() {
  try {
    const context = new AudioContext();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = 880;
    gain.gain.value = 0.06;
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.12);
  } catch {
    // Audio is optional.
  }
}

function notifyNewListings(data) {
  if (data.baseline) return;
  const ids = new Set(data.newListingIds || []);
  const newListings = (data.listings || []).filter((listing) => ids.has(listing.id) && !state.notifiedIds.has(listing.id));
  if (!newListings.length) return;
  for (const listing of newListings) {
    state.notifiedIds.add(listing.id);
  }
  beep();
  showNotice(`${newListings.length} new matching listing${newListings.length === 1 ? "" : "s"} found.`);
  clearNoticeSoon();
  if ("Notification" in window && Notification.permission === "granted") {
    const first = newListings[0];
    const notification = new Notification(`${newListings.length} new rental listing${newListings.length === 1 ? "" : "s"}`, {
      body: `${first.source_label}: ${first.title}`,
      tag: `rental-watch-${first.id}`,
    });
    notification.onclick = () => {
      window.focus();
      window.open(first.url, "_blank", "noreferrer");
    };
  }
}

async function checkNow({ manual = false } = {}) {
  if (state.checking) return;
  const filters = buildFilters();
  if (!filters.sources.length) {
    showNotice("Pick at least one source.", true);
    return;
  }
  state.checking = true;
  setWatchState("checking", "Checking now");
  els.checkNow.disabled = true;
  try {
    const data = await postJson("/api/check", filters);
    renderResult(data);
    notifyNewListings(data);
    if (data.baseline) {
      showNotice(`Baseline saved for ${data.city}. Future checks will notify only genuinely new listings.`);
      clearNoticeSoon();
    } else if (manual) {
      showNotice(data.newCount ? `${data.newCount} new listing(s) found.` : "No new listings this check.");
      clearNoticeSoon();
    }
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.checking = false;
    els.checkNow.disabled = false;
    refreshWatchStatus().catch(() => setWatchState("idle", "Idle"));
  }
}

function applyWatchStatus(status, { notify = true } = {}) {
  const running = Boolean(status.running);
  els.startWatch.disabled = running;
  els.stopWatch.disabled = !running;
  if (running && status.checking) {
    setWatchState("checking", "Scanning in background");
  } else if (running) {
    setWatchState("running", `Watching every ${status.intervalSeconds}s`);
  } else if (!state.checking) {
    setWatchState("idle", "Idle");
  }
  if (running && status.intervalSeconds) {
    els.pollSeconds.value = status.intervalSeconds;
  }
  if (status.lastResult && resultKey(status.lastResult) !== state.lastWatchResultKey) {
    renderResult(status.lastResult);
    if (notify) notifyNewListings(status.lastResult);
  }
  if (status.lastError) {
    showNotice(status.lastError, true);
  }
}

async function refreshWatchStatus(options = {}) {
  const key = state.lastWatchResultKey ? `?resultKey=${encodeURIComponent(state.lastWatchResultKey)}` : "";
  const status = await getJson(`/api/watch/status${key}`);
  applyWatchStatus(status, options);
  return status;
}

function ensureStatusPolling() {
  if (state.statusTimer) return;
  state.statusTimer = window.setInterval(() => {
    refreshWatchStatus().catch(() => {
      setWatchState("idle", "Server unavailable");
    });
  }, 5000);
}

async function startWatching() {
  const filters = buildFilters();
  if (!filters.sources.length) {
    showNotice("Pick at least one source.", true);
    return;
  }
  const seconds = Math.max(30, Math.min(300, Number(els.pollSeconds.value) || 30));
  els.pollSeconds.value = seconds;
  els.startWatch.disabled = true;
  try {
    const status = await postJson("/api/watch/start", { ...filters, intervalSeconds: seconds });
    applyWatchStatus(status, { notify: false });
    ensureStatusPolling();
    showNotice("Background watcher started. It will keep scanning while this server is running.");
    clearNoticeSoon();
  } catch (error) {
    els.startWatch.disabled = false;
    showNotice(error.message, true);
  }
}

async function stopWatching() {
  els.stopWatch.disabled = true;
  try {
    const status = await postJson("/api/watch/stop", {});
    applyWatchStatus(status, { notify: false });
    showNotice("Background watcher stopped.");
    clearNoticeSoon();
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function enableNotifications() {
  if (!("Notification" in window)) {
    showNotice("This browser does not support desktop notifications.", true);
    return;
  }
  const permission = await Notification.requestPermission();
  showNotice(permission === "granted" ? "Notifications enabled." : "Notifications were not enabled.", permission !== "granted");
  clearNoticeSoon();
}

async function markAllSeen() {
  try {
    await postJson("/api/seen", {});
    state.listings = state.listings.map((listing) => ({ ...listing, is_new: false, seen: 1 }));
    renderListings();
    els.newCount.textContent = "0";
    showNotice("Listings marked seen.");
    clearNoticeSoon();
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function init() {
  const response = await fetch("/api/config");
  populateConfig(await response.json());
  els.city.addEventListener("change", updateCityNote);
  els.checkNow.addEventListener("click", () => checkNow({ manual: true }));
  els.startWatch.addEventListener("click", startWatching);
  els.stopWatch.addEventListener("click", stopWatching);
  els.enableNotifications.addEventListener("click", enableNotifications);
  els.markSeen.addEventListener("click", markAllSeen);
  els.sortMode.addEventListener("change", renderListings);
  ensureStatusPolling();
  await refreshWatchStatus({ notify: false });
}

init().catch((error) => showNotice(error.message, true));
