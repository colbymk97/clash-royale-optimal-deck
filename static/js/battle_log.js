/* ============================================================
   Battle Log Page JS
   ============================================================ */

const $ = (id) => document.getElementById(id);

const battleCount             = $("battle-count");
const syncBattlesBtn          = $("sync-battles-btn");
const syncStatus              = $("sync-status");
const syncMsg                 = $("sync-msg");
const battleLogEmpty          = $("battle-log-empty");
const battleLogItems          = $("battle-log-items");
const battleProfileLabel      = $("battle-profile-label");

const battleAnalysisModal     = $("battle-analysis-modal");
const battleAnalysisBackdrop  = $("battle-analysis-backdrop");
const battleAnalysisTitle     = $("battle-analysis-title");
const battleAnalysisClose     = $("battle-analysis-close");
const battleAnalysisDecks     = $("battle-analysis-decks");
const battleAnalysisStream    = $("battle-analysis-stream-status");
const battleAnalysisStatusMsg = $("battle-analysis-status-msg");
const battleAnalysisResult    = $("battle-analysis-result");
const battleAnalysisTokenUsage= $("battle-analysis-token-usage");
const battleAnalysisEmpty     = $("battle-analysis-empty");
const runBattleAnalysisBtn    = $("run-battle-analysis-btn");

const state = {
  activeProfileId: null,
  activeProfile: null,
  battles: [],
  battleAnalysis: { battleId: null, battleData: null, streaming: false },
};

// ── Init ────────────────────────────────────────────────────────────────────

async function init() {
  const storedId = localStorage.getItem("clash_active_profile");
  if (storedId) state.activeProfileId = parseInt(storedId, 10);

  if (state.activeProfileId) {
    try {
      const res = await fetch(`/api/profiles/${state.activeProfileId}`);
      const data = await res.json();
      if (data.profile) {
        state.activeProfile = data.profile;
        battleProfileLabel.textContent = `${data.profile.player_name} (${data.profile.player_tag})`;
      }
    } catch { /* ignore */ }
    await loadBattles();
  } else {
    battleLogEmpty.classList.remove("hidden");
    battleLogEmpty.textContent = "No active profile. Go back to the Deck Builder and select a profile first.";
  }

  syncBattlesBtn.addEventListener("click", syncBattles);
  battleAnalysisBackdrop.addEventListener("click", closeBattleAnalysis);
  battleAnalysisClose.addEventListener("click", closeBattleAnalysis);
  runBattleAnalysisBtn.addEventListener("click", runBattleAnalysis);
}

// ── Data ────────────────────────────────────────────────────────────────────

async function loadBattles() {
  if (!state.activeProfileId) return;
  try {
    const res = await fetch(`/api/profiles/${state.activeProfileId}/battles`);
    const data = await res.json();
    state.battles = data.battles || [];
    battleCount.textContent = state.battles.length;
    renderBattleLog();
  } catch { state.battles = []; }
}

async function syncBattles() {
  if (!state.activeProfileId) return;
  syncBattlesBtn.disabled = true;
  syncStatus.classList.remove("hidden");
  syncMsg.textContent = "Syncing battles from Clash Royale...";

  try {
    const res = await fetch(`/api/profiles/${state.activeProfileId}/battles/sync`, { method: "POST" });
    const data = await res.json();
    if (data.error) {
      syncMsg.textContent = `Error: ${data.error}`;
      setTimeout(() => syncStatus.classList.add("hidden"), 3000);
    } else {
      state.battles = data.battles || [];
      battleCount.textContent = state.battles.length;
      renderBattleLog();
      syncStatus.classList.add("hidden");
    }
  } catch (err) {
    syncMsg.textContent = `Network error: ${err.message}`;
    setTimeout(() => syncStatus.classList.add("hidden"), 3000);
  }
  syncBattlesBtn.disabled = false;
}

// ── Render ───────────────────────────────────────────────────────────────────

function renderBattleLog() {
  battleLogItems.innerHTML = "";
  if (!state.battles.length) {
    battleLogEmpty.classList.remove("hidden");
    return;
  }
  battleLogEmpty.classList.add("hidden");

  state.battles.forEach(b => {
    const resultClass = b.result === "win" ? "battle-win" : b.result === "loss" ? "battle-loss" : "battle-draw";
    const teamChips = (b.team_cards || []).map(c => `<span class="mini-chip">${escapeHtml(c.name)}</span>`).join("");
    const oppChips  = (b.opponent_cards || []).map(c => `<span class="mini-chip">${escapeHtml(c.name)}</span>`).join("");
    const date = b.battle_time
      ? new Date(b.battle_time.replace(/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/, "$1-$2-$3T$4:$5:$6")).toLocaleString()
      : "";
    const hasAnalysis = !!b.analysis;

    const el = document.createElement("div");
    el.className = `battle-log-item ${resultClass}`;
    el.innerHTML = `
      <div class="battle-log-header">
        <div class="battle-result-badge ${resultClass}">${b.result.toUpperCase()}</div>
        <div class="battle-score">${b.team_crowns} – ${b.opponent_crowns}</div>
        <div class="battle-mode">${escapeHtml(b.game_mode || "Ladder")}</div>
        <div class="battle-opponent">vs ${escapeHtml(b.opponent_name || "Opponent")}</div>
        <div class="battle-time">${date}</div>
        <button class="btn btn-sm ${hasAnalysis ? "btn-ghost" : "btn-primary"} analyze-battle-btn">
          ${hasAnalysis ? "View Analysis" : "Analyze"}
        </button>
      </div>
      <div class="battle-decks-row">
        <div class="battle-deck-side">
          <span class="battle-deck-label">Your deck:</span>
          <div class="battle-deck-chips">${teamChips}</div>
        </div>
        <div class="battle-deck-side">
          <span class="battle-deck-label">Opponent:</span>
          <div class="battle-deck-chips">${oppChips}</div>
        </div>
      </div>
    `;
    el.querySelector(".analyze-battle-btn").addEventListener("click", () => openBattleAnalysis(b));
    battleLogItems.appendChild(el);
  });
}

// ── Analysis Modal ───────────────────────────────────────────────────────────

function openBattleAnalysis(battle) {
  state.battleAnalysis.battleId  = battle.id;
  state.battleAnalysis.battleData = battle;

  const resultText = `${battle.result.toUpperCase()} ${battle.team_crowns}–${battle.opponent_crowns}`;
  battleAnalysisTitle.textContent = `${resultText} vs ${battle.opponent_name || "Opponent"}`;

  const teamChips = (battle.team_cards || []).map(c =>
    `<div class="deck-card-item">${escapeHtml(c.name)} <span class="item-level">Lvl ${c.level}</span></div>`
  ).join("");
  const oppChips = (battle.opponent_cards || []).map(c =>
    `<div class="deck-card-item">${escapeHtml(c.name)} <span class="item-level">Lvl ${c.level}</span></div>`
  ).join("");
  battleAnalysisDecks.innerHTML = `
    <div class="battle-analysis-side">
      <h4>Your Deck</h4>
      <div class="deck-cards-row">${teamChips}</div>
    </div>
    <div class="battle-analysis-vs">VS</div>
    <div class="battle-analysis-side">
      <h4>${escapeHtml(battle.opponent_name || "Opponent")}'s Deck</h4>
      <div class="deck-cards-row">${oppChips}</div>
    </div>
  `;

  battleAnalysisStream.classList.add("hidden");
  battleAnalysisTokenUsage.classList.add("hidden");

  if (battle.analysis) {
    showBattleAnalysisResult(battle.analysis);
    battleAnalysisEmpty.style.display = "none";
  } else {
    battleAnalysisResult.classList.add("hidden");
    battleAnalysisEmpty.style.display = "";
  }

  battleAnalysisModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeBattleAnalysis() {
  battleAnalysisModal.classList.add("hidden");
  document.body.style.overflow = "";
}

async function runBattleAnalysis() {
  if (state.battleAnalysis.streaming) return;
  const battleId = state.battleAnalysis.battleId;
  if (!battleId) return;

  state.battleAnalysis.streaming = true;
  battleAnalysisEmpty.style.display = "none";
  battleAnalysisResult.classList.add("hidden");
  battleAnalysisTokenUsage.classList.add("hidden");
  battleAnalysisStream.classList.remove("hidden");
  battleAnalysisStatusMsg.textContent = "Consulting wiki for card matchup data...";

  let accumulated = "";
  try {
    const res = await fetch(`/api/battles/${battleId}/analysis`, { method: "POST" });
    await streamSSE(res,
      (chunk) => { accumulated += chunk; },
      (msg) => {
        if (msg.status) battleAnalysisStatusMsg.textContent = msg.status;
        if (msg.done) {
          battleAnalysisStream.classList.add("hidden");
          showTokenUsage(battleAnalysisTokenUsage, msg.usage);
          if (msg.analysis) {
            showBattleAnalysisResult(msg.analysis);
            const b = state.battles.find(x => x.id === battleId);
            if (b) b.analysis = msg.analysis;
            // Update button label in list
            renderBattleLog();
          } else {
            try {
              const j0 = accumulated.indexOf("{"), j1 = accumulated.lastIndexOf("}");
              if (j0 !== -1 && j1 !== -1) showBattleAnalysisResult(JSON.parse(accumulated.slice(j0, j1 + 1)));
              else battleAnalysisEmpty.style.display = "";
            } catch { battleAnalysisEmpty.style.display = ""; }
          }
        }
      }
    );
  } catch (err) {
    battleAnalysisStream.classList.add("hidden");
    battleAnalysisResult.innerHTML = `<div class="status-msg error">Error: ${escapeHtml(err.message)}</div>`;
    battleAnalysisResult.classList.remove("hidden");
  }
  state.battleAnalysis.streaming = false;
}

function showBattleAnalysisResult(a) {
  battleAnalysisEmpty.style.display = "none";
  battleAnalysisStream.classList.add("hidden");

  const grade = a.grade || {};
  const gradeClass = `grade-${(grade.overall || "C").replace(/[^A-DS]/g, "")}`;

  const interactions = (a.key_interactions   || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");
  const right        = (a.what_went_right    || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");
  const wrong        = (a.what_went_wrong    || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");
  const tips         = (a.improvement_tips   || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");
  const mvps         = (a.card_mvps         || []).map(s => `<span class="matchup-tag matchup-fav">${escapeHtml(s)}</span>`).join("");
  const liabilities  = (a.card_liabilities  || []).map(s => `<span class="matchup-tag matchup-unfav">${escapeHtml(s)}</span>`).join("");

  battleAnalysisResult.innerHTML = `
    <div class="battle-analysis-overview">
      <div class="grade-badge ${gradeClass}">${escapeHtml(grade.overall || "?")}</div>
      <div class="battle-analysis-summary">
        <div class="battle-matchup-line">
          <span class="tag tag-archetype">${escapeHtml(a.your_deck_archetype || "")}</span>
          <span>vs</span>
          <span class="tag tag-archetype">${escapeHtml(a.opponent_deck_archetype || "")}</span>
          <span class="matchup-tag matchup-${a.matchup_favorability === "Favorable" ? "fav" : a.matchup_favorability === "Unfavorable" ? "unfav" : "even"}">${escapeHtml(a.matchup_favorability || "")}</span>
        </div>
        <p>${escapeHtml(a.matchup_summary || "")}</p>
        ${grade.summary ? `<p class="grade-summary">${escapeHtml(grade.summary)}</p>` : ""}
      </div>
    </div>
    <div class="strategy-grid">
      ${interactions ? `<div class="strategy-box full-width"><h4>Key Interactions</h4><ul>${interactions}</ul></div>` : ""}
      ${right        ? `<div class="strategy-box"><h4>What Worked</h4><ul>${right}</ul></div>`         : ""}
      ${wrong        ? `<div class="strategy-box"><h4>What Didn't Work</h4><ul>${wrong}</ul></div>`    : ""}
      ${tips         ? `<div class="strategy-box full-width"><h4>How to Improve</h4><ul>${tips}</ul></div>` : ""}
    </div>
    ${mvps || liabilities ? `
    <div class="battle-card-assessment">
      ${mvps        ? `<div><strong>MVPs:</strong> ${mvps}</div>`             : ""}
      ${liabilities ? `<div><strong>Liabilities:</strong> ${liabilities}</div>` : ""}
    </div>` : ""}
  `;
  battleAnalysisResult.classList.remove("hidden");
}

// ── Token Usage ──────────────────────────────────────────────────────────────

function showTokenUsage(el, usage) {
  if (!usage || !el) return;
  const inp  = usage.input_tokens  || 0;
  const out  = usage.output_tokens || 0;
  const cost = (inp * 3 + out * 15) / 1_000_000;
  el.textContent = `Tokens: ↑ ${inp.toLocaleString()} in  ↓ ${out.toLocaleString()} out  |  est. $${cost.toFixed(4)}`;
  el.classList.remove("hidden");
}

// ── SSE Helper ───────────────────────────────────────────────────────────────

async function streamSSE(response, onChunk, onEvent = null) {
  const reader  = response.body.getReader();
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

// ── Utilities ────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

init();
