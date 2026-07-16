const state = {
  config: null,
  currentCountry: "de",
  user: null,
  accountSummary: null,
  savedSearches: [],
  selectedSearchId: null,
  viewingMode: "live",
  statusTimer: null,
  accountTimer: null,
  checking: false,
  listings: [],
  notifiedIds: new Set(),
  accountNotifiedIds: new Set(),
  lastWatchResultKey: null,
  authMode: "register",
};

const els = {
  country: document.querySelector("#country"),
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
  topCreateAccount: document.querySelector("#topCreateAccount"),
  topSignIn: document.querySelector("#topSignIn"),
  accountChip: document.querySelector("#account-chip"),
  authGuest: document.querySelector("#auth-guest"),
  authUser: document.querySelector("#auth-user"),
  authForm: document.querySelector("#auth-form"),
  authModeTitle: document.querySelector("#authModeTitle"),
  authEmail: document.querySelector("#authEmail"),
  authPassword: document.querySelector("#authPassword"),
  introCreateAccount: document.querySelector("#introCreateAccount"),
  introSignIn: document.querySelector("#introSignIn"),
  loginButton: document.querySelector("#loginButton"),
  registerButton: document.querySelector("#registerButton"),
  logoutButton: document.querySelector("#logoutButton"),
  accountEmail: document.querySelector("#accountEmail"),
  accountSummary: document.querySelector("#accountSummary"),
  saveSearchName: document.querySelector("#saveSearchName"),
  accountNotificationsEnabled: document.querySelector("#accountNotificationsEnabled"),
  saveSearch: document.querySelector("#saveSearch"),
  savedSearches: document.querySelector("#saved-searches"),
  accountResultTools: document.querySelector("#account-result-tools"),
  accountStatusFilter: document.querySelector("#accountStatusFilter"),
  accountFavoritesOnly: document.querySelector("#accountFavoritesOnly"),
  accountShowHidden: document.querySelector("#accountShowHidden"),
  exportResults: document.querySelector("#exportResults"),
  copyDigest: document.querySelector("#copyDigest"),
  adminPanel: document.querySelector("#admin-panel"),
  refreshAdmin: document.querySelector("#refreshAdmin"),
  adminStats: document.querySelector("#admin-stats"),
  adminUsers: document.querySelector("#admin-users"),
  adminSearches: document.querySelector("#admin-searches"),
  adminSources: document.querySelector("#admin-sources"),
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

function setHidden(node, hidden) {
  node.classList.toggle("hidden", hidden);
}

function showAuthMode(mode) {
  state.authMode = mode === "login" ? "login" : "register";
  setHidden(els.authForm, false);
  els.authModeTitle.textContent = state.authMode === "login" ? "Sign in" : "Create account";
  els.loginButton.classList.toggle("primary-action", state.authMode === "login");
  els.registerButton.classList.toggle("primary-action", state.authMode !== "login");
  window.requestAnimationFrame(() => {
    els.authEmail.focus();
  });
}

function openAuth(mode) {
  showAuthMode(mode);
  document.querySelector(".account-panel").scrollIntoView({ behavior: "smooth", block: "center" });
}

function option(value, label) {
  const node = document.createElement("option");
  node.value = value;
  node.textContent = label;
  return node;
}

function populateConfig(config) {
  state.config = config;
  for (const country of config.countries) {
    els.country.append(option(country.id, country.name));
  }
  for (const type of config.propertyTypes) {
    els.propertyType.append(option(type.id, type.name));
  }
  state.currentCountry = config.defaults.country || "de";
  els.country.value = state.currentCountry;
  renderCountryOptions();
  els.propertyType.value = config.defaults.propertyType;
  els.pollSeconds.value = config.defaults.pollSeconds ?? 30;
  updateCityNote();
}

function renderCountryOptions() {
  state.currentCountry = els.country.value || state.currentCountry || "de";
  els.city.innerHTML = "";
  for (const city of state.config.cities.filter((item) => item.country === state.currentCountry)) {
    els.city.append(option(city.id, city.name));
  }
  const firstCity = state.config.cities.find((item) => item.country === state.currentCountry);
  const defaultCity = state.currentCountry === "de" ? "berlin" : "amsterdam";
  els.city.value = state.config.cities.some((item) => item.id === defaultCity && item.country === state.currentCountry)
    ? defaultCity
    : firstCity?.id || "";

  els.sources.innerHTML = "";
  const defaultSources = new Set(state.config.defaults.sources[state.currentCountry] || []);
  for (const source of state.config.sources.filter((item) => item.country === state.currentCountry)) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "source";
    input.value = source.id;
    input.checked = defaultSources.has(source.id);
    label.append(input, source.name);
    els.sources.append(label);
  }
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
    country: els.country.value,
    city: els.city.value,
    sources,
    propertyType: els.propertyType.value,
    maxRent: numericValue(els.maxRent),
    minRooms: numericValue(els.minRooms),
    minArea: numericValue(els.minArea),
    keyword: els.keyword.value.trim(),
  };
}

function applyFilters(filters) {
  if (!filters) return;
  const city = state.config?.cities.find((item) => item.id === filters.city);
  els.country.value = filters.country || city?.country || els.country.value;
  renderCountryOptions();
  if (filters.city && state.config.cities.some((item) => item.id === filters.city && item.country === els.country.value)) {
    els.city.value = filters.city;
  }
  els.propertyType.value = filters.propertyType || "any";
  els.maxRent.value = filters.maxRent || "";
  els.minRooms.value = filters.minRooms || "";
  els.minArea.value = filters.minArea || "";
  els.keyword.value = filters.keyword || "";
  const selected = new Set(filters.sources || []);
  document.querySelectorAll("input[name='source']").forEach((input) => {
    input.checked = selected.has(input.value);
  });
  updateCityNote();
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

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-999px";
  document.body.append(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function mapSearchUrl(listing) {
  const query = [listing.location, cityName(listing.city_id), "Germany"].filter(Boolean).join(" ");
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

function csvValue(value) {
  const text = String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

function thumbnailFallback(listing) {
  const source = listing.source_label || listing.source || "Rent";
  const type = listing.listing_type || "rental";
  return `${source.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase()}\n${type}`;
}

function resultKey(data) {
  return [data?.checkedAt || "", data?.fetched || 0, data?.newListingIds?.join(",") || ""].join("|");
}

function cityName(cityId) {
  return state.config?.cities.find((city) => city.id === cityId)?.name || cityId || "Any city";
}

function typeName(typeId) {
  return state.config?.propertyTypes.find((type) => type.id === typeId)?.name || typeId || "Any rental";
}

function filterSummary(filters) {
  const parts = [cityName(filters.city), typeName(filters.propertyType)];
  if (filters.maxRent) parts.push(`max ${formatNumber(filters.maxRent)} EUR`);
  if (filters.minRooms) parts.push(`${filters.minRooms}+ rooms`);
  if (filters.minArea) parts.push(`${filters.minArea}+ m2`);
  if (filters.keyword) parts.push(`"${filters.keyword}"`);
  return parts.join(" · ");
}

function renderStatuses(statuses) {
  els.sourceStatus.innerHTML = "";
  if (!statuses?.length) {
    els.sourceStatus.className = "source-status empty";
    els.sourceStatus.textContent = state.viewingMode === "account" ? "Showing stored account results." : "No checks yet.";
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

function visibleListings() {
  let listings = [...state.listings];
  if (state.viewingMode === "account") {
    if (!els.accountShowHidden.checked) {
      listings = listings.filter((listing) => !listing.hidden);
    }
    if (els.accountFavoritesOnly.checked) {
      listings = listings.filter((listing) => listing.favorite);
    }
    if (els.accountStatusFilter.value) {
      listings = listings.filter((listing) => (listing.account_status || "new") === els.accountStatusFilter.value);
    }
  }
  return listings;
}

function sortedListings() {
  const listings = visibleListings();
  if (els.sortMode.value === "rent") {
    return listings.sort((a, b) => (a.rent_eur ?? 999999) - (b.rent_eur ?? 999999));
  }
  if (els.sortMode.value === "size") {
    return listings.sort((a, b) => (b.area_sqm ?? 0) - (a.area_sqm ?? 0));
  }
  return listings.sort((a, b) => String(b.last_matched || b.last_seen).localeCompare(String(a.last_matched || a.last_seen)));
}

function renderListings() {
  els.listings.innerHTML = "";
  const listings = sortedListings();
  if (!listings.length) {
    els.listings.className = "listing-list empty";
    els.listings.textContent = state.viewingMode === "account" ? "No stored matches for this saved search yet." : "No matching listings yet.";
    return;
  }
  els.listings.className = "listing-list";
  for (const listing of listings) {
    const row = document.createElement("article");
    row.className = `listing${listing.is_new ? " is-new" : ""}${listing.hidden ? " is-hidden" : ""}`;

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
      listing.favorite ? "favorite" : null,
      listing.hidden ? "hidden" : null,
      listing.account_status && state.viewingMode === "account" ? listing.account_status : null,
      `seen ${formatTime(listing.first_seen)}`,
    ].filter(Boolean);
    for (const value of values) {
      const pill = document.createElement("span");
      pill.className = "pill";
      pill.textContent = value;
      meta.append(pill);
    }
    body.append(title, meta);
    if (state.user && state.viewingMode === "account") {
      body.append(accountListingTools(listing));
    }

    const rent = document.createElement("div");
    rent.className = "rent";
    rent.textContent = listing.rent_eur ? `${formatNumber(listing.rent_eur)} EUR` : "Rent unknown";

    row.append(thumb, body, rent);
    els.listings.append(row);
  }
}

function accountListingTools(listing) {
  const wrap = document.createElement("div");
  wrap.className = "account-tools";

  const favorite = document.createElement("button");
  favorite.type = "button";
  favorite.textContent = listing.favorite ? "Favorited" : "Favorite";
  favorite.addEventListener("click", () => saveListingState(listing, { favorite: !listing.favorite }));

  const hidden = document.createElement("button");
  hidden.type = "button";
  hidden.textContent = listing.hidden ? "Unhide" : "Hide";
  hidden.addEventListener("click", () => saveListingState(listing, { hidden: !listing.hidden }));

  const status = document.createElement("select");
  status.ariaLabel = "Listing status";
  for (const value of ["new", "interested", "contacted", "viewing", "applied", "rejected"]) {
    const node = option(value, value[0].toUpperCase() + value.slice(1));
    status.append(node);
  }
  status.value = listing.account_status || "new";

  const note = document.createElement("input");
  note.type = "text";
  note.placeholder = "Private note";
  note.value = listing.note || "";

  const save = document.createElement("button");
  save.type = "button";
  save.textContent = "Save note/status";
  save.addEventListener("click", () => saveListingState(listing, { status: status.value, note: note.value }));

  const copy = document.createElement("button");
  copy.type = "button";
  copy.textContent = "Copy link";
  copy.addEventListener("click", () => {
    copyText(listing.url).then(() => {
      showNotice("Listing link copied.");
      clearNoticeSoon();
    }).catch((error) => showNotice(error.message, true));
  });

  const map = document.createElement("a");
  map.className = "tool-link";
  map.href = mapSearchUrl(listing);
  map.target = "_blank";
  map.rel = "noreferrer";
  map.textContent = "Map";

  wrap.append(favorite, hidden, status, note, save, copy, map);
  return wrap;
}

async function saveListingState(listing, patch) {
  const payload = {
    listingId: listing.id,
    favorite: Boolean(patch.favorite ?? listing.favorite),
    hidden: Boolean(patch.hidden ?? listing.hidden),
    status: patch.status ?? listing.account_status ?? "new",
    note: patch.note ?? listing.note ?? "",
  };
  const data = await postJson("/api/account/listing-state", payload);
  Object.assign(listing, {
    favorite: data.state.favorite,
    hidden: data.state.hidden,
    account_status: data.state.status,
    note: data.state.note,
  });
  state.accountSummary = data.summary;
  renderAccount();
  updateStoredView();
}

function renderSummary(data) {
  els.resultCount.textContent = String(data.listings?.length || 0);
  els.newCount.textContent = String(data.newCount || 0);
  els.fetchedCount.textContent = String(data.fetched || 0);
  els.lastCheck.textContent = formatClock(data.checkedAt);
}

function renderStoredSummary(search, results) {
  const visible = visibleListings();
  const unseen = visible.filter((listing) => listing.is_new).length;
  els.resultCount.textContent = visible.length === results.length ? String(results.length) : `${visible.length}/${results.length}`;
  els.newCount.textContent = String(unseen);
  els.fetchedCount.textContent = "stored";
  els.lastCheck.textContent = formatClock(search?.lastChecked);
}

function updateStoredView() {
  if (state.viewingMode !== "account" || !state.selectedSearchId) {
    setHidden(els.accountResultTools, true);
    return;
  }
  const search = state.savedSearches.find((item) => item.id === state.selectedSearchId);
  setHidden(els.accountResultTools, false);
  renderStoredSummary(search, state.listings);
  renderListings();
}

function exportVisibleResults() {
  if (state.viewingMode !== "account") {
    showNotice("Open a saved search first.", true);
    return;
  }
  const rows = visibleListings();
  const header = ["Title", "Rent EUR", "Area m2", "Rooms", "Location", "Source", "Status", "Favorite", "Hidden", "Note", "URL"];
  const body = rows.map((listing) => [
    listing.title,
    listing.rent_eur ?? "",
    listing.area_sqm ?? "",
    listing.rooms ?? "",
    listing.location ?? "",
    listing.source_label ?? listing.source,
    listing.account_status ?? "new",
    listing.favorite ? "yes" : "no",
    listing.hidden ? "yes" : "no",
    listing.note ?? "",
    listing.url,
  ]);
  const csv = [header, ...body].map((row) => row.map(csvValue).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const search = state.savedSearches.find((item) => item.id === state.selectedSearchId);
  const filename = `${(search?.name || "saved-search").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "saved-search"}.csv`;
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function copyVisibleDigest() {
  if (state.viewingMode !== "account") {
    showNotice("Open a saved search first.", true);
    return;
  }
  const rows = visibleListings().slice(0, 20);
  if (!rows.length) {
    showNotice("No visible listings to copy.", true);
    return;
  }
  const search = state.savedSearches.find((item) => item.id === state.selectedSearchId);
  const lines = [
    `${search?.name || "Saved search"} shortlist`,
    ...rows.map((listing, index) => {
      const rent = listing.rent_eur ? `${formatNumber(listing.rent_eur)} EUR` : "rent unknown";
      const place = listing.location ? ` · ${listing.location}` : "";
      return `${index + 1}. ${listing.title} · ${rent}${place}\n${listing.url}`;
    }),
  ];
  await copyText(lines.join("\n\n"));
  showNotice("Shortlist summary copied.");
  clearNoticeSoon();
}

function renderResult(data) {
  state.viewingMode = "live";
  state.selectedSearchId = null;
  setHidden(els.accountResultTools, true);
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

function notifyAccountItems(items) {
  const fresh = items.filter((item) => {
    const key = `${item.searchId}:${item.listingId}`;
    if (state.accountNotifiedIds.has(key)) return false;
    state.accountNotifiedIds.add(key);
    return true;
  });
  if (!fresh.length) return;
  beep();
  showNotice(`${fresh.length} new saved-search match${fresh.length === 1 ? "" : "es"} stored in your account.`);
  clearNoticeSoon();
  if ("Notification" in window && Notification.permission === "granted") {
    const first = fresh[0];
    const notification = new Notification(`${fresh.length} saved-search match${fresh.length === 1 ? "" : "es"}`, {
      body: `${first.searchName}: ${first.title}`,
      tag: `saved-search-${first.searchId}-${first.listingId}`,
    });
    notification.onclick = () => {
      window.focus();
      loadSavedSearchResults(first.searchId).catch((error) => showNotice(error.message, true));
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
  if (state.viewingMode === "live" && status.lastResult && resultKey(status.lastResult) !== state.lastWatchResultKey) {
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

function ensureAccountPolling() {
  if (state.accountTimer) return;
  state.accountTimer = window.setInterval(() => {
    if (!state.user) return;
    refreshAccount({ quiet: true }).catch(() => {});
    refreshAccountNotifications().catch(() => {});
  }, 10000);
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
    if (state.user && state.viewingMode === "account" && state.selectedSearchId) {
      const data = await postJson("/api/account/search-results/seen", { searchId: state.selectedSearchId });
      state.listings = state.listings.map((listing) => ({ ...listing, is_new: false, search_seen: 1 }));
      state.accountSummary = data.summary;
      renderAccount();
      updateStoredView();
    } else {
      await postJson("/api/seen", {});
      state.listings = state.listings.map((listing) => ({ ...listing, is_new: false, seen: 1 }));
      renderListings();
      els.newCount.textContent = "0";
    }
    showNotice("Listings marked seen.");
    clearNoticeSoon();
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function loadMe() {
  const data = await getJson("/api/me");
  state.user = data.user;
  state.accountSummary = data.summary;
  renderAccount();
  if (state.user) {
    await refreshAccount({ quiet: true });
    ensureAccountPolling();
  }
}

function authPayload() {
  return {
    email: els.authEmail.value.trim(),
    password: els.authPassword.value,
  };
}

async function register() {
  const data = await postJson("/api/auth/register", authPayload());
  state.user = data.user;
  state.accountSummary = data.summary;
  els.authPassword.value = "";
  await refreshAccount({ quiet: true });
  renderAccount();
  ensureAccountPolling();
  showNotice("Account created. You can now save searches.");
  clearNoticeSoon();
}

async function login() {
  const data = await postJson("/api/auth/login", authPayload());
  state.user = data.user;
  state.accountSummary = data.summary;
  els.authPassword.value = "";
  await refreshAccount({ quiet: true });
  renderAccount();
  ensureAccountPolling();
  showNotice("Signed in.");
  clearNoticeSoon();
}

async function logout() {
  await postJson("/api/auth/logout", {});
  state.user = null;
  state.accountSummary = null;
  state.savedSearches = [];
  state.selectedSearchId = null;
  state.viewingMode = "live";
  state.listings = [];
  state.accountNotifiedIds.clear();
  renderAccount();
  renderSummary({ listings: [], newCount: 0, fetched: 0, checkedAt: null });
  renderStatuses([]);
  renderListings();
  showNotice("Signed out. Anonymous search still works.");
  clearNoticeSoon();
}

function renderAccount() {
  const signedIn = Boolean(state.user);
  setHidden(els.authGuest, signedIn);
  setHidden(els.authUser, !signedIn);
  setHidden(els.topCreateAccount, signedIn);
  setHidden(els.topSignIn, signedIn);
  setHidden(els.adminPanel, !state.user?.isAdmin);
  els.accountChip.textContent = signedIn ? state.user.email : "Guest mode";
  if (!signedIn) {
    setHidden(els.accountResultTools, true);
    return;
  }
  const summary = state.accountSummary || {};
  els.accountEmail.textContent = state.user.email;
  els.accountSummary.textContent = `${summary.savedCount || 0} saved searches · ${summary.storedCount || 0} stored matches · ${summary.unseenCount || 0} unseen · ${summary.favoriteCount || 0} favorites`;
  renderSavedSearches();
  if (state.user?.isAdmin) {
    loadAdminOverview().catch(() => {});
  }
}

function renderAdminList(node, rows, renderRow) {
  node.innerHTML = "";
  if (!rows.length) {
    node.className = "admin-list empty";
    node.textContent = "No data yet.";
    return;
  }
  node.className = "admin-list";
  for (const row of rows) {
    const item = document.createElement("div");
    item.className = "admin-row";
    item.innerHTML = renderRow(row);
    node.append(item);
  }
}

async function loadAdminOverview() {
  if (!state.user?.isAdmin) return;
  const data = await getJson("/api/admin/overview");
  els.adminStats.innerHTML = "";
  const stats = [
    ["Users", data.counts.users],
    ["Saved searches", data.counts.savedSearches],
    ["Active watches", data.counts.activeSearches],
    ["Stored matches", data.counts.storedMatches],
    ["Listings", data.counts.listings],
  ];
  for (const [label, value] of stats) {
    const card = document.createElement("div");
    card.className = "admin-stat";
    card.innerHTML = `<strong>${formatNumber(value)}</strong><span>${label}</span>`;
    els.adminStats.append(card);
  }
  renderAdminList(els.adminUsers, data.users || [], (user) => `
    <strong>${user.email}${user.isAdmin ? " · admin" : ""}</strong>
    <span>${user.savedCount} searches · ${user.matchCount} matches · joined ${formatTime(user.createdAt)}</span>
  `);
  renderAdminList(els.adminSearches, data.searches || [], (search) => `
    <strong>${search.name}</strong>
    <span>${search.email} · ${search.storedCount} stored · ${search.isActive ? "active" : "paused"} · last ${formatTime(search.lastChecked)}</span>
  `);
  renderAdminList(els.adminSources, data.sources || [], (source) => `
    <strong>${source.sourceLabel}</strong>
    <span>${source.count} listings · last seen ${formatTime(source.lastSeen)}</span>
  `);
}

function renderSavedSearches() {
  els.savedSearches.innerHTML = "";
  if (!state.savedSearches.length) {
    els.savedSearches.className = "saved-search-list empty";
    els.savedSearches.textContent = "No saved searches yet.";
    return;
  }
  els.savedSearches.className = "saved-search-list";
  for (const search of state.savedSearches) {
    const card = document.createElement("article");
    card.className = `saved-search${search.id === state.selectedSearchId ? " selected" : ""}`;

    const title = document.createElement("strong");
    title.textContent = search.name;
    const detail = document.createElement("span");
    detail.textContent = filterSummary(search.filters);
    const counts = document.createElement("span");
    counts.textContent = `${search.storedCount || 0} stored · ${search.unseenCount || 0} unseen · ${search.isActive ? `watching every ${search.intervalSeconds}s` : "paused"} · last ${formatTime(search.lastChecked)}`;

    const actions = document.createElement("div");
    actions.className = "saved-actions";
    const buttons = [
      ["View", () => loadSavedSearchResults(search.id)],
      ["Run now", () => runSavedSearch(search.id)],
      [search.isActive ? "Pause" : "Watch", () => updateSavedSearch(search.id, { isActive: !search.isActive })],
      [search.notificationsEnabled ? "Notifications on" : "Notifications off", () => updateSavedSearch(search.id, { notificationsEnabled: !search.notificationsEnabled })],
      ["Use filters", () => applyFilters(search.filters)],
      ["Delete", () => deleteSavedSearch(search.id), "danger"],
    ];
    for (const [label, handler, kind] of buttons) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      if (kind) button.className = kind;
      button.addEventListener("click", () => handler().catch((error) => showNotice(error.message, true)));
      actions.append(button);
    }

    card.append(title, detail, counts, actions);
    els.savedSearches.append(card);
  }
}

async function refreshAccount({ quiet = false } = {}) {
  if (!state.user) return;
  const data = await getJson("/api/account/searches");
  state.savedSearches = data.searches || [];
  state.accountSummary = data.summary;
  renderAccount();
  if (!quiet && state.selectedSearchId) {
    await loadSavedSearchResults(state.selectedSearchId);
  }
}

function defaultSearchName() {
  const filters = buildFilters();
  const base = `${cityName(filters.city)} ${typeName(filters.propertyType)}`;
  const rent = filters.maxRent ? ` under ${filters.maxRent}` : "";
  return `${base}${rent}`.trim();
}

async function saveCurrentSearch() {
  if (!state.user) {
    showNotice("Create an account or sign in to save searches.", true);
    return;
  }
  const filters = buildFilters();
  if (!filters.sources.length) {
    showNotice("Pick at least one source.", true);
    return;
  }
  const seconds = Math.max(30, Math.min(3600, Number(els.pollSeconds.value) || 30));
  const data = await postJson("/api/account/searches", {
    name: els.saveSearchName.value.trim() || defaultSearchName(),
    filters,
    intervalSeconds: seconds,
    notificationsEnabled: els.accountNotificationsEnabled.checked,
  });
  state.savedSearches = [data.search, ...state.savedSearches.filter((item) => item.id !== data.search.id)];
  state.accountSummary = data.summary;
  renderAccount();
  await runSavedSearch(data.search.id);
  showNotice("Saved search created and initial results stored.");
  clearNoticeSoon();
}

async function updateSavedSearch(id, updates) {
  const data = await postJson("/api/account/searches/update", { id, ...updates });
  state.savedSearches = state.savedSearches.map((search) => (search.id === id ? data.search : search));
  state.accountSummary = data.summary;
  renderAccount();
}

async function deleteSavedSearch(id) {
  await postJson("/api/account/searches/delete", { id });
  state.savedSearches = state.savedSearches.filter((search) => search.id !== id);
  if (state.selectedSearchId === id) {
    state.selectedSearchId = null;
    state.viewingMode = "live";
    state.listings = [];
    renderSummary({ listings: [], newCount: 0, fetched: 0, checkedAt: null });
    renderStatuses([]);
    renderListings();
  }
  await refreshAccount({ quiet: true });
  showNotice("Saved search deleted.");
  clearNoticeSoon();
}

async function runSavedSearch(id) {
  const data = await postJson("/api/account/searches/run", { id });
  await refreshAccount({ quiet: true });
  await loadSavedSearchResults(id);
  showNotice(data.accountNewCount ? `${data.accountNewCount} new account match(es) stored.` : "Saved search refreshed. No new stored matches.");
  clearNoticeSoon();
}

async function loadSavedSearchResults(id) {
  const data = await getJson(`/api/account/search-results?searchId=${encodeURIComponent(id)}`);
  state.viewingMode = "account";
  state.selectedSearchId = id;
  state.listings = data.results || [];
  renderStatuses([]);
  renderSavedSearches();
  updateStoredView();
}

async function refreshAccountNotifications() {
  if (!state.user) return;
  const data = await getJson("/api/account/notifications");
  notifyAccountItems(data.items || []);
}

async function init() {
  const response = await fetch("/api/config");
  populateConfig(await response.json());
  els.country.addEventListener("change", renderCountryOptions);
  els.city.addEventListener("change", updateCityNote);
  els.checkNow.addEventListener("click", () => checkNow({ manual: true }));
  els.startWatch.addEventListener("click", startWatching);
  els.stopWatch.addEventListener("click", stopWatching);
  els.enableNotifications.addEventListener("click", enableNotifications);
  els.markSeen.addEventListener("click", markAllSeen);
  els.sortMode.addEventListener("change", renderListings);
  els.topCreateAccount.addEventListener("click", () => openAuth("register"));
  els.topSignIn.addEventListener("click", () => openAuth("login"));
  els.introCreateAccount.addEventListener("click", () => openAuth("register"));
  els.introSignIn.addEventListener("click", () => openAuth("login"));
  els.loginButton.addEventListener("click", () => login().catch((error) => showNotice(error.message, true)));
  els.registerButton.addEventListener("click", () => register().catch((error) => showNotice(error.message, true)));
  els.authPassword.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const action = state.authMode === "login" ? login : register;
    action().catch((error) => showNotice(error.message, true));
  });
  els.logoutButton.addEventListener("click", () => logout().catch((error) => showNotice(error.message, true)));
  els.saveSearch.addEventListener("click", () => saveCurrentSearch().catch((error) => showNotice(error.message, true)));
  els.accountStatusFilter.addEventListener("change", updateStoredView);
  els.accountFavoritesOnly.addEventListener("change", updateStoredView);
  els.accountShowHidden.addEventListener("change", updateStoredView);
  els.exportResults.addEventListener("click", exportVisibleResults);
  els.copyDigest.addEventListener("click", () => copyVisibleDigest().catch((error) => showNotice(error.message, true)));
  els.refreshAdmin.addEventListener("click", () => loadAdminOverview().catch((error) => showNotice(error.message, true)));
  ensureStatusPolling();
  await loadMe();
  await refreshWatchStatus({ notify: false });
}

init().catch((error) => showNotice(error.message, true));
