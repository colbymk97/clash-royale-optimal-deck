# Clash Royale Optimal Deck

An AI-powered Clash Royale deck builder and analyzer. Give it your card collection and it builds optimized decks for the current meta — or analyze any existing deck with deep coaching advice.

## Features

- **AI Deck Recommendations** — Input your card collection and get 3 distinct deck suggestions (Cycle, Beatdown, Control, etc.) tailored to your card levels
- **Deep Deck Analysis** — Analyze any 8-card deck for tier rating, meta viability, strengths/weaknesses, and suggested swaps from your collection
- **Strategy Chat** — Chat with an AI coach about any deck: matchups, positioning, elixir management, and more
- **Clash Royale API Integration** — Auto-import your card collection and current battle deck by player tag
- **Saved Decks** — Save, edit, and manage your decks with persistent analysis and chat history
- **Wiki-Backed Knowledge** — All AI responses are grounded in a local RAG pipeline built from the Clash Royale Fandom wiki

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com) (required)
- A [Clash Royale API key](https://developer.clashroyale.com) (optional — for auto-importing cards by player tag)
- The [clash-royale-wiki-mcp](../clash-royale-wiki-mcp) RAG pipeline, ingested and embedded

## Setup

1. Clone the repo and install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy the example environment file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
CLASH_ROYALE_API_KEY=your_clash_royale_api_key_here   # optional
FLASK_SECRET_KEY=change_this_to_a_random_secret
FLASK_DEBUG=false
```

3. Run the app:

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Usage

### Get Deck Recommendations

1. Enter your player tag to auto-import your cards, or manually select cards from the dropdown
2. Click **Analyze** — the AI queries the wiki, then builds 3 optimized decks from your collection
3. Click any deck to see detailed strategy, synergies, and matchup tips
4. Use the chat to ask follow-up questions about a specific deck

### Analyze a Saved Deck

1. Go to **Saved Decks** and create or import a deck
2. Click **Run Deep Analysis** — the AI evaluates it against the current meta and gives a tier rating, strengths/weaknesses, and swap suggestions
3. Use the fine-tune chat to explore specific improvements

---

## AI Operations

Every AI operation uses an **agentic tool-use loop**: Claude can call any of 6 wiki retrieval tools (backed by a local ChromaDB vector store) as many times as it needs before committing to an answer. All four operations use the same underlying loop — the differences are in output format and how the final response is delivered.

### Wiki Tools Available to Claude

| Tool | What it does |
|---|---|
| `get_card_info` | Stats, description, and details for a specific card |
| `get_card_counters` | Cards that counter a given card |
| `get_card_synergies` | Cards that pair well with a given card |
| `search_deck_strategies` | Deck compositions, archetypes, and play guides |
| `get_game_mechanics` | Game mechanics (elixir, towers, deck building rules, etc.) |
| `search_wiki` | General semantic search across all wiki content |

Tool calls are dispatched to a persistent subprocess (`wiki_context.py`) running the local RAG server, so the ChromaDB index and embedding model stay warm across requests — no cold-start overhead per tool call.

---

### 1. Deck Recommendations

**Trigger:** clicking *Analyze & Generate Recommendations*
**Flask route:** `POST /api/analyze`
**Deck analyzer method:** `analyze_stream(cards)`
**Agent loop:** `_buffered_agent` (non-streaming throughout)

Claude receives your high-level card collection (filtered to cards within 2 levels of max) and is instructed to query the wiki before answering. It typically calls `search_deck_strategies` to understand the current meta, then `get_card_synergies` for candidate win conditions, before writing its response.

**Why non-streaming:** The output is a single JSON object containing all 3 decks. The frontend can only render anything once the entire JSON is parsed — there's no benefit to streaming individual tokens. The whole response is yielded as one event when Claude finishes.

**Typical tool call sequence:**
```
search_deck_strategies("competitive meta cycle beatdown control")
get_card_synergies("Hog Rider")          ← win condition from your collection
get_card_counters("Hog Rider")           ← informs level_notes and matchup_tips
→ final response: JSON with 3 decks
```

---

### 2. Deep Deck Analysis

**Trigger:** clicking *Run Deep Analysis* inside a saved deck
**Flask route:** `POST /api/saved-decks/<id>/analysis`
**Deck analyzer method:** `analyze_saved_deck_stream(deck_cards, collection)`
**Agent loop:** `_buffered_agent` (non-streaming throughout)

Claude receives the 8 deck cards and your full collection. It is instructed to look up card data before judging the deck. It typically calls `get_card_info` for each card in the deck, then `get_card_counters` and `get_card_synergies` for the win condition before writing the analysis. Swap suggestions are constrained to cards present in your collection.

**Why non-streaming:** Same as recommendations — the output is a JSON object (tier rating, matchups, coaching paragraphs, suggested swaps) that is only useful when fully parsed and rendered in the analysis panel.

**Typical tool call sequence:**
```
get_card_info("Hog Rider")
get_card_info("Musketeer")
get_card_info("Ice Golem")
... (remaining deck cards)
get_card_counters("Hog Rider")           ← win condition counters → weaknesses
get_card_synergies("Hog Rider")          ← synergy check → strengths
→ final response: JSON analysis object
```

---

### 3. Recommendation Chat

**Trigger:** clicking *Chat* on a recommended deck card
**Flask route:** `POST /api/decks/<id>/chat`
**Deck analyzer method:** `chat_stream(deck, cards, history, message)`
**Agent loop:** `_streaming_agent` (streaming for the final response)

After recommendations are generated, you can open a chat about any specific deck. The system prompt is built dynamically: it includes the deck's name, archetype, full card list, strategy section, key synergies, and your card collection. All previous messages in the conversation are included each turn.

Claude is given wiki tools and decides whether to use them based on the question. Simple strategic questions ("how do I open the game?") are often answered from the system prompt context alone. Specific questions about matchups or counters ("how do I beat Mega Knight?") typically trigger a `get_card_counters` or `search_wiki` call.

**Why streaming:** The output is conversational prose. Word-by-word streaming makes the response feel immediate. The first API call is a streaming call. If Claude returns without using any tools, those buffered chunks are forwarded directly. If Claude uses a tool, the pre-tool output is discarded, a status event is sent to update the typing indicator, then a fresh streaming call is made for the actual answer.

**Typical tool call sequences:**
```
# Simple question (no tools):
→ streaming response directly

# Matchup question:
get_card_counters("Mega Knight")
→ streaming response (word-by-word)

# Swap question:
get_card_info("Valkyrie")
get_card_synergies("Hog Rider")
→ streaming response (word-by-word)
```

---

### 4. Saved Deck Fine-Tune Chat

**Trigger:** typing in the *Fine-tune Chat* panel inside a saved deck detail view
**Flask route:** `POST /api/saved-decks/<id>/chat`
**Deck analyzer method:** `saved_deck_chat_stream(deck_cards, analysis, collection, history, message)`
**Agent loop:** `_streaming_agent` (streaming for the final response)

Structurally identical to Recommendation Chat, but the system prompt is richer. If a deep analysis has been run, it is injected into the system prompt (tier rating, strengths, weaknesses, suggested swaps) so Claude builds on the prior analysis rather than repeating it. The full conversation history and your card collection are also included so swap suggestions stay grounded in what you actually own.

**Why streaming:** Same reasoning as Recommendation Chat — conversational prose benefits from word-by-word streaming.

**How it differs from Recommendation Chat:**
- Richer system prompt (prior analysis section, if available)
- Operates on manually-saved decks (not AI-generated ones)
- Swap context is anchored to the full collection, not just the high-level subset sent to the recommender

---

### Agentic Loop: How Tool Rounds Work

Both loop types follow the same tool-use pattern:

```
messages = [initial user message]

loop:
  call Claude (with WIKI_TOOLS defined)

  if stop_reason == "tool_use":
    for each tool_use block in response:
      emit status event → frontend updates typing indicator
      dispatch tool call → persistent wiki subprocess
    append assistant message + tool results to messages
    continue loop

  if stop_reason == "end_turn":
    yield final text
    break
```

The difference between `_buffered_agent` and `_streaming_agent` is only in how the **final** `end_turn` response is delivered:

| | `_buffered_agent` | `_streaming_agent` |
|---|---|---|
| Used for | JSON outputs (analyze) | Prose outputs (chat) |
| Tool rounds | Non-streaming `messages.create()` | First call streaming; remaining non-streaming |
| Final response | Non-streaming `messages.create()` → yield full text | Fresh streaming call → yield word-by-word |
| Why | JSON only renders when complete | Prose benefits from progressive display |

---

## Stack

- **Backend:** Python / Flask
- **AI:** Claude Sonnet 4.6 via Anthropic API
- **AI Knowledge:** Local RAG pipeline (`clash-royale-wiki-mcp`) — ChromaDB + `all-MiniLM-L6-v2` embeddings over Clash Royale Fandom wiki
- **Database:** SQLite (via `db.py`)
- **Frontend:** Vanilla JS + CSS

## Project Structure

```
app.py              Flask routes and SSE streaming
deck_analyzer.py    Agentic loop logic (buffered + streaming agents)
prompts.py          All Claude prompt strings and builder functions
wiki_context.py     Persistent wiki subprocess server + Anthropic tool definitions
clash_api.py        Clash Royale API client (player cards, current deck)
db.py               SQLite helpers (sessions, saved decks, chat history)
templates/          Jinja2 HTML
static/             JS and CSS
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/all-cards` | List all Clash Royale cards |
| GET | `/api/fetch-cards/<player_tag>` | Fetch a player's card collection + current deck |
| POST | `/api/analyze` | Stream deck recommendations (SSE) |
| GET/POST | `/api/saved-decks` | List / create saved decks |
| GET/PUT/DELETE | `/api/saved-decks/<id>` | Get / update / delete a saved deck |
| POST | `/api/saved-decks/<id>/analysis` | Stream deep deck analysis (SSE) |
| GET/POST | `/api/saved-decks/<id>/chat` | Get / post fine-tune chat messages (SSE) |
| GET/POST | `/api/decks/<id>/chat` | Get / post recommendation chat messages (SSE) |
| GET | `/api/sessions` | List recommendation history sessions |
| GET | `/api/sessions/<id>` | Get a specific session |
