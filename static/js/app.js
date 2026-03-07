/* ============================================================
   Clash Royale Deck Builder — Frontend JS
   ============================================================ */

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  allCards: [],       // [{name, maxLevel, ...}] from /api/all-cards
  collection: [],     // [{name, level, maxLevel}] — user's cards
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

// ── Initialise ─────────────────────────────────────────────────────────────
async function init() {
  populateLevelOptions(14); // default max before we know the card
  await loadAllCards();
  bindEvents();
}

async function loadAllCards() {
  try {
    const res = await fetch("/api/all-cards");
    const data = await res.json();
    state.allCards = data.cards || [];
  } catch {
    console.warn("Could not load card list from API.");
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

// ── Tab switching ──────────────────────────────────────────────────────────
function bindEvents() {
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

  // Collection management
  clearCardsBtn.addEventListener("click", () => {
    state.collection = [];
    renderCollection();
  });

  // Generate
  generateBtn.addEventListener("click", generateDecks);
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
  matches.forEach((card, i) => {
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
  cardLevelSel.value = maxLevel; // default to max
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
    // Update level if already in collection
    existing.level = level;
    renderCollection();
    cardSearch.value = "";
    cardLevelSel.value = "";
    cardSearch.focus();
    return;
  }

  // Find maxLevel from allCards
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
  if (!tag) {
    showTagStatus("Please enter a player tag.", "error");
    return;
  }

  showTagStatus("Fetching your cards from Clash Royale API...", "loading");
  fetchCardsBtn.disabled = true;

  try {
    const res = await fetch(`/api/fetch-cards/${encodeURIComponent(tag)}`);
    const data = await res.json();

    if (data.error) {
      showTagStatus(`Error: ${data.error}`, "error");
      return;
    }

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
  streamStatus.classList.add("visible");
  streamMsg.textContent = "Searching for current meta information...";

  // Scroll to results
  setTimeout(() => resultsSection.scrollIntoView({ behavior: "smooth", block: "start" }), 100);

  let accumulated = "";
  let parsedOk = false;

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
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6);
        try {
          const msg = JSON.parse(payload);

          if (msg.error) {
            showStreamError(msg.error);
            return;
          }

          if (msg.done) {
            // Parse the full accumulated JSON
            parsedOk = tryRenderDecks(accumulated);
            if (!parsedOk) {
              showStreamError("Failed to parse AI response. Please try again.");
            }
            return;
          }

          if (msg.chunk) {
            accumulated += msg.chunk;
            updateStreamStatus(accumulated);
          }
        } catch {
          // Ignore malformed SSE lines
        }
      }
    }
  } catch (err) {
    showStreamError(`Connection error: ${err.message}`);
  } finally {
    streamStatus.classList.remove("visible");
    generateBtn.disabled = state.collection.length < 8;
  }
}

function updateStreamStatus(text) {
  // Update status message based on what we've seen so far
  if (text.includes('"meta_context"')) {
    streamMsg.textContent = "Analyzing your card collection...";
  } else if (text.includes('"decks"')) {
    streamMsg.textContent = "Building deck suggestions...";
  } else if (text.includes('"strategy"')) {
    streamMsg.textContent = "Writing strategies...";
  }
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
function tryRenderDecks(text) {
  // Extract JSON from the text (Claude may include extra whitespace/newlines)
  const jsonStart = text.indexOf("{");
  const jsonEnd   = text.lastIndexOf("}");
  if (jsonStart === -1 || jsonEnd === -1) return false;

  let parsed;
  try {
    parsed = JSON.parse(text.slice(jsonStart, jsonEnd + 1));
  } catch {
    return false;
  }

  if (parsed.meta_context) {
    metaContext.textContent = `Meta snapshot: ${parsed.meta_context}`;
  }

  const decks = parsed.decks || [];
  decks.forEach((deck, i) => {
    decksContainer.appendChild(buildDeckCard(deck, i));
  });

  return true;
}

function buildDeckCard(deck, idx) {
  const winCards = (deck.win_condition || "").toLowerCase().split(/[,/&]+/).map(s => s.trim());

  const cardItems = (deck.cards || []).map(name => {
    // Find the card in user's collection to show its level
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
      ${deck.win_condition ? `<div class="deck-win-condition">Win: <strong>${escapeHtml(deck.win_condition)}</strong></div>` : ""}
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
  return el;
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
