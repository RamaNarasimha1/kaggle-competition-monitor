# Kaggle Competition Monitor 🏆

Automatically discovers, scores, and delivers high-quality Kaggle competitions
to your Telegram — twice a day, with zero spam.

---

## Features

- Fetches all active Kaggle competitions via the official API
- Enriches each competition with dataset metadata (size, file types, modality)
- 100-point scoring engine across 6 dimensions
- Duplicate detection — never notifies the same competition twice
- Rich Telegram notifications with detailed breakdown
- GitHub Actions automation (runs at 09:00 and 21:00 UTC daily)

---

## Project structure

```
kaggle-competition-monitor/
├── src/
│   ├── kaggle_client.py      # Kaggle API wrapper + competition normalization
│   ├── dataset_analyzer.py   # Metadata enrichment (no downloads)
│   ├── scorer.py             # 100-point scoring engine
│   ├── storage.py            # Seen-competition deduplication (JSON)
│   └── telegram_bot.py       # Message formatting + Telegram delivery
├── data/
│   └── seen_competitions.json
├── tests/
│   └── test_scorer.py
├── main.py                   # Pipeline entry point
├── requirements.txt
├── .env.example
└── .github/workflows/monitor.yml
```

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/kaggle-competition-monitor
cd kaggle-competition-monitor
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your Kaggle and Telegram credentials
```

**Kaggle API key**: [kaggle.com/settings](https://www.kaggle.com/settings) → API → Create New Token

**Telegram Bot Token**: Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot`

**Telegram Chat ID**: Message [@userinfobot](https://t.me/userinfobot) on Telegram

### 3. Test locally

```bash
# Dry-run: score everything, print results, no Telegram
python main.py --dry-run

# Test that Telegram is configured correctly
python main.py --test-telegram

# Full run
python main.py
```

### 4. Run tests

```bash
python -m pytest tests/ -v
```

---

## Scoring breakdown

| Dimension       | Points | Description                                    |
|-----------------|--------|------------------------------------------------|
| Relevance       | 30     | Keyword match: CV, NLP, LLM, DL, etc.         |
| Portfolio value | 20     | Real-world impact, org prestige, research fit  |
| Prize           | 15     | Cash reward tier                               |
| Feasibility     | 15     | Dataset size vs consumer hardware              |
| Time remaining  | 10     | Days until deadline                            |
| Competition     | 10     | Team count sweet-spot                          |
| **Total**       | **100**|                                                |

**Notification threshold**: ≥ 75 points (🟢 Strong or 🔥 Excellent)

---

## Notification categories

| Score   | Label         |
|---------|---------------|
| 90–100  | 🔥 Excellent  |
| 75–89   | 🟢 Strong     |
| 60–74   | 🟡 Consider   |
| < 60    | ⚪ Ignore     |

---

## GitHub Actions setup

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Add these secrets:
   - `KAGGLE_USERNAME`
   - `KAGGLE_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. The workflow runs automatically at 09:00 and 21:00 UTC
5. Trigger manually via **Actions → Kaggle Competition Monitor → Run workflow**

---

## CLI flags

```
python main.py --dry-run         Score everything, print, no Telegram
python main.py --test-telegram   Send connectivity test and exit
python main.py --list-seen       Print all previously seen competition IDs
```

---

## Environment variables

| Variable            | Required | Default | Description                                |
|---------------------|----------|---------|--------------------------------------------|
| `KAGGLE_USERNAME`   | ✅       | —       | Your Kaggle username                       |
| `KAGGLE_KEY`        | ✅       | —       | Your Kaggle API key                        |
| `TELEGRAM_BOT_TOKEN`| ✅       | —       | Bot token from @BotFather                  |
| `TELEGRAM_CHAT_ID`  | ✅       | —       | Comma-separated recipient chat IDs         |
| `MAX_PAGES`         | —        | `3`     | Pages of Kaggle results to fetch (100/page)|
| `MIN_SCORE`         | —        | `75`    | Minimum score to trigger notification      |

---

## V2 roadmap

- SQLite storage backend
- Leaderboard change tracking
- Deadline approaching reminders
- Prize/description change detection
- Streamlit dashboard
- DrivenData / Zindi / AIcrowd support
