/* ============================================================
   Clash Royale Deck Builder — Frontend JS
   ============================================================ */

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  allCards: [],        // [{name, elixirCost, rarity, maxLevel}]
  collection: [],      // active profile's cards [{name, level, maxLevel}]
  profiles: [],        // [{id, player_tag, player_name, trophies, arena, last_synced}]
  activeProfileId: null,
  deckIds: [],         // rec deck IDs from the last analysis stream
  savedDecks: [],      // [{id, name, source, cards, created_at, updated_at}]
  collectionSort: { field: 'level', dir: 'desc' },

  // Deck builder modal
  builder: {
    editingId: null,
    slots: Array(8).fill(null),
    activeSlot: null,
  },

  // Saved deck detail modal
  detail: {
    deckId: null,
    deckData: null,
    analysis: null,
    chatStreaming: false,
    analysisStreaming: false,
  },

  // Recommendation chat
  recChat: {
    deckId: null,
    deckData: null,
    streaming: false,
  },

  // Recommendation options
  recOptions: {
    numDecks: 1,
    strategies: [],      // selected archetype strings
    selectedCards: [],    // card name strings for custom pool
  },

  showArchived: false,
  collectionCollapsed: true,
};

// ── DOM refs ───────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// Profiles
const addProfileBtn     = $("add-profile-btn");
const addProfileForm    = $("add-profile-form");
const newProfileTag     = $("new-profile-tag");
const connectProfileBtn = $("connect-profile-btn");
const cancelAddProfile  = $("cancel-add-profile");
const addProfileStatus  = $("add-profile-status");
const profilesEmpty     = $("profiles-empty");
const profilesGrid      = $("profiles-grid");

// Collection
const cardGrid           = $("card-grid");
const cardCountBadge     = $("card-count");
const collectionHint     = $("collection-hint");
const collectionProfileLabel = $("collection-profile-label");

// Generate
const generateBtn    = $("generate-btn");
const resultsSection = $("results-section");
const streamStatus   = $("stream-status");
const streamMsg      = $("stream-msg");
const decksContainer = $("decks-container");
const metaContext    = $("meta-context");

// My Decks
const myDecksGrid    = $("my-decks-grid");
const myDecksEmpty   = $("my-decks-empty");
const myDecksCount   = $("my-decks-count");
const newDeckBtn     = $("new-deck-btn");

// History
const historyToggleBtn = $("history-toggle-btn");
const historyList      = $("history-list");
const historyLoading   = $("history-loading");
const historyEmpty     = $("history-empty");
const historyItems     = $("history-items");

// Deck Builder Modal
const deckBuilderModal  = $("deck-builder-modal");
const deckBuilderBdrop  = $("deck-builder-backdrop");
const deckBuilderTitle  = $("deck-builder-title");
const deckBuilderClose  = $("deck-builder-close");
const deckBuilderCancel = $("deck-builder-cancel");
const deckBuilderSave   = $("deck-builder-save");
const deckNameInput     = $("deck-name-input");
const cardSlotsEl       = $("card-slots");
const slotCountLabel    = $("slot-count-label");
const deckBuilderError  = $("deck-builder-error");

// Slot picker
const slotPickerDropdown = $("slot-picker-dropdown");
const slotPickerSearch   = $("slot-picker-search");
const slotPickerList     = $("slot-picker-list");

// Saved Deck Detail Modal
const deckDetailModal   = $("deck-detail-modal");
const detailBackdrop    = $("detail-backdrop");
const detailDeckName    = $("detail-deck-name");
const detailSourceLabel = $("detail-source-label");
const detailMetaTags    = $("detail-meta-tags");
const detailEditBtn     = $("detail-edit-btn");
const detailDeleteBtn   = $("detail-delete-btn");
const detailCloseBtn    = $("detail-close-btn");
const detailStaleWarn   = $("detail-stale-warning");
const detailUpdateLvls  = $("detail-update-levels-btn");
const detailReanalyze   = $("detail-reanalyze-btn");
const detailCardsDisp   = $("detail-cards-display");
const analysisEmpty     = $("analysis-empty");
const analysisLoading   = $("analysis-loading");
const analysisResult    = $("analysis-result");
const analysisStatusMsg = $("analysis-status-msg");
const runAnalysisBtn    = $("run-analysis-btn");
const detailChatMsgs    = $("detail-chat-messages");
const detailChatInput   = $("detail-chat-input");
const detailChatSend    = $("detail-chat-send");

// Rec Chat Modal
const chatModal         = $("chat-modal");
const chatBackdrop      = $("chat-backdrop");
const chatCloseBtn      = $("chat-close-btn");
const chatDeckTitle     = $("chat-deck-title");
const chatPanelContext  = $("chat-panel-context");
const chatMessages      = $("chat-messages");
const chatInput         = $("chat-input");
const chatSendBtn       = $("chat-send-btn");

// Token usage bars
const recTokenUsage       = $("rec-token-usage");
const analysisTokenUsage  = $("analysis-token-usage");
const detailChatTokenFooter = $("detail-chat-token-footer");
const recChatTokenFooter  = $("rec-chat-token-footer");


// Archive
const showArchivedBtn   = $("show-archived-btn");

// Recommendation Options
const recOptionsToggle  = $("rec-options-toggle");
const recOptionsPanel   = $("rec-options-panel");
const recNumMinus       = $("rec-num-minus");
const recNumPlus        = $("rec-num-plus");
const recNumValue       = $("rec-num-value");
const strategyChipsEl   = $("strategy-chips");
const cardPoolClear     = $("card-pool-clear");
const cardPoolGrid      = $("card-pool-grid");
const cardPoolCount     = $("card-pool-count");
const collectionToggleBtn = $("collection-toggle-btn");
const collectionExpandRow = $("collection-expand-row");

// ── Init ───────────────────────────────────────────────────────────────────
async function init() {
  await Promise.all([loadAllCards(), loadProfiles(), checkCRStatus()]);
  bindEvents();
}

async function checkCRStatus() {
  try {
    const res = await fetch("/api/cr-status");
    const data = await res.json();
    if (!data.available) {
      showCRStatusBanner(data.message);
    }
  } catch { /* ignore — server not ready yet */ }
}

function showCRStatusBanner(message) {
  const banner = document.createElement("div");
  banner.id = "cr-status-banner";
  banner.className = "cr-status-banner";
  banner.innerHTML = `
    <span class="cr-status-icon">ℹ</span>
    <span class="cr-status-msg">${escapeHtml(message)}</span>
    <button class="cr-status-dismiss" title="Dismiss">✕</button>
  `;
  banner.querySelector(".cr-status-dismiss").addEventListener("click", () => banner.remove());
  // Insert after the header, before main
  const main = document.querySelector("main");
  if (main) main.prepend(banner);
}

async function loadAllCards() {
  try {
    const res = await fetch("/api/all-cards");
    const data = await res.json();
    state.allCards = data.cards || [];
  } catch { /* ignore */ }
}


// ── Event Bindings ─────────────────────────────────────────────────────────
function bindEvents() {
  // Profile section
  addProfileBtn.addEventListener("click", () => {
    addProfileForm.classList.remove("hidden");
    addProfileBtn.classList.add("hidden");
    addProfileStatus.classList.add("hidden");
    newProfileTag.focus();
  });
  cancelAddProfile.addEventListener("click", () => {
    addProfileForm.classList.add("hidden");
    addProfileBtn.classList.remove("hidden");
    newProfileTag.value = "";
    addProfileStatus.classList.add("hidden");
  });
  connectProfileBtn.addEventListener("click", () => addProfile(newProfileTag.value.trim()));
  newProfileTag.addEventListener("keydown", e => {
    if (e.key === "Enter") addProfile(newProfileTag.value.trim());
    if (e.key === "Escape") cancelAddProfile.click();
  });

  // Sort buttons
  document.querySelectorAll(".sort-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const field = btn.dataset.sort;
      if (state.collectionSort.field === field) {
        state.collectionSort.dir = state.collectionSort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        state.collectionSort.field = field;
        state.collectionSort.dir = field === 'level' ? 'desc' : 'asc';
      }
      updateSortButtons();
      renderCollection();
    });
  });

  // Close slot picker on outside click
  document.addEventListener("click", (e) => {
    if (!slotPickerDropdown.contains(e.target)) hideSlotPicker();
  });

  // Generate
  generateBtn.addEventListener("click", generateDecks);

  // Recommendation options
  recOptionsToggle.addEventListener("click", () => {
    recOptionsPanel.classList.toggle("hidden");
    recOptionsToggle.textContent = recOptionsPanel.classList.contains("hidden")
      ? "Customize Recommendations" : "Hide Options";
    if (!recOptionsPanel.classList.contains("hidden")) renderCardPoolGrid();
  });
  recNumMinus.addEventListener("click", () => {
    state.recOptions.numDecks = Math.max(1, state.recOptions.numDecks - 1);
    recNumValue.textContent = state.recOptions.numDecks;
  });
  recNumPlus.addEventListener("click", () => {
    state.recOptions.numDecks = Math.min(10, state.recOptions.numDecks + 1);
    recNumValue.textContent = state.recOptions.numDecks;
  });
  strategyChipsEl.addEventListener("click", (e) => {
    const chip = e.target.closest(".strategy-chip");
    if (!chip) return;
    const strat = chip.dataset.strategy;
    chip.classList.toggle("active");
    if (chip.classList.contains("active")) {
      if (!state.recOptions.strategies.includes(strat)) state.recOptions.strategies.push(strat);
    } else {
      state.recOptions.strategies = state.recOptions.strategies.filter(s => s !== strat);
    }
  });
  cardPoolClear.addEventListener("click", () => {
    state.recOptions.selectedCards = [];
    renderCardPoolGrid();
  });
  if (collectionToggleBtn) {
    collectionToggleBtn.addEventListener("click", () => {
      state.collectionCollapsed = !state.collectionCollapsed;
      renderCollection();
    });
  }

  // My Decks
  newDeckBtn.addEventListener("click", () => openDeckBuilder(null));
  showArchivedBtn.addEventListener("click", () => {
    state.showArchived = !state.showArchived;
    showArchivedBtn.textContent = state.showArchived ? "Hide Archived" : "Show Archived";
    loadSavedDecks();
  });

  // History
  historyToggleBtn.addEventListener("click", toggleHistory);

  // Deck Builder Modal
  deckBuilderBdrop.addEventListener("click", closeDeckBuilder);
  deckBuilderClose.addEventListener("click", closeDeckBuilder);
  deckBuilderCancel.addEventListener("click", closeDeckBuilder);
  deckBuilderSave.addEventListener("click", saveDeckFromBuilder);
  slotPickerSearch.addEventListener("input", renderSlotPickerList);
  slotPickerSearch.addEventListener("keydown", onSlotPickerKeydown);

  // Detail modal
  detailBackdrop.addEventListener("click", closeDetailModal);
  detailCloseBtn.addEventListener("click", closeDetailModal);
  detailEditBtn.addEventListener("click", () => {
    closeDetailModal();
    openDeckBuilder(state.detail.deckId);
  });
  detailDeleteBtn.addEventListener("click", deleteSavedDeck);
  runAnalysisBtn.addEventListener("click", runDeckAnalysis);
  detailUpdateLvls.addEventListener("click", updateDeckLevels);
  detailReanalyze.addEventListener("click", () => {
    detailStaleWarn.classList.add("hidden");
    runDeckAnalysis();
  });
  detailChatSend.addEventListener("click", sendDetailChatMessage);
  detailChatInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendDetailChatMessage(); }
  });
  document.querySelectorAll(".detail-suggestion").forEach(btn => {
    btn.addEventListener("click", () => { detailChatInput.value = btn.dataset.q; detailChatInput.focus(); });
  });

  // Rec Chat Modal
  chatBackdrop.addEventListener("click", closeRecChat);
  chatCloseBtn.addEventListener("click", closeRecChat);
  chatSendBtn.addEventListener("click", sendRecChatMessage);
  chatInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendRecChatMessage(); }
  });
  document.querySelectorAll("#chat-modal .chat-suggestion").forEach(btn => {
    btn.addEventListener("click", () => { chatInput.value = btn.dataset.q; chatInput.focus(); });
  });

  // Global escape
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      if (!deckDetailModal.classList.contains("hidden")) closeDetailModal();
      else if (!chatModal.classList.contains("hidden")) closeRecChat();
      else if (!deckBuilderModal.classList.contains("hidden")) closeDeckBuilder();
    }
  });
}


// ══════════════════════════════════════════════════════════════════════════
// PROFILES
// ══════════════════════════════════════════════════════════════════════════

async function loadProfiles() {
  try {
    const res = await fetch("/api/profiles");
    const data = await res.json();
    state.profiles = data.profiles || [];

    const savedId = parseInt(localStorage.getItem("clash_active_profile") || "0");
    const exists = savedId && state.profiles.some(p => p.id === savedId);
    const targetId = exists ? savedId : (state.profiles[0]?.id ?? null);

    if (targetId) {
      await activateProfile(targetId);
    } else {
      renderProfiles();
      renderCollection();
      await loadSavedDecks();
    }
  } catch { /* ignore */ }
}

async function activateProfile(profileId) {
  state.activeProfileId = profileId;
  localStorage.setItem("clash_active_profile", profileId);

  try {
    const res = await fetch(`/api/profiles/${profileId}`);
    const data = await res.json();
    if (data.profile) {
      state.collection = data.profile.collection || [];
    }
  } catch { /* ignore */ }

  renderProfiles();
  renderCollection();
  historyLoaded = false;
  await loadSavedDecks();
}

async function addProfile(tag) {
  if (!tag) { newProfileTag.focus(); return; }

  addProfileStatus.textContent = "Connecting to Clash Royale API...";
  addProfileStatus.className = "status-msg loading";
  addProfileStatus.classList.remove("hidden");
  connectProfileBtn.disabled = true;

  try {
    const res = await fetch("/api/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_tag: tag }),
    });
    const data = await res.json();
    if (data.error) {
      addProfileStatus.textContent = `Error: ${data.error}`;
      addProfileStatus.className = "status-msg error";
      return;
    }

    // Re-fetch full profile list, then activate the new one
    const listRes = await fetch("/api/profiles");
    const listData = await listRes.json();
    state.profiles = listData.profiles || [];

    addProfileForm.classList.add("hidden");
    addProfileBtn.classList.remove("hidden");
    newProfileTag.value = "";
    addProfileStatus.classList.add("hidden");

    await activateProfile(data.profile.id);
  } catch (err) {
    addProfileStatus.textContent = `Network error: ${err.message}`;
    addProfileStatus.className = "status-msg error";
  } finally {
    connectProfileBtn.disabled = false;
  }
}

async function syncProfile(profileId) {
  const btns = profilesGrid.querySelectorAll(`.profile-sync-btn[data-id="${profileId}"]`);
  btns.forEach(b => { b.disabled = true; b.textContent = "Syncing…"; });

  try {
    const res = await fetch(`/api/profiles/${profileId}/sync`, { method: "POST" });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }

    // Update stored profile metadata
    const idx = state.profiles.findIndex(p => p.id === profileId);
    if (idx !== -1) {
      state.profiles[idx] = {
        ...state.profiles[idx],
        player_name: data.profile.player_name,
        trophies: data.profile.trophies,
        arena: data.profile.arena,
        last_synced: data.profile.last_synced,
      };
    }

    // If active, update collection
    if (profileId === state.activeProfileId) {
      state.collection = data.profile.collection || [];
      renderCollection();
      renderMyDecks();
    }
    renderProfiles();
  } catch (err) {
    alert(`Sync failed: ${err.message}`);
  } finally {
    btns.forEach(b => { b.disabled = false; b.textContent = "↻ Sync"; });
  }
}

async function deleteProfile(profileId) {
  const profile = state.profiles.find(p => p.id === profileId);
  if (!profile) return;
  if (!confirm(`Delete profile for ${profile.player_name || profile.player_tag}?\nThis will also remove their saved decks.`)) return;

  try {
    await fetch(`/api/profiles/${profileId}`, { method: "DELETE" });
    state.profiles = state.profiles.filter(p => p.id !== profileId);

    if (state.activeProfileId === profileId) {
      state.activeProfileId = null;
      state.collection = [];
      localStorage.removeItem("clash_active_profile");

      if (state.profiles.length > 0) {
        await activateProfile(state.profiles[0].id);
      } else {
        renderProfiles();
        renderCollection();
        await loadSavedDecks();
      }
    } else {
      renderProfiles();
    }
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
  }
}

function renderProfiles() {
  profilesGrid.innerHTML = "";

  if (!state.profiles.length) {
    profilesEmpty.style.display = "";
    return;
  }
  profilesEmpty.style.display = "none";

  state.profiles.forEach(profile => {
    const isActive = profile.id === state.activeProfileId;
    const card = document.createElement("div");
    card.className = `profile-card${isActive ? " active" : ""}`;

    const syncTime = profile.last_synced
      ? new Date(profile.last_synced + "Z").toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
      : "Never";

    card.innerHTML = `
      <div class="profile-card-body">
        <div class="profile-name">${escapeHtml(profile.player_name || "Unknown")}</div>
        <div class="profile-tag">${escapeHtml(profile.player_tag)}</div>
        <div class="profile-stats">🏆 ${(profile.trophies || 0).toLocaleString()} · ${escapeHtml(profile.arena || "—")}</div>
        <div class="profile-sync-time">Synced: ${syncTime}</div>
      </div>
      <div class="profile-card-actions">
        ${isActive
          ? '<span class="profile-active-badge">✓ Active</span>'
          : `<button class="btn btn-primary btn-sm profile-select-btn" data-id="${profile.id}">Select</button>`}
        <button class="btn btn-ghost btn-sm profile-sync-btn" data-id="${profile.id}">↻ Sync</button>
        <button class="btn btn-ghost btn-sm btn-danger-ghost profile-delete-btn" data-id="${profile.id}">Delete</button>
      </div>
    `;

    if (!isActive) {
      card.querySelector(".profile-select-btn").addEventListener("click", () => activateProfile(profile.id));
    }
    card.querySelector(".profile-sync-btn").addEventListener("click", () => syncProfile(profile.id));
    card.querySelector(".profile-delete-btn").addEventListener("click", () => deleteProfile(profile.id));

    profilesGrid.appendChild(card);
  });
}


// ══════════════════════════════════════════════════════════════════════════
// COLLECTION (read-only — populated from active profile)
// ══════════════════════════════════════════════════════════════════════════

const RARITY_ORDER = { common: 0, rare: 1, epic: 2, legendary: 3, champion: 4 };

function getSortedCollection() {
  const { field, dir } = state.collectionSort;
  const mult = dir === 'asc' ? 1 : -1;
  return [...state.collection].sort((a, b) => {
    let va, vb;
    if (field === 'rarity') {
      const ca = state.allCards.find(c => c.name === a.name);
      const cb = state.allCards.find(c => c.name === b.name);
      va = RARITY_ORDER[(ca?.rarity || '').toLowerCase()] ?? 0;
      vb = RARITY_ORDER[(cb?.rarity || '').toLowerCase()] ?? 0;
    } else if (field === 'elixir') {
      const ca = state.allCards.find(c => c.name === a.name);
      const cb = state.allCards.find(c => c.name === b.name);
      va = ca?.elixirCost ?? 0;
      vb = cb?.elixirCost ?? 0;
    } else {
      va = a.level; vb = b.level;
    }
    return mult * (va - vb) || a.name.localeCompare(b.name);
  });
}

function updateSortButtons() {
  document.querySelectorAll(".sort-btn").forEach(btn => {
    const active = btn.dataset.sort === state.collectionSort.field;
    btn.classList.toggle("active", active);
    const label = btn.dataset.sort.charAt(0).toUpperCase() + btn.dataset.sort.slice(1);
    btn.textContent = active ? `${label} ${state.collectionSort.dir === 'asc' ? '▲' : '▼'}` : label;
  });
}

const COLLECTION_PREVIEW = 24; // cards shown when collapsed

function renderCollection() {
  cardGrid.innerHTML = "";

  const profile = state.profiles.find(p => p.id === state.activeProfileId);
  if (collectionProfileLabel) {
    collectionProfileLabel.textContent = profile
      ? `${escapeHtml(profile.player_name)} (${escapeHtml(profile.player_tag)})`
      : "";
  }

  if (!state.collection.length) {
    cardCountBadge.textContent = "0 cards";
    collectionHint.style.display = "";
    if (collectionExpandRow) collectionExpandRow.classList.add("hidden");
    generateBtn.disabled = true;
    return;
  }

  const sorted = getSortedCollection();
  const visible = state.collectionCollapsed ? sorted.slice(0, COLLECTION_PREVIEW) : sorted;

  visible.forEach(card => {
    const chip = document.createElement("div");
    chip.className = "card-chip";
    chip.innerHTML = `<span class="chip-level">${card.level}</span><span class="chip-name">${escapeHtml(card.name)}</span>`;
    cardGrid.appendChild(chip);
  });

  const count = state.collection.length;
  cardCountBadge.textContent = `${count} card${count !== 1 ? "s" : ""}`;
  collectionHint.style.display = "none";
  generateBtn.disabled = count < 8;

  if (collectionExpandRow) {
    if (count > COLLECTION_PREVIEW) {
      collectionExpandRow.classList.remove("hidden");
      const hidden = count - COLLECTION_PREVIEW;
      if (collectionToggleBtn) {
        collectionToggleBtn.textContent = state.collectionCollapsed
          ? `Show all ${count} cards (${hidden} more) ▼`
          : "Show fewer ▲";
      }
    } else {
      collectionExpandRow.classList.add("hidden");
    }
  }
}


// ══════════════════════════════════════════════════════════════════════════
// MY DECKS
// ══════════════════════════════════════════════════════════════════════════

async function loadSavedDecks() {
  try {
    let url = state.activeProfileId
      ? `/api/saved-decks?profile_id=${state.activeProfileId}`
      : "/api/saved-decks";
    if (state.showArchived) url += (url.includes("?") ? "&" : "?") + "include_archived=true";
    const res = await fetch(url);
    const data = await res.json();
    state.savedDecks = data.decks || [];
    renderMyDecks();
  } catch { /* ignore */ }
}

function renderMyDecks() {
  myDecksGrid.innerHTML = "";
  if (!state.savedDecks.length) {
    myDecksEmpty.style.display = "";
    myDecksCount.textContent = "0";
    return;
  }
  myDecksEmpty.style.display = "none";
  myDecksCount.textContent = state.savedDecks.length;

  state.savedDecks.forEach(deck => {
    const stale = isDeckStale(deck);
    const el = document.createElement("div");
    el.className = `my-deck-card${stale ? " is-stale" : ""}`;

    const winCards = getWinCards(deck);
    const chipHtml = (deck.cards || []).map(c => {
      const isWin = winCards.has(c.name.toLowerCase());
      return `<span class="mini-chip${isWin ? " win-con" : ""}">${escapeHtml(c.name)}</span>`;
    }).join("");

    const sourceLbl = deck.source === "recommendation" ? "💡 Saved from AI"
                    : deck.source === "api"            ? "📱 Imported from game"
                    : "🔧 Manual build";

    const isArchived = deck.archived;
    el.innerHTML = `
      <div class="my-deck-card-header">
        <div>
          <div class="my-deck-card-title">${escapeHtml(deck.name)}</div>
          <div class="my-deck-card-source">${sourceLbl}</div>
        </div>
        ${isArchived ? '<span class="tag tag-archived">Archived</span>' : ""}
        ${stale && !isArchived ? '<span class="tag tag-stale">Levels Updated</span>' : ""}
      </div>
      <div class="my-deck-card-chips">${chipHtml}</div>
      <div class="my-deck-card-footer">
        <button class="btn btn-primary btn-sm open-saved-deck-btn">Open & Analyze</button>
        <button class="btn btn-ghost btn-sm edit-saved-deck-btn">Edit</button>
        <button class="btn btn-ghost btn-sm archive-deck-btn">${isArchived ? "Restore" : "Archive"}</button>
      </div>
    `;
    el.querySelector(".open-saved-deck-btn").addEventListener("click", () => openDetailModal(deck.id));
    el.querySelector(".edit-saved-deck-btn").addEventListener("click", () => openDeckBuilder(deck.id));
    el.querySelector(".archive-deck-btn").addEventListener("click", async () => {
      await fetch(`/api/saved-decks/${deck.id}/archive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ archived: !isArchived }),
      });
      await loadSavedDecks();
    });
    myDecksGrid.appendChild(el);
  });
}

/** A saved deck is stale if any of its card levels differ from current collection */
function isDeckStale(deck) {
  if (!state.collection.length) return false;
  return (deck.cards || []).some(dc => {
    const cur = state.collection.find(c => c.name.toLowerCase() === dc.name.toLowerCase());
    return cur && cur.level !== dc.level;
  });
}

/** Pull win condition card names from a deck */
function getWinCards(deck) {
  const wc = (deck.win_condition || "").toLowerCase();
  return new Set((deck.cards || []).map(c => c.name.toLowerCase()).filter(n => wc.includes(n)));
}


// ══════════════════════════════════════════════════════════════════════════
// DECK BUILDER MODAL
// ══════════════════════════════════════════════════════════════════════════

function openDeckBuilder(editId = null) {
  state.builder.editingId = editId;

  if (editId) {
    const deck = state.savedDecks.find(d => d.id === editId);
    if (!deck) return;
    deckBuilderTitle.textContent = "Edit Deck";
    deckNameInput.value = deck.name;
    state.builder.slots = (deck.cards || []).map(c => ({ ...c }));
    while (state.builder.slots.length < 8) state.builder.slots.push(null);
  } else {
    deckBuilderTitle.textContent = "Build a Deck";
    deckNameInput.value = "";
    state.builder.slots = Array(8).fill(null);
  }

  deckBuilderError.classList.add("hidden");
  renderSlots();
  deckBuilderModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  setTimeout(() => deckNameInput.focus(), 100);
}

function closeDeckBuilder() {
  deckBuilderModal.classList.add("hidden");
  document.body.style.overflow = "";
  hideSlotPicker();
  state.builder.activeSlot = null;
}

function renderSlots() {
  cardSlotsEl.innerHTML = "";
  const filled = state.builder.slots.filter(Boolean).length;
  slotCountLabel.textContent = `(${filled} / 8)`;
  deckBuilderSave.disabled = filled < 8 || !deckNameInput.value.trim();

  state.builder.slots.forEach((card, i) => {
    const slot = document.createElement("div");
    slot.className = `card-slot${card ? " filled" : ""}${state.builder.activeSlot === i ? " is-picking" : ""}`;
    slot.dataset.idx = i;

    if (card) {
      slot.innerHTML = `
        <span class="card-slot-name">${escapeHtml(card.name)}</span>
        <span class="card-slot-level">Lvl ${card.level}</span>
        <button class="card-slot-remove" data-idx="${i}" title="Remove">&times;</button>
      `;
      slot.querySelector(".card-slot-remove").addEventListener("click", e => {
        e.stopPropagation();
        state.builder.slots[i] = null;
        renderSlots();
      });
    } else {
      slot.innerHTML = `<span class="card-slot-placeholder">+ Pick a card</span>`;
    }

    slot.addEventListener("click", e => {
      if (e.target.classList.contains("card-slot-remove")) return;
      e.stopPropagation();
      toggleSlotPicker(i, slot);
    });

    cardSlotsEl.appendChild(slot);
  });

  deckNameInput.onkeyup = () => {
    const filled = state.builder.slots.filter(Boolean).length;
    deckBuilderSave.disabled = filled < 8 || !deckNameInput.value.trim();
  };
}

function toggleSlotPicker(slotIdx, slotEl) {
  if (state.builder.activeSlot === slotIdx) {
    hideSlotPicker();
    return;
  }
  state.builder.activeSlot = slotIdx;
  renderSlots();

  const rect = slotEl.getBoundingClientRect();
  slotPickerDropdown.style.top = `${rect.bottom + 4}px`;
  slotPickerDropdown.style.left = `${rect.left}px`;
  slotPickerDropdown.classList.remove("hidden");
  slotPickerSearch.value = "";
  renderSlotPickerList();
  setTimeout(() => slotPickerSearch.focus(), 50);
}

function hideSlotPicker() {
  slotPickerDropdown.classList.add("hidden");
  if (state.builder.activeSlot !== null) {
    state.builder.activeSlot = null;
    renderSlots();
  }
}

function renderSlotPickerList() {
  const q = slotPickerSearch.value.trim().toLowerCase();
  const inDeck = new Set(state.builder.slots.filter(Boolean).map(c => c.name.toLowerCase()));
  const cards = state.collection.filter(c => !q || c.name.toLowerCase().includes(q));

  slotPickerList.innerHTML = "";
  if (!cards.length) {
    slotPickerList.innerHTML = '<li style="color:var(--text-muted);cursor:default">No cards match</li>';
    return;
  }

  cards.forEach(card => {
    const inUse = inDeck.has(card.name.toLowerCase());
    const li = document.createElement("li");
    li.className = inUse ? "in-deck" : "";
    li.innerHTML = `
      <span>${escapeHtml(card.name)}</span>
      <span class="slot-picker-level">Lvl ${card.level}</span>
    `;
    if (!inUse) {
      li.addEventListener("click", () => {
        state.builder.slots[state.builder.activeSlot] = { name: card.name, level: card.level, maxLevel: card.maxLevel };
        hideSlotPicker();
        renderSlots();
      });
    }
    slotPickerList.appendChild(li);
  });
}

let slotPickerFocusIdx = -1;
function onSlotPickerKeydown(e) {
  const items = [...slotPickerList.querySelectorAll("li:not(.in-deck)")];
  if (e.key === "ArrowDown") { e.preventDefault(); slotPickerFocusIdx = Math.min(slotPickerFocusIdx + 1, items.length - 1); items.forEach((li, i) => li.classList.toggle("focused", i === slotPickerFocusIdx)); }
  else if (e.key === "ArrowUp") { e.preventDefault(); slotPickerFocusIdx = Math.max(slotPickerFocusIdx - 1, 0); items.forEach((li, i) => li.classList.toggle("focused", i === slotPickerFocusIdx)); }
  else if (e.key === "Enter" && slotPickerFocusIdx >= 0 && items[slotPickerFocusIdx]) { items[slotPickerFocusIdx].click(); }
  else if (e.key === "Escape") { hideSlotPicker(); }
}

async function saveDeckFromBuilder() {
  const name = deckNameInput.value.trim();
  if (!name) { showBuilderError("Please enter a deck name."); return; }

  const cards = state.builder.slots.filter(Boolean);
  if (cards.length !== 8) { showBuilderError("You must fill all 8 card slots."); return; }

  const names = cards.map(c => c.name.toLowerCase());
  if (new Set(names).size !== 8) { showBuilderError("Deck contains duplicate cards."); return; }

  deckBuilderSave.disabled = true;
  deckBuilderError.classList.add("hidden");

  try {
    if (state.builder.editingId) {
      const res = await fetch(`/api/saved-decks/${state.builder.editingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, cards }),
      });
      const data = await res.json();
      if (data.error) { showBuilderError(data.error); return; }
    } else {
      const res = await fetch("/api/saved-decks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, cards, source: "manual", profile_id: state.activeProfileId }),
      });
      const data = await res.json();
      if (data.error) { showBuilderError(data.error); return; }
    }

    await loadSavedDecks();
    closeDeckBuilder();
  } catch (err) {
    showBuilderError(`Network error: ${err.message}`);
  } finally {
    deckBuilderSave.disabled = false;
  }
}

function showBuilderError(msg) {
  deckBuilderError.textContent = msg;
  deckBuilderError.classList.remove("hidden");
}


// ══════════════════════════════════════════════════════════════════════════
// SAVED DECK DETAIL MODAL
// ══════════════════════════════════════════════════════════════════════════

async function openDetailModal(deckId) {
  const deck = state.savedDecks.find(d => d.id === deckId);
  if (!deck) return;

  state.detail.deckId = deckId;
  state.detail.deckData = deck;
  state.detail.analysis = null;

  detailDeckName.textContent = deck.name;
  detailSourceLabel.textContent = deck.source === "recommendation" ? "💡 Saved from AI recommendation"
                                : deck.source === "api"            ? "📱 Imported from game"
                                : "🔧 Manually built deck";
  detailMetaTags.innerHTML = "";

  analysisEmpty.style.display = "";
  analysisLoading.classList.remove("visible");
  analysisResult.classList.add("hidden");
  analysisResult.innerHTML = "";

  detailChatMsgs.innerHTML = `<div class="chat-welcome" id="detail-chat-welcome"><p>💬 Ask me anything about this deck — card swaps, matchups, playstyle adjustments, or how to improve your win rate.</p></div>`;

  renderDetailCards(deck);

  const stale = isDeckStale(deck);
  detailStaleWarn.classList.toggle("hidden", !stale);

  deckDetailModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";

  try {
    const [analysisRes, chatRes] = await Promise.all([
      fetch(`/api/saved-decks/${deckId}/analysis`),
      fetch(`/api/saved-decks/${deckId}/chat`),
    ]);
    const analysisData = await analysisRes.json();
    const chatData = await chatRes.json();

    if (analysisData && analysisData.analysis) {
      state.detail.analysis = analysisData.analysis;
      showAnalysisResult(analysisData.analysis, analysisData.collection_snapshot);
      updateDetailMetaTags(analysisData.analysis);
    }

    if (chatData.messages && chatData.messages.length) {
      detailChatMsgs.innerHTML = "";
      chatData.messages.forEach(m => appendDetailChatMsg(m.role, m.content, m.created_at));
    }
  } catch { /* ignore */ }
}

function closeDetailModal() {
  deckDetailModal.classList.add("hidden");
  document.body.style.overflow = "";
  state.detail.deckId = null;
  state.detail.deckData = null;
  state.detail.analysis = null;
}

function renderDetailCards(deck) {
  detailCardsDisp.innerHTML = "";
  const winCards = getWinCards(deck);

  (deck.cards || []).forEach(card => {
    const curCard = state.collection.find(c => c.name.toLowerCase() === card.name.toLowerCase());
    const levelChanged = curCard && curCard.level !== card.level;
    const isWin = winCards.has(card.name.toLowerCase());

    const chip = document.createElement("div");
    chip.className = `detail-card-chip${isWin ? " win-con" : ""}${levelChanged ? " stale-level" : ""}`;
    chip.innerHTML = `${escapeHtml(card.name)} <span class="chip-lv">${levelChanged ? `Lvl ${card.level} → ${curCard.level}` : `Lvl ${card.level}`}</span>`;
    detailCardsDisp.appendChild(chip);
  });
}

function updateDetailMetaTags(analysis) {
  detailMetaTags.innerHTML = "";
  // Handle both deep-analysis format (tier) and recommendation format (grade.overall)
  const tier = analysis.tier || analysis.grade?.overall;
  if (tier) {
    const t = document.createElement("span");
    t.className = `tag tag-tier-${tier}`;
    t.textContent = `Tier ${tier}`;
    detailMetaTags.appendChild(t);
  }
  if (analysis.archetype) {
    const a = document.createElement("span");
    a.className = "tag tag-archetype";
    a.textContent = analysis.archetype;
    detailMetaTags.appendChild(a);
  }
  if (analysis.average_elixir) {
    const e = document.createElement("span");
    e.className = "tag tag-elixir";
    e.textContent = `⚡ ${analysis.average_elixir}`;
    detailMetaTags.appendChild(e);
  }
}

async function deleteSavedDeck() {
  if (!state.detail.deckId) return;
  if (!confirm(`Delete "${state.detail.deckData?.name}"? This cannot be undone.`)) return;
  try {
    await fetch(`/api/saved-decks/${state.detail.deckId}`, { method: "DELETE" });
    closeDetailModal();
    await loadSavedDecks();
  } catch { /* ignore */ }
}

async function updateDeckLevels() {
  if (!state.detail.deckId || !state.detail.deckData) return;
  const deck = state.detail.deckData;

  const updatedCards = (deck.cards || []).map(card => {
    const cur = state.collection.find(c => c.name.toLowerCase() === card.name.toLowerCase());
    return cur ? { ...card, level: cur.level, maxLevel: cur.maxLevel } : card;
  });

  try {
    const res = await fetch(`/api/saved-decks/${state.detail.deckId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cards: updatedCards }),
    });
    const data = await res.json();
    if (data.ok) {
      state.detail.analysis = null;
      const savedId = state.detail.deckId;
      await loadSavedDecks();
      closeDetailModal();
      await openDetailModal(savedId);
    }
  } catch { /* ignore */ }
}


// ── Analysis ───────────────────────────────────────────────────────────────

async function runDeckAnalysis() {
  if (!state.detail.deckId || state.detail.analysisStreaming) return;
  if (!state.collection.length) {
    alert("Please select a player profile first so the AI can suggest swaps.");
    return;
  }

  state.detail.analysisStreaming = true;
  analysisEmpty.style.display = "none";
  analysisResult.classList.add("hidden");
  analysisResult.innerHTML = "";
  analysisLoading.classList.add("visible");
  analysisStatusMsg.textContent = "Querying wiki for card data and meta context...";

  let accumulated = "";
  try {
    const res = await fetch(`/api/saved-decks/${state.detail.deckId}/analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        collection: state.collection,
        player_tag: state.profiles.find(p => p.id === state.activeProfileId)?.player_tag ?? null,
      }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const msg = JSON.parse(line.slice(6));
          if (msg.error) { showAnalysisError(msg.error); return; }
          if (msg.status) analysisStatusMsg.textContent = msg.status;
          if (msg.chunk) { accumulated += msg.chunk; updateAnalysisStatusMsg(accumulated); }
          if (msg.done && msg.analysis) {
            state.detail.analysis = msg.analysis;
            analysisLoading.classList.remove("visible");
            showAnalysisResult(msg.analysis, state.collection);
            updateDetailMetaTags(msg.analysis);
            showTokenUsage(analysisTokenUsage, msg.usage);
            return;
          }
          if (msg.done) {
            const j0 = accumulated.indexOf("{"), j1 = accumulated.lastIndexOf("}");
            if (j0 !== -1 && j1 !== -1) {
              try {
                const parsed = JSON.parse(accumulated.slice(j0, j1 + 1));
                state.detail.analysis = parsed;
                analysisLoading.classList.remove("visible");
                showAnalysisResult(parsed, state.collection);
                updateDetailMetaTags(parsed);
                showTokenUsage(analysisTokenUsage, msg.usage);
              } catch { showAnalysisError("Could not parse analysis response."); }
            }
            return;
          }
        } catch { /* ignore */ }
      }
    }
  } catch (err) {
    showAnalysisError(`Connection error: ${err.message}`);
  } finally {
    state.detail.analysisStreaming = false;
    analysisLoading.classList.remove("visible");
  }
}

function updateAnalysisStatusMsg(text) {
  if (text.includes('"tier"')) analysisStatusMsg.textContent = "Evaluating deck strength...";
  else if (text.includes('"suggested_swaps"')) analysisStatusMsg.textContent = "Finding improvement swaps...";
  else if (text.includes('"coaching"')) analysisStatusMsg.textContent = "Writing coaching advice...";
}

function showAnalysisError(msg) {
  analysisLoading.classList.remove("visible");
  analysisEmpty.style.display = "";
  analysisEmpty.innerHTML = `<p style="color:#f85149">${escapeHtml(msg)}</p><button id="run-analysis-btn" class="btn btn-primary">Retry Analysis</button>`;
  $("run-analysis-btn").addEventListener("click", runDeckAnalysis);
}

function showAnalysisResult(a, collectionSnapshot) {
  analysisEmpty.style.display = "none";
  analysisLoading.classList.remove("visible");

  // Normalize: handle both deep-analysis schema and recommendation schema
  const tier         = a.tier || a.grade?.overall || "?";
  const tierExpl     = a.tier_explanation || a.grade?.summary || "";
  const overview     = a.meta_viability || a.description || "";
  const strategy     = a.strategy || null;  // rec schema
  const coaching     = a.coaching || null;  // deep-analysis schema

  // Strengths: prefer explicit strengths, fall back to key_synergies from rec
  const strengths    = a.strengths?.length ? a.strengths : (strategy?.key_synergies || []);
  const weaknesses   = a.weaknesses || [];

  const tierColors = { S: "tag-tier-S", A: "tag-tier-A", B: "tag-tier-B", C: "tag-tier-C", D: "tag-tier-D" };
  const tierClass  = tierColors[tier] || "tag-tier-B";

  const collectionNames = new Set((collectionSnapshot || state.collection).map(c => c.name.toLowerCase()));

  const strengthsHtml  = strengths.map(s => `<li>${escapeHtml(s)}</li>`).join("");
  const weaknessesHtml = weaknesses.map(w => `<li>${escapeHtml(w)}</li>`).join("");

  // Strategy sections (rec format only)
  const strategyHtml = strategy ? `
    <div class="analysis-section-label">Strategy</div>
    ${strategy.general  ? `<p class="strategy-para"><strong>Gameplan:</strong> ${escapeHtml(strategy.general)}</p>` : ""}
    ${strategy.offense  ? `<p class="strategy-para"><strong>Offense:</strong> ${escapeHtml(strategy.offense)}</p>` : ""}
    ${strategy.defense  ? `<p class="strategy-para"><strong>Defense:</strong> ${escapeHtml(strategy.defense)}</p>` : ""}
    ${strategy.matchup_tips?.length ? `<p class="strategy-para"><strong>Matchup Tips:</strong></p><ul>${strategy.matchup_tips.map(t => `<li>${escapeHtml(t)}</li>`).join("")}</ul>` : ""}
  ` : "";

  const swapsHtml = (a.suggested_swaps || []).map(swap => {
    const available = swap.in_collection !== false && collectionNames.has((swap.add || "").toLowerCase());
    return `
      <div class="swap-item">
        <div class="swap-cards">
          <span class="swap-remove">${escapeHtml(swap.remove || "")}</span>
          <span class="swap-arrow">→</span>
          <span class="swap-add">${escapeHtml(swap.add || "")}</span>
          <span class="${available ? "swap-available" : "swap-unavailable"}">${available ? "✓ in collection" : "✗ not in collection"}</span>
        </div>
        <div class="swap-reason">${escapeHtml(swap.reason || "")}</div>
      </div>`;
  }).join("");

  const matchups     = a.matchups || {};
  // rec uses "even", deep analysis uses "neutral"
  const matchupFav   = (matchups.favorable   || []).map(m => `<li>${escapeHtml(m)}</li>`).join("");
  const matchupUnfav = (matchups.unfavorable || []).map(m => `<li>${escapeHtml(m)}</li>`).join("");
  const matchupNeu   = (matchups.neutral || matchups.even || []).map(m => `<li>${escapeHtml(m)}</li>`).join("");

  analysisResult.innerHTML = `
    <div class="analysis-top-bar">
      <div class="tier-badge ${tierClass}">${escapeHtml(tier)}</div>
      <div>
        ${overview   ? `<div class="analysis-viability">${escapeHtml(overview)}</div>` : ""}
        ${tierExpl   ? `<div class="analysis-tier-expl">${escapeHtml(tierExpl)}</div>` : ""}
      </div>
    </div>

    ${(strengthsHtml || weaknessesHtml) ? `
    <div class="analysis-grid">
      ${strengthsHtml  ? `<div class="analysis-box strengths"><h5>Strengths</h5><ul>${strengthsHtml}</ul></div>` : ""}
      ${weaknessesHtml ? `<div class="analysis-box weaknesses"><h5>Weaknesses</h5><ul>${weaknessesHtml}</ul></div>` : ""}
    </div>` : ""}

    ${strategyHtml ? `<div class="analysis-strategy">${strategyHtml}</div>` : ""}

    ${swapsHtml ? `
    <div>
      <div class="analysis-section-label">Suggested Swaps from Your Collection</div>
      ${swapsHtml}
    </div>` : ""}

    ${(matchupFav || matchupUnfav || matchupNeu) ? `
    <div>
      <div class="analysis-section-label">Matchup Overview</div>
      <div class="matchup-grid">
        <div class="matchup-box favorable"><h5>Favorable</h5><ul>${matchupFav || "<li>—</li>"}</ul></div>
        <div class="matchup-box unfavorable"><h5>Unfavorable</h5><ul>${matchupUnfav || "<li>—</li>"}</ul></div>
        <div class="matchup-box neutral"><h5>Neutral</h5><ul>${matchupNeu || "<li>—</li>"}</ul></div>
      </div>
    </div>` : ""}

    ${coaching ? `
    <div>
      <div class="analysis-section-label">Coaching Advice</div>
      <div class="coaching-text">${escapeHtml(coaching)}</div>
    </div>` : ""}

    <div class="analysis-rerun-row">
      <button class="btn btn-ghost btn-sm rerun-analysis-btn">↺ Re-run Deep Analysis</button>
    </div>
  `;

  analysisResult.querySelector(".rerun-analysis-btn").addEventListener("click", runDeckAnalysis);
  analysisResult.classList.remove("hidden");
}


// ── Fine-Tune Chat ─────────────────────────────────────────────────────────

async function sendDetailChatMessage() {
  if (state.detail.chatStreaming) return;
  const message = detailChatInput.value.trim();
  if (!message || !state.detail.deckId) return;

  detailChatInput.value = "";
  detailChatInput.disabled = true;
  detailChatSend.disabled = true;

  const welcome = detailChatMsgs.querySelector(".chat-welcome");
  if (welcome) welcome.remove();
  appendDetailChatMsg("user", message);

  const typing = createTypingIndicator();
  detailChatMsgs.appendChild(typing);
  scrollEl(detailChatMsgs);

  state.detail.chatStreaming = true;

  try {
    const res = await fetch(`/api/saved-decks/${state.detail.deckId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        collection: state.collection,
        player_tag: state.profiles.find(p => p.id === state.activeProfileId)?.player_tag ?? null,
      }),
    });

    if (!res.ok) { typing.remove(); const e = await res.json(); appendDetailChatMsg("assistant", `Error: ${e.error}`); return; }

    let fullText = "";
    let bubbleStarted = false;
    let msgEl, bubble;
    await streamSSE(res,
      (chunk) => {
        if (!bubbleStarted) {
          typing.remove();
          msgEl = createStreamingBubble();
          detailChatMsgs.appendChild(msgEl);
          bubble = msgEl.querySelector(".chat-bubble");
          bubbleStarted = true;
          scrollEl(detailChatMsgs);
        }
        fullText += chunk;
        bubble.textContent = fullText;
        scrollEl(detailChatMsgs);
      },
      (msg) => {
        if (msg.status) typing.innerHTML = `<span class="chat-tool-status">${escapeHtml(msg.status)}</span>`;
        if (msg.done) showTokenUsage(detailChatTokenFooter, msg.usage);
      }
    );
    if (bubbleStarted) { bubble.classList.remove("streaming"); addTimestamp(msgEl); }
    else typing.remove();
  } catch (err) {
    typing.remove();
    appendDetailChatMsg("assistant", `Connection error: ${err.message}`);
  } finally {
    state.detail.chatStreaming = false;
    detailChatInput.disabled = false;
    detailChatSend.disabled = false;
    detailChatInput.focus();
  }
}

function appendDetailChatMsg(role, content, timestamp = null) {
  const welcome = detailChatMsgs.querySelector(".chat-welcome");
  if (welcome) welcome.remove();
  const el = buildChatMessage(role, content, timestamp);
  detailChatMsgs.appendChild(el);
  scrollEl(detailChatMsgs);
}


// ══════════════════════════════════════════════════════════════════════════
// GENERATE / RECOMMENDATIONS
// ══════════════════════════════════════════════════════════════════════════

// ── Card Pool Picker ────────────────────────────────────────────────────
function renderCardPoolGrid() {
  if (!cardPoolGrid) return;
  if (!state.collection.length) {
    cardPoolGrid.innerHTML = `<p class="hint">Load a player profile to select cards.</p>`;
    cardPoolCount.textContent = "";
    return;
  }

  const selected = new Set(state.recOptions.selectedCards.map(n => n.toLowerCase()));
  const sorted   = [...state.collection].sort((a, b) => b.level - a.level || a.name.localeCompare(b.name));

  cardPoolGrid.innerHTML = "";
  sorted.forEach(card => {
    const chip = document.createElement("div");
    const isSelected = selected.has(card.name.toLowerCase());
    chip.className = `card-pool-chip-pick${isSelected ? " selected" : ""}`;
    chip.dataset.name = card.name;
    chip.innerHTML = `<span class="chip-level">${card.level}</span><span class="chip-name">${escapeHtml(card.name)}</span>`;
    chip.addEventListener("click", () => {
      const idx = state.recOptions.selectedCards.findIndex(n => n.toLowerCase() === card.name.toLowerCase());
      if (idx === -1) {
        state.recOptions.selectedCards.push(card.name);
      } else {
        state.recOptions.selectedCards.splice(idx, 1);
      }
      renderCardPoolGrid();
    });
    cardPoolGrid.appendChild(chip);
  });

  const n = state.recOptions.selectedCards.length;
  cardPoolCount.textContent = n ? `${n} card${n !== 1 ? "s" : ""} selected` : "";
}

// ── Generate Decks ──────────────────────────────────────────────────────
async function generateDecks() {
  generateBtn.disabled = true;
  resultsSection.classList.remove("hidden");
  decksContainer.innerHTML = "";
  metaContext.textContent = "";
  state.deckIds = [];

  recTokenUsage.classList.add("hidden");
  streamStatus.classList.add("visible");
  streamMsg.textContent = "Analyzing collection — querying wiki for meta data...";
  setTimeout(() => resultsSection.scrollIntoView({ behavior: "smooth", block: "start" }), 80);

  let accumulated = "";
  try {
    const payload = {
      cards: state.collection.filter(c => c.level >= (c.maxLevel || 16) - 2),
      profile_id: state.activeProfileId,
      player_tag: state.profiles.find(p => p.id === state.activeProfileId)?.player_tag ?? null,
      num_decks: state.recOptions.numDecks,
    };
    if (state.recOptions.strategies.length) payload.strategies = state.recOptions.strategies;
    if (state.recOptions.selectedCards.length) payload.selected_cards = state.recOptions.selectedCards;

    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      showStreamError(err.error || "Request failed");
      return;
    }

    await streamSSE(res,
      (chunk) => { accumulated += chunk; updateStreamStatus(accumulated); },
      (msg) => {
        if (msg.status) streamMsg.textContent = msg.status;
        if (msg.done) {
          if (msg.deck_ids) state.deckIds = msg.deck_ids;
          const ok = tryRenderDecks(accumulated, state.deckIds);
          if (!ok) showStreamError("Failed to parse AI response. Please try again.");
          showTokenUsage(recTokenUsage, msg.usage);
        }
      }
    );
  } catch (err) {
    showStreamError(`Connection error: ${err.message}`);
  } finally {
    streamStatus.classList.remove("visible");
    generateBtn.disabled = state.collection.length < 8;
    if (!historyList.classList.contains("hidden")) loadHistory();
  }
}

function updateStreamStatus(text) {
  if (text.includes('"meta_context"')) streamMsg.textContent = "Analyzing your card collection...";
  else if (text.includes('"decks"')) streamMsg.textContent = "Building deck suggestions...";
  else if (text.includes('"strategy"')) streamMsg.textContent = "Writing strategies...";
}

function showStreamError(msg) {
  streamStatus.classList.remove("visible");
  decksContainer.innerHTML = `<div class="status-msg error" style="display:block"><strong>Error:</strong> ${escapeHtml(msg)}</div>`;
}

function tryRenderDecks(text, deckIds = []) {
  const j0 = text.indexOf("{"), j1 = text.lastIndexOf("}");
  if (j0 === -1 || j1 === -1) return false;
  let parsed;
  try { parsed = JSON.parse(text.slice(j0, j1 + 1)); } catch { return false; }
  if (parsed.meta_context) metaContext.textContent = `Meta snapshot: ${parsed.meta_context}`;
  (parsed.decks || []).forEach((deck, i) => decksContainer.appendChild(buildRecDeckCard(deck, i, deckIds[i] ?? null)));
  return true;
}

function buildRecDeckCard(deck, idx, deckId = null) {
  const winCards = (deck.win_condition || "").toLowerCase().split(/[,/&]+/).map(s => s.trim());
  const cardItemsHtml = (deck.cards || []).map(name => {
    const owned = state.collection.find(c => c.name.toLowerCase() === name.toLowerCase());
    const level = owned ? `<span class="item-level">Lvl ${owned.level}</span>` : "";
    const isWin = winCards.some(w => name.toLowerCase().includes(w) || w.includes(name.toLowerCase()));
    return `<div class="deck-card-item${isWin ? " is-win-condition" : ""}">${escapeHtml(name)}${level}</div>`;
  }).join("");

  const difficulty = deck.difficulty || "Intermediate";
  const strategy = deck.strategy || {};
  const synergies = (strategy.key_synergies || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");
  const matchups  = (strategy.matchup_tips  || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");

  // Grade & scores
  const grade = deck.grade || {};
  const scores = grade.scores || {};
  const gradeClass = `grade-${(grade.overall || "C").replace(/[^A-DS]/g, "")}`;
  const scoreLabels = {
    offense: "Offense", defense: "Defense", synergy: "Synergy",
    versatility: "Versatility", meta_viability: "Meta", f2p_friendly: "F2P"
  };

  let gradeHtml = "";
  if (grade.overall) {
    const barsHtml = Object.entries(scoreLabels).map(([key, label]) => {
      const val = scores[key] ?? 0;
      const pct = val * 10;
      const barColor = val >= 8 ? "var(--cr-green)" : val >= 5 ? "var(--cr-gold)" : "var(--cr-red)";
      return `<div class="score-row">
        <span class="score-label">${label}</span>
        <div class="score-bar-track"><div class="score-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>
        <span class="score-value">${val}/10</span>
      </div>`;
    }).join("");

    gradeHtml = `
      <div class="deck-grade-panel">
        <div class="grade-badge ${gradeClass}">${escapeHtml(grade.overall)}</div>
        <div class="grade-scores">${barsHtml}</div>
        ${grade.summary ? `<p class="grade-summary">${escapeHtml(grade.summary)}</p>` : ""}
      </div>`;
  }

  // Matchups section
  const deckMatchups = deck.matchups || {};
  let matchupsSectionHtml = "";
  if (deckMatchups.favorable || deckMatchups.unfavorable || deckMatchups.even) {
    const favHtml = (deckMatchups.favorable || []).map(s => `<span class="matchup-tag matchup-fav">${escapeHtml(s)}</span>`).join("");
    const unfavHtml = (deckMatchups.unfavorable || []).map(s => `<span class="matchup-tag matchup-unfav">${escapeHtml(s)}</span>`).join("");
    const evenHtml = (deckMatchups.even || []).map(s => `<span class="matchup-tag matchup-even">${escapeHtml(s)}</span>`).join("");
    matchupsSectionHtml = `<div class="strategy-box full-width"><h4>Matchups</h4>
      <div class="matchup-group">
        ${favHtml ? `<div class="matchup-row"><span class="matchup-label fav-label">Favorable:</span>${favHtml}</div>` : ""}
        ${unfavHtml ? `<div class="matchup-row"><span class="matchup-label unfav-label">Unfavorable:</span>${unfavHtml}</div>` : ""}
        ${evenHtml ? `<div class="matchup-row"><span class="matchup-label even-label">Even:</span>${evenHtml}</div>` : ""}
      </div>
    </div>`;
  }

  const el = document.createElement("article");
  el.className = "deck-card";
  el.style.animationDelay = `${idx * 0.1}s`;
  el.innerHTML = `
    <div class="deck-header">
      <div class="deck-title-group">
        <div class="deck-name">${escapeHtml(deck.name || `Deck ${idx + 1}`)}</div>
        <div class="deck-meta">
          ${deck.archetype ? `<span class="tag tag-archetype">${escapeHtml(deck.archetype)}</span>` : ""}
          ${deck.average_elixir ? `<span class="tag tag-elixir">${deck.average_elixir}</span>` : ""}
          <span class="tag tag-difficulty-${difficulty}">${difficulty}</span>
        </div>
      </div>
      <div class="deck-header-right">
        ${deck.win_condition ? `<div class="deck-win-condition">Win: <strong>${escapeHtml(deck.win_condition)}</strong></div>` : ""}
        <button class="btn btn-save-deck save-rec-btn" data-idx="${idx}">⭐ Save</button>
        <button class="btn btn-discuss discuss-btn" ${deckId ? `data-deck-id="${deckId}"` : "disabled"}>💬 Discuss</button>
      </div>
    </div>
    <div class="deck-cards-row">${cardItemsHtml}</div>
    <div class="deck-body">
      ${deck.description ? `<p class="deck-description">${escapeHtml(deck.description)}</p>` : ""}
      ${gradeHtml}
      <div class="strategy-grid">
        ${strategy.general ? `<div class="strategy-box full-width"><h4>General Gameplan</h4><p>${escapeHtml(strategy.general)}</p></div>` : ""}
        ${strategy.offense ? `<div class="strategy-box"><h4>Offense</h4><p>${escapeHtml(strategy.offense)}</p></div>` : ""}
        ${strategy.defense ? `<div class="strategy-box"><h4>Defense</h4><p>${escapeHtml(strategy.defense)}</p></div>` : ""}
        ${synergies ? `<div class="strategy-box"><h4>Key Synergies</h4><ul>${synergies}</ul></div>` : ""}
        ${matchups  ? `<div class="strategy-box"><h4>Matchup Tips</h4><ul>${matchups}</ul></div>`  : ""}
        ${matchupsSectionHtml}
      </div>
      ${deck.level_notes ? `<div class="level-notes"><strong>Level Notes:</strong> ${escapeHtml(deck.level_notes)}</div>` : ""}
    </div>
  `;

  const saveBtn = el.querySelector(".save-rec-btn");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      if (saveBtn.classList.contains("saved")) return;
      const cards = (deck.cards || []).map(name => {
        const owned = state.collection.find(c => c.name.toLowerCase() === name.toLowerCase());
        return owned ? { name: owned.name, level: owned.level, maxLevel: owned.maxLevel } : { name, level: 1, maxLevel: 14 };
      });
      if (cards.length !== 8) return;
      try {
        const res = await fetch("/api/saved-decks", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: deck.name || `Saved Deck ${idx + 1}`,
            cards,
            source: "recommendation",
            profile_id: state.activeProfileId,
          }),
        });
        const data = await res.json();
        if (!data.error) {
          // Persist the recommendation as the deck's initial analysis so it shows immediately
          try {
            await fetch(`/api/saved-decks/${data.id}/analysis`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ analysis: deck, collection: state.collection }),
            });
          } catch { /* non-critical */ }
          saveBtn.textContent = "✓ Saved";
          saveBtn.classList.add("saved");
          await loadSavedDecks();
        }
      } catch { /* ignore */ }
    });
  }

  const discussBtn = el.querySelector(".discuss-btn");
  if (deckId && discussBtn) {
    discussBtn.addEventListener("click", () => openRecChat(deckId, deck));
  }

  return el;
}


// ══════════════════════════════════════════════════════════════════════════
// RECOMMENDATION CHAT
// ══════════════════════════════════════════════════════════════════════════

async function openRecChat(deckId, deckData) {
  state.recChat.deckId = deckId;
  state.recChat.deckData = deckData;
  chatDeckTitle.textContent = deckData.name || "Deck Strategy";
  chatPanelContext.textContent = [
    deckData.archetype,
    deckData.average_elixir ? `⚡ ${deckData.average_elixir}` : null,
    deckData.win_condition ? `Win: ${deckData.win_condition}` : null,
  ].filter(Boolean).join("  ·  ");

  chatMessages.innerHTML = `<div class="chat-welcome"><p>👋 Ask me anything about this deck!</p></div>`;
  recChatTokenFooter.classList.add("hidden");

  try {
    const res = await fetch(`/api/decks/${deckId}/chat`);
    const data = await res.json();
    if (data.messages && data.messages.length) {
      chatMessages.innerHTML = "";
      data.messages.forEach(m => appendRecChatMsg(m.role, m.content, m.created_at));
    }
  } catch { /* ignore */ }

  chatModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  setTimeout(() => chatInput.focus(), 150);
  scrollEl(chatMessages);
}

function closeRecChat() {
  chatModal.classList.add("hidden");
  document.body.style.overflow = "";
}

async function sendRecChatMessage() {
  if (state.recChat.streaming) return;
  const message = chatInput.value.trim();
  if (!message || !state.recChat.deckId) return;

  chatInput.value = "";
  chatInput.disabled = true;
  chatSendBtn.disabled = true;

  const welcome = chatMessages.querySelector(".chat-welcome");
  if (welcome) welcome.remove();
  appendRecChatMsg("user", message);

  const typing = createTypingIndicator();
  chatMessages.appendChild(typing);
  scrollEl(chatMessages);

  state.recChat.streaming = true;
  try {
    const res = await fetch(`/api/decks/${state.recChat.deckId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        player_tag: state.profiles.find(p => p.id === state.activeProfileId)?.player_tag ?? null,
      }),
    });

    if (!res.ok) { typing.remove(); const e = await res.json(); appendRecChatMsg("assistant", `Error: ${e.error}`); return; }

    let fullText = "";
    let bubbleStarted = false;
    let msgEl, bubble;
    await streamSSE(res,
      (chunk) => {
        if (!bubbleStarted) {
          typing.remove();
          msgEl = createStreamingBubble();
          chatMessages.appendChild(msgEl);
          bubble = msgEl.querySelector(".chat-bubble");
          bubbleStarted = true;
          scrollEl(chatMessages);
        }
        fullText += chunk;
        bubble.textContent = fullText;
        scrollEl(chatMessages);
      },
      (msg) => {
        if (msg.status) typing.innerHTML = `<span class="chat-tool-status">${escapeHtml(msg.status)}</span>`;
        if (msg.done) showTokenUsage(recChatTokenFooter, msg.usage);
      }
    );
    if (bubbleStarted) { bubble.classList.remove("streaming"); addTimestamp(msgEl); }
    else typing.remove();
  } catch (err) {
    typing.remove();
    appendRecChatMsg("assistant", `Connection error: ${err.message}`);
  } finally {
    state.recChat.streaming = false;
    chatInput.disabled = false;
    chatSendBtn.disabled = false;
    chatInput.focus();
  }
}

function appendRecChatMsg(role, content, timestamp = null) {
  const welcome = chatMessages.querySelector(".chat-welcome");
  if (welcome) welcome.remove();
  chatMessages.appendChild(buildChatMessage(role, content, timestamp));
  scrollEl(chatMessages);
}


// ══════════════════════════════════════════════════════════════════════════
// HISTORY
// ══════════════════════════════════════════════════════════════════════════

let historyLoaded = false;

async function toggleHistory() {
  const hidden = historyList.classList.contains("hidden");
  historyList.classList.toggle("hidden", !hidden);
  historyToggleBtn.textContent = hidden ? "Hide" : "Show";
  if (hidden && !historyLoaded) await loadHistory();
}

async function loadHistory() {
  historyLoading.classList.remove("hidden");
  historyEmpty.classList.add("hidden");
  historyItems.innerHTML = "";
  try {
    const url = state.activeProfileId
      ? `/api/sessions?profile_id=${state.activeProfileId}`
      : "/api/sessions";
    const res = await fetch(url);
    const data = await res.json();
    historyLoaded = true;
    historyLoading.classList.add("hidden");
    const sessions = data.sessions || [];
    if (!sessions.length) { historyEmpty.classList.remove("hidden"); return; }
    sessions.forEach(s => historyItems.appendChild(buildHistoryItem(s)));
  } catch {
    historyLoading.classList.add("hidden");
    historyEmpty.classList.remove("hidden");
    historyEmpty.textContent = "Failed to load history.";
  }
}

function buildHistoryItem(session) {
  const sessionCards = JSON.parse(session.cards_json || "[]");
  const stale = sessionCards.some(sc => {
    const cur = state.collection.find(c => c.name.toLowerCase() === sc.name.toLowerCase());
    return cur && cur.level !== sc.level;
  });

  const date = new Date(session.created_at + "Z");
  const dateStr = date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  const timeStr = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

  const el = document.createElement("div");
  el.className = `history-item${stale ? " is-stale" : ""}`;
  el.dataset.sessionId = session.id;

  const meta = session.meta_context
    ? session.meta_context.slice(0, 90) + (session.meta_context.length > 90 ? "…" : "")
    : `${session.deck_count} deck${session.deck_count !== 1 ? "s" : ""}`;

  el.innerHTML = `
    <div class="history-item-header">
      <span class="history-item-date">${dateStr} ${timeStr}</span>
      <span class="history-item-meta">${escapeHtml(meta)}</span>
      ${stale ? '<span class="tag tag-stale">⚠ Stale</span>' : ""}
      <span class="history-chevron">▼</span>
    </div>
    <div class="history-item-decks" id="session-decks-${session.id}">
      <div class="history-empty"><div class="spinner"></div> Loading...</div>
    </div>
  `;
  el.querySelector(".history-item-header").addEventListener("click", () => toggleHistoryItem(el, session.id));
  return el;
}

async function toggleHistoryItem(el, sessionId) {
  const wasExpanded = el.classList.contains("expanded");
  el.classList.toggle("expanded", !wasExpanded);
  if (wasExpanded) return;

  const container = $(`session-decks-${sessionId}`);
  if (container.dataset.loaded) return;
  container.dataset.loaded = "1";

  try {
    const res = await fetch(`/api/sessions/${sessionId}`);
    const data = await res.json();
    container.innerHTML = "";
    if (!data.decks?.length) { container.innerHTML = '<div class="history-empty">No decks found.</div>'; return; }

    data.decks.forEach(deckRow => {
      const deck = deckRow.deck;
      const row = document.createElement("div");
      row.className = "history-deck-row";
      row.innerHTML = `
        <div class="history-deck-info">
          <div class="history-deck-name">${escapeHtml(deck.name || "Deck")}${deck.archetype ? ` <span class="tag tag-archetype" style="margin-left:5px">${escapeHtml(deck.archetype)}</span>` : ""}</div>
          <div class="history-deck-cards">${(deck.cards || []).join(", ")}</div>
        </div>
        <div class="history-deck-actions">
          <button class="btn btn-discuss btn-sm hist-discuss-btn">💬 Discuss</button>
        </div>
      `;
      row.querySelector(".hist-discuss-btn").addEventListener("click", () => openRecChat(deckRow.id, deck));
      container.appendChild(row);
    });
  } catch {
    container.innerHTML = '<div class="history-empty">Failed to load decks.</div>';
  }
}


// ══════════════════════════════════════════════════════════════════════════
// SHARED CHAT HELPERS
// ══════════════════════════════════════════════════════════════════════════

function buildChatMessage(role, content, timestamp = null) {
  const el = document.createElement("div");
  el.className = `chat-message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = content;
  el.appendChild(bubble);
  if (timestamp || role === "assistant") {
    const t = document.createElement("div");
    t.className = "chat-message-time";
    const d = timestamp ? new Date(timestamp + "Z") : new Date();
    t.textContent = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    el.appendChild(t);
  }
  return el;
}

function createStreamingBubble() {
  const el = document.createElement("div");
  el.className = "chat-message assistant";
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble streaming";
  el.appendChild(bubble);
  return el;
}

function addTimestamp(msgEl) {
  const t = document.createElement("div");
  t.className = "chat-message-time";
  t.textContent = new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  msgEl.appendChild(t);
}

function createTypingIndicator() {
  const el = document.createElement("div");
  el.className = "chat-typing";
  el.innerHTML = "<span></span><span></span><span></span>";
  return el;
}

function scrollEl(el) { el.scrollTop = el.scrollHeight; }


// ══════════════════════════════════════════════════════════════════════════
// TOKEN USAGE DISPLAY
// ══════════════════════════════════════════════════════════════════════════

function showTokenUsage(el, usage) {
  if (!el || !usage) return;
  const fmt = (n) => n != null ? n.toLocaleString() : "—";
  const cost = usage.cost != null ? `$${usage.cost.toFixed(4)}` : "—";
  el.innerHTML = `
    <span class="tu-label">Tokens</span>
    <span class="tu-sep">|</span>
    <span class="tu-stat tu-in"><span class="tu-icon">↑</span> ${fmt(usage.input_tokens)} in</span>
    <span class="tu-stat tu-out"><span class="tu-icon">↓</span> ${fmt(usage.output_tokens)} out</span>
    <span class="tu-sep">|</span>
    <span class="tu-stat tu-cost">est. ${cost}</span>
  `;
  el.classList.remove("hidden");
}


// ══════════════════════════════════════════════════════════════════════════
// SSE STREAMING HELPER
// ══════════════════════════════════════════════════════════════════════════

async function streamSSE(response, onChunk, onEvent = null) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const msg = JSON.parse(line.slice(6));
        if (msg.error) throw new Error(msg.error);
        if (msg.chunk && onChunk) onChunk(msg.chunk);
        if (onEvent) onEvent(msg);
        if (msg.done) return;
      } catch (e) {
        if (e.message && !e.message.startsWith("JSON")) throw e;
      }
    }
  }
}


// ══════════════════════════════════════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════════════════════════════════════

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}


// ── Boot ───────────────────────────────────────────────────────────────────
init();
