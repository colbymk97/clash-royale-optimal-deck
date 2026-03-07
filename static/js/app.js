/* ============================================================
   Clash Royale Deck Builder — Frontend JS
   ============================================================ */

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  allCards: [],       // [{name, maxLevel, ...}] from /api/all-cards
  collection: [],     // [{name, level, maxLevel}] — user's cards
  deckIds: [],        // [int] deck IDs from last analysis
  chat: {
    deckId: null,     // currently open deck
    deckData: null,   // {name, archetype, cards, ...}
    streaming: false,
  },
};

// ── DOM refs ───────────────────────────────────────────────────────────────
const cardSearch       = document.getElementById("card-search");
const cardLevelSel     = document.getElementById("card-level");
const addCardBtn       = document.getElementById("add-card-btn");
const suggestList      = document.getElementById("card-suggestions");
const cardGrid         = document.getElementById("card-grid");
const cardCountBadge   = document.getElementById("card-count");
const collectionHint   = document.getElementById("collection-hint");
const clearCardsBtn    = document.getElementById("clear-cards-btn");

const playerTagInput   = document.getElementById("player-tag");
const fetchCardsBtn    = document.getElementById("fetch-cards-btn");
const tagStatus        = document.getElementById("tag-status");

const generateBtn      = document.getElementById("generate-btn");
const resultsSection   = document.getElementById("results-section");
const streamStatus     = document.getElementById("stream-status");
const streamMsg        = document.getElementById("stream-msg");
const decksContainer   = document.getElementById("decks-container");
const metaContext      = document.getElementById("meta-context");

const historyToggleBtn = document.getElementById("history-toggle-btn");
const historyList      = document.getElementById("history-list");
const historyLoading   = document.getElementById("history-loading");
const historyEmpty     = document.getElementById("history-empty");
const historyItems     = document.getElementById("history-items");

const chatModal        = document.getElementById("chat-modal");
const chatBackdrop     = document.getElementById("chat-backdrop");
const chatCloseBtn     = document.getElementById("chat-close-btn");
const chatDeckTitle    = document.getElementById("chat-deck-title");
const chatPanelContext = document.getElementById("chat-panel-context");
const chatMessages     = document.getElementById("chat-messages");
const chatInput        = document.getElementById("chat-input");
const chatSendBtn      = document.getElementById("chat-send-btn");

// ── Initialise ─────────────────────────────────────────────────────────────
async function init() {
  populateLevelOptions(14);
  await loadAllCards();
  bindEvents();
}

async function loadAllCards() {
  try {
    const res = await fetch("/api/all-cards");
    const data = await res.json();
    state.allCards = data.cards || [];
  } catch {
    console.warn("Could not load card list.");
  }
}

function populateLevelOptions(max = 14) {
  cardLevelSel.innerHTML = '<option value="">Level</option>';
  for (let i = 1; i <= max; i++) {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `Lvl ${i}`;
    cardLevelSel.appendChild(opt);
  }
}

// ── Event Bindings ─────────────────────────────────────────────────────────
function bindEvents() {
  // Tabs
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  // Manual card entry
  cardSearch.addEventListener("input", onSearchInput);
  cardSearch.addEventListener("keydown", onSearchKeydown);
  document.addEventListener("click", (e) => {
    if (!cardSearch.contains(e.target)) hideSuggestions();
  });
  addCardBtn.addEventListener("click", addCardFromInput);

  // Player tag import
  fetchCardsBtn.addEventListener("click", importByPlayerTag);
  playerTagInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") importByPlayerTag();
  });

  // Collection
  clearCardsBtn.addEventListener("click", () => {
    state.collection = [];
    renderCollection();
  });

  // Generate
  generateBtn.addEventListener("click", generateDecks);

  // History toggle
  historyToggleBtn.addEventListener("click", toggleHistory);

  // Chat modal
  chatBackdrop.addEventListener("click", closeChat);
  chatCloseBtn.addEventListener("click", closeChat);
  chatSendBtn.addEventListener("click", sendChatMessage);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
  });
  document.querySelectorAll(".chat-suggestion").forEach(btn => {
    btn.addEventListener("click", () => {
      chatInput.value = btn.dataset.q;
      chatInput.focus();
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !chatModal.classList.contains("hidden")) closeChat();
  });
}

// ── Autocomplete ───────────────────────────────────────────────────────────
let focusedIdx = -1;

function onSearchInput() {
  const q = cardSearch.value.trim().toLowerCase();
  if (!q) { hideSuggestions(); return; }

  const alreadyAdded = new Set(state.collection.map(c => c.name.toLowerCase()));
  const matches = state.allCards
    .filter(c => c.name.toLowerCase().includes(q) && !alreadyAdded.has(c.name.toLowerCase()))
    .slice(0, 8);

  if (!matches.length) { hideSuggestions(); return; }

  suggestList.innerHTML = "";
  focusedIdx = -1;
  matches.forEach((card) => {
    const li = document.createElement("li");
    li.innerHTML = highlightMatch(card.name, q);
    li.dataset.name = card.name;
    li.dataset.maxLevel = card.maxLevel || 14;
    li.addEventListener("mousedown", (e) => {
      e.preventDefault();
      selectSuggestion(card.name, card.maxLevel || 14);
    });
    suggestList.appendChild(li);
  });
  suggestList.classList.remove("hidden");
}

function onSearchKeydown(e) {
  const items = suggestList.querySelectorAll("li");
  if (e.key === "ArrowDown") {
    e.preventDefault();
    focusedIdx = Math.min(focusedIdx + 1, items.length - 1);
    updateFocused(items);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    focusedIdx = Math.max(focusedIdx - 1, 0);
    updateFocused(items);
  } else if (e.key === "Enter") {
    if (focusedIdx >= 0 && items[focusedIdx]) {
      const li = items[focusedIdx];
      selectSuggestion(li.dataset.name, parseInt(li.dataset.maxLevel));
    } else {
      addCardFromInput();
    }
  } else if (e.key === "Escape") {
    hideSuggestions();
  }
}

function updateFocused(items) {
  items.forEach((li, i) => li.classList.toggle("focused", i === focusedIdx));
}

function selectSuggestion(name, maxLevel) {
  cardSearch.value = name;
  populateLevelOptions(maxLevel);
  cardLevelSel.value = maxLevel;
  hideSuggestions();
  cardLevelSel.focus();
}

function hideSuggestions() {
  suggestList.classList.add("hidden");
  suggestList.innerHTML = "";
  focusedIdx = -1;
}

function highlightMatch(name, query) {
  const idx = name.toLowerCase().indexOf(query);
  if (idx === -1) return escapeHtml(name);
  return (
    escapeHtml(name.slice(0, idx)) +
    `<mark>${escapeHtml(name.slice(idx, idx + query.length))}</mark>` +
    escapeHtml(name.slice(idx + query.length))
  );
}

// ── Add card manually ──────────────────────────────────────────────────────
function addCardFromInput() {
  const name = cardSearch.value.trim();
  const level = parseInt(cardLevelSel.value);
  if (!name) { cardSearch.focus(); return; }
  if (!level) { cardLevelSel.focus(); return; }

  const existing = state.collection.find(c => c.name.toLowerCase() === name.toLowerCase());
  if (existing) {
    existing.level = level;
    renderCollection();
    cardSearch.value = "";
    cardLevelSel.value = "";
    cardSearch.focus();
    return;
  }

  const cardData = state.allCards.find(c => c.name.toLowerCase() === name.toLowerCase());
  const maxLevel = cardData ? (cardData.maxLevel || 14) : 14;

  state.collection.push({ name, level, maxLevel });
  renderCollection();
  cardSearch.value = "";
  cardLevelSel.value = "";
  hideSuggestions();
  cardSearch.focus();
}

// ── Import by player tag ───────────────────────────────────────────────────
async function importByPlayerTag() {
  const tag = playerTagInput.value.trim();
  if (!tag) { showTagStatus("Please enter a player tag.", "error"); return; }

  showTagStatus("Fetching your cards from Clash Royale API...", "loading");
  fetchCardsBtn.disabled = true;

  try {
    const res = await fetch(`/api/fetch-cards/${encodeURIComponent(tag)}`);
    const data = await res.json();

    if (data.error) { showTagStatus(`Error: ${data.error}`, "error"); return; }

    state.collection = data.cards.map(c => ({
      name: c.name,
      level: c.level,
      maxLevel: c.maxLevel || 14,
    }));
    renderCollection();

    const { name, trophies, arena } = data.player || {};
    const label = [name, trophies && `${trophies} trophies`, arena].filter(Boolean).join(" · ");
    showTagStatus(`Imported ${data.total} cards for ${label}`, "success");
  } catch (err) {
    showTagStatus(`Network error: ${err.message}`, "error");
  } finally {
    fetchCardsBtn.disabled = false;
  }
}

function showTagStatus(msg, type) {
  tagStatus.textContent = msg;
  tagStatus.className = `status-msg ${type}`;
  tagStatus.classList.remove("hidden");
}

// ── Render collection ──────────────────────────────────────────────────────
function renderCollection() {
  cardGrid.innerHTML = "";
  state.collection.forEach((card, i) => {
    const chip = document.createElement("div");
    chip.className = "card-chip";
    chip.innerHTML = `
      <span class="chip-level">${card.level}</span>
      <span class="chip-name">${escapeHtml(card.name)}</span>
      <button class="chip-remove" title="Remove" data-idx="${i}">&times;</button>
    `;
    chip.querySelector(".chip-remove").addEventListener("click", () => {
      state.collection.splice(i, 1);
      renderCollection();
    });
    cardGrid.appendChild(chip);
  });

  const count = state.collection.length;
  cardCountBadge.textContent = `${count} card${count !== 1 ? "s" : ""}`;
  collectionHint.style.display = count > 0 ? "none" : "";
  generateBtn.disabled = count < 8;
}

// ── Generate decks ─────────────────────────────────────────────────────────
async function generateDecks() {
  generateBtn.disabled = true;
  resultsSection.classList.remove("hidden");
  decksContainer.innerHTML = "";
  metaContext.textContent = "";
  state.deckIds = [];

  streamStatus.classList.add("visible");
  streamMsg.textContent = "Searching for current meta information...";

  setTimeout(() => resultsSection.scrollIntoView({ behavior: "smooth", block: "start" }), 100);

  let accumulated = "";

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cards: state.collection }),
    });

    if (!res.ok) {
      const err = await res.json();
      showStreamError(err.error || "Request failed");
      return;
    }

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
        const payload = line.slice(6);
        try {
          const msg = JSON.parse(payload);

          if (msg.error) { showStreamError(msg.error); return; }

          if (msg.done) {
            if (msg.deck_ids) state.deckIds = msg.deck_ids;
            const ok = tryRenderDecks(accumulated, msg.deck_ids || []);
            if (!ok) showStreamError("Failed to parse AI response. Please try again.");
            return;
          }

          if (msg.chunk) {
            accumulated += msg.chunk;
            updateStreamStatus(accumulated);
          }
        } catch { /* ignore malformed SSE */ }
      }
    }
  } catch (err) {
    showStreamError(`Connection error: ${err.message}`);
  } finally {
    streamStatus.classList.remove("visible");
    generateBtn.disabled = state.collection.length < 8;
    // Refresh history list if it's open
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
  decksContainer.innerHTML = `
    <div class="status-msg error" style="display:block">
      <strong>Error:</strong> ${escapeHtml(msg)}
    </div>
  `;
}

// ── Parse & render decks ───────────────────────────────────────────────────
function tryRenderDecks(text, deckIds = []) {
  const jsonStart = text.indexOf("{");
  const jsonEnd   = text.lastIndexOf("}");
  if (jsonStart === -1 || jsonEnd === -1) return false;

  let parsed;
  try { parsed = JSON.parse(text.slice(jsonStart, jsonEnd + 1)); }
  catch { return false; }

  if (parsed.meta_context) {
    metaContext.textContent = `Meta snapshot: ${parsed.meta_context}`;
  }

  (parsed.decks || []).forEach((deck, i) => {
    const deckId = deckIds[i] ?? null;
    decksContainer.appendChild(buildDeckCard(deck, i, deckId));
  });

  return true;
}

function buildDeckCard(deck, idx, deckId = null) {
  const winCards = (deck.win_condition || "").toLowerCase().split(/[,/&]+/).map(s => s.trim());

  const cardItems = (deck.cards || []).map(name => {
    const owned = state.collection.find(c => c.name.toLowerCase() === name.toLowerCase());
    const level = owned ? `Lvl ${owned.level}` : "";
    const isWin = winCards.some(w => name.toLowerCase().includes(w) || w.includes(name.toLowerCase()));
    return `<div class="deck-card-item ${isWin ? "is-win-condition" : ""}">
      ${escapeHtml(name)}${level ? `<span class="item-level">${level}</span>` : ""}
    </div>`;
  }).join("");

  const difficulty = deck.difficulty || "Intermediate";
  const strategy   = deck.strategy || {};
  const synergies  = (strategy.key_synergies || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");
  const matchups   = (strategy.matchup_tips || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");

  const discussAttrs = deckId
    ? `data-deck-id="${deckId}" data-deck-name="${escapeHtml(deck.name || "")}" data-deck-archetype="${escapeHtml(deck.archetype || "")}"`
    : `disabled title="Save a deck first to enable chat"`;

  const el = document.createElement("article");
  el.className = "deck-card";
  el.style.animationDelay = `${idx * 0.12}s`;
  el.innerHTML = `
    <div class="deck-header">
      <div class="deck-title-group">
        <div class="deck-name">${escapeHtml(deck.name || `Deck ${idx + 1}`)}</div>
        <div class="deck-meta">
          ${deck.archetype ? `<span class="tag tag-archetype">${escapeHtml(deck.archetype)}</span>` : ""}
          ${deck.average_elixir ? `<span class="tag tag-elixir">⚡ ${deck.average_elixir} avg elixir</span>` : ""}
          <span class="tag tag-difficulty-${difficulty}">${difficulty}</span>
        </div>
      </div>
      <div class="deck-header-right">
        ${deck.win_condition ? `<div class="deck-win-condition">Win: <strong>${escapeHtml(deck.win_condition)}</strong></div>` : ""}
        <button class="btn btn-discuss discuss-btn" ${discussAttrs}>
          💬 Discuss
        </button>
      </div>
    </div>

    <div class="deck-cards">${cardItems}</div>

    <div class="deck-body">
      ${deck.description ? `<p class="deck-description">${escapeHtml(deck.description)}</p>` : ""}

      <div class="strategy-grid">
        ${strategy.general ? `
          <div class="strategy-box full-width">
            <h4>General Gameplan</h4>
            <p>${escapeHtml(strategy.general)}</p>
          </div>` : ""}
        ${strategy.offense ? `
          <div class="strategy-box">
            <h4>Offense</h4>
            <p>${escapeHtml(strategy.offense)}</p>
          </div>` : ""}
        ${strategy.defense ? `
          <div class="strategy-box">
            <h4>Defense</h4>
            <p>${escapeHtml(strategy.defense)}</p>
          </div>` : ""}
        ${synergies ? `
          <div class="strategy-box">
            <h4>Key Synergies</h4>
            <ul>${synergies}</ul>
          </div>` : ""}
        ${matchups ? `
          <div class="strategy-box">
            <h4>Matchup Tips</h4>
            <ul>${matchups}</ul>
          </div>` : ""}
      </div>

      ${deck.level_notes ? `
        <div class="level-notes">
          <strong>Level Notes:</strong> ${escapeHtml(deck.level_notes)}
        </div>` : ""}
    </div>
  `;

  // Wire up the Discuss button
  const discussBtn = el.querySelector(".discuss-btn");
  if (deckId && discussBtn) {
    discussBtn.addEventListener("click", () => openChat(deckId, deck));
  }

  return el;
}

// ── History ────────────────────────────────────────────────────────────────
let historyLoaded = false;

async function toggleHistory() {
  const isHidden = historyList.classList.contains("hidden");
  historyList.classList.toggle("hidden", !isHidden);
  historyToggleBtn.textContent = isHidden ? "Hide" : "Show";
  if (isHidden && !historyLoaded) await loadHistory();
}

async function loadHistory() {
  historyLoading.classList.remove("hidden");
  historyEmpty.classList.add("hidden");
  historyItems.innerHTML = "";

  try {
    const res = await fetch("/api/sessions");
    const data = await res.json();
    const sessions = data.sessions || [];

    historyLoaded = true;
    historyLoading.classList.add("hidden");

    if (!sessions.length) {
      historyEmpty.classList.remove("hidden");
      return;
    }

    sessions.forEach(session => {
      historyItems.appendChild(buildHistoryItem(session));
    });
  } catch {
    historyLoading.classList.add("hidden");
    historyEmpty.classList.remove("hidden");
    historyEmpty.textContent = "Failed to load history.";
  }
}

function buildHistoryItem(session) {
  const date = new Date(session.created_at + "Z");
  const dateStr = date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  const timeStr = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

  const el = document.createElement("div");
  el.className = "history-item";
  el.dataset.sessionId = session.id;

  const meta = session.meta_context
    ? session.meta_context.slice(0, 80) + (session.meta_context.length > 80 ? "…" : "")
    : `${session.deck_count} deck${session.deck_count !== 1 ? "s" : ""} generated`;

  el.innerHTML = `
    <div class="history-item-header">
      <span class="history-item-date">${dateStr} ${timeStr}</span>
      <span class="history-item-meta">${escapeHtml(meta)}</span>
      <span class="history-chevron">▼</span>
    </div>
    <div class="history-item-decks" id="session-decks-${session.id}">
      <div class="history-empty" style="padding:12px">
        <div class="spinner"></div> Loading decks...
      </div>
    </div>
  `;

  el.querySelector(".history-item-header").addEventListener("click", () =>
    toggleHistoryItem(el, session.id)
  );

  return el;
}

async function toggleHistoryItem(el, sessionId) {
  const wasExpanded = el.classList.contains("expanded");
  el.classList.toggle("expanded", !wasExpanded);

  if (!wasExpanded) {
    const deckContainer = el.querySelector(`#session-decks-${sessionId}`);
    if (deckContainer.dataset.loaded) return;
    deckContainer.dataset.loaded = "1";

    try {
      const res = await fetch(`/api/sessions/${sessionId}`);
      const data = await res.json();

      deckContainer.innerHTML = "";
      if (!data.decks || !data.decks.length) {
        deckContainer.innerHTML = '<div class="history-empty">No decks found.</div>';
        return;
      }

      data.decks.forEach(deckRow => {
        const deck = deckRow.deck;
        const row = document.createElement("div");
        row.className = "history-deck-row";
        row.innerHTML = `
          <div class="history-deck-info">
            <div class="history-deck-name">
              ${escapeHtml(deck.name || "Deck")}
              ${deck.archetype ? `<span class="tag tag-archetype" style="margin-left:6px">${escapeHtml(deck.archetype)}</span>` : ""}
            </div>
            <div class="history-deck-cards">${(deck.cards || []).join(", ")}</div>
          </div>
          <div class="history-deck-actions">
            <button class="btn btn-discuss history-discuss-btn"
              data-deck-id="${deckRow.id}">
              💬 Discuss
            </button>
          </div>
        `;
        row.querySelector(".history-discuss-btn").addEventListener("click", () =>
          openChat(deckRow.id, deck)
        );
        deckContainer.appendChild(row);
      });
    } catch {
      deckContainer.innerHTML = '<div class="history-empty">Failed to load decks.</div>';
    }
  }
}

// ── Chat ───────────────────────────────────────────────────────────────────
async function openChat(deckId, deckData) {
  state.chat.deckId = deckId;
  state.chat.deckData = deckData;

  // Set header
  chatDeckTitle.textContent = deckData.name || "Deck Strategy";
  chatPanelContext.textContent = [
    deckData.archetype,
    deckData.average_elixir ? `⚡ ${deckData.average_elixir} elixir` : null,
    deckData.win_condition ? `Win: ${deckData.win_condition}` : null,
  ].filter(Boolean).join("  ·  ");

  // Reset messages area
  chatMessages.innerHTML = `
    <div class="chat-welcome">
      <p>👋 Ask me anything about this deck — matchups, placements, elixir management, counters, or how to improve your gameplay!</p>
    </div>
  `;

  // Load existing chat history
  try {
    const res = await fetch(`/api/decks/${deckId}/chat`);
    const data = await res.json();
    if (data.messages && data.messages.length) {
      chatMessages.innerHTML = ""; // clear welcome if we have history
      data.messages.forEach(msg => appendChatMessage(msg.role, msg.content, msg.created_at));
    }
  } catch { /* ignore, start fresh */ }

  chatModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  setTimeout(() => chatInput.focus(), 200);
  scrollChatToBottom();
}

function closeChat() {
  chatModal.classList.add("hidden");
  document.body.style.overflow = "";
  state.chat.deckId = null;
  state.chat.deckData = null;
}

async function sendChatMessage() {
  if (state.chat.streaming) return;
  const message = chatInput.value.trim();
  if (!message || !state.chat.deckId) return;

  chatInput.value = "";
  chatInput.disabled = true;
  chatSendBtn.disabled = true;

  // Remove welcome message if present
  const welcome = chatMessages.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  // Show user message immediately
  appendChatMessage("user", message);

  // Show typing indicator
  const typing = document.createElement("div");
  typing.className = "chat-typing";
  typing.innerHTML = "<span></span><span></span><span></span>";
  chatMessages.appendChild(typing);
  scrollChatToBottom();

  state.chat.streaming = true;

  try {
    const res = await fetch(`/api/decks/${state.chat.deckId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    if (!res.ok) {
      typing.remove();
      const err = await res.json();
      appendChatMessage("assistant", `Error: ${err.error || "Request failed"}`);
      return;
    }

    typing.remove();

    // Create streaming assistant bubble
    const msgEl = document.createElement("div");
    msgEl.className = "chat-message assistant";
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble streaming";
    msgEl.appendChild(bubble);
    chatMessages.appendChild(msgEl);
    scrollChatToBottom();

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullText = "";

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
          if (msg.chunk) {
            fullText += msg.chunk;
            bubble.textContent = fullText;
            scrollChatToBottom();
          }
          if (msg.done) {
            bubble.classList.remove("streaming");
            // Add timestamp
            const time = document.createElement("div");
            time.className = "chat-message-time";
            time.textContent = new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
            msgEl.appendChild(time);
          }
        } catch { /* ignore */ }
      }
    }
  } catch (err) {
    typing.remove();
    appendChatMessage("assistant", `Connection error: ${err.message}`);
  } finally {
    state.chat.streaming = false;
    chatInput.disabled = false;
    chatSendBtn.disabled = false;
    chatInput.focus();
  }
}

function appendChatMessage(role, content, timestamp = null) {
  // Clear welcome message if there are real messages
  const welcome = chatMessages.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  const msgEl = document.createElement("div");
  msgEl.className = `chat-message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = content;
  msgEl.appendChild(bubble);

  if (timestamp || role === "assistant") {
    const time = document.createElement("div");
    time.className = "chat-message-time";
    const t = timestamp ? new Date(timestamp + "Z") : new Date();
    time.textContent = t.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    msgEl.appendChild(time);
  }

  chatMessages.appendChild(msgEl);
  scrollChatToBottom();
}

function scrollChatToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ── Utilities ──────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Boot ───────────────────────────────────────────────────────────────────
init();
