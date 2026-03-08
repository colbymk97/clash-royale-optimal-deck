# Clash Royale Optimal Deck

An AI-powered Clash Royale deck builder and analyzer. Give it your card collection and it builds optimized decks for the current meta — or analyze any existing deck with deep coaching advice.

## Features

- **AI Deck Recommendations** — Input your card collection and get 3 distinct deck suggestions (Cycle, Beatdown, Control, etc.) tailored to your card levels
- **Deep Deck Analysis** — Analyze any 8-card deck for tier rating, meta viability, strengths/weaknesses, and suggested swaps from your collection
- **Strategy Chat** — Chat with an AI coach about any deck: matchups, positioning, elixir management, and more
- **Clash Royale API Integration** — Optionally auto-import your card collection by player tag
- **Saved Decks** — Save, edit, and manage your decks with persistent analysis and chat history

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com) (required)
- A [Clash Royale API key](https://developer.clashroyale.com) (optional — for auto-importing cards by player tag)

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
2. Click **Analyze** — the AI searches the current meta and builds 3 optimized decks from your collection
3. Click any deck to see detailed strategy, synergies, and matchup tips
4. Use the chat to ask follow-up questions about a specific deck

### Analyze a Saved Deck

1. Go to **Saved Decks** and create or import a deck
2. Click **Analyze** — the AI evaluates it against the current meta and gives a tier rating, strengths/weaknesses, and swap suggestions
3. Use the fine-tune chat to explore specific improvements

## Stack

- **Backend:** Python / Flask
- **AI:** Claude claude-opus-4-6 with extended thinking + web search
- **Database:** SQLite (via `db.py`)
- **Frontend:** Vanilla JS + CSS

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/all-cards` | List all Clash Royale cards |
| GET | `/api/fetch-cards/<player_tag>` | Fetch a player's card collection |
| POST | `/api/analyze` | Stream deck recommendations (SSE) |
| GET/POST | `/api/saved-decks` | List / create saved decks |
| GET/PUT/DELETE | `/api/saved-decks/<id>` | Get / update / delete a saved deck |
| POST | `/api/saved-decks/<id>/analysis` | Stream deep deck analysis (SSE) |
| GET/POST | `/api/saved-decks/<id>/chat` | Get / post fine-tune chat messages |
