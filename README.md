# 🚀 Azure Updates — Launched

A Streamlit web app that tracks **newly launched Azure services and features** in real time, pulling directly from Microsoft's official Azure Release Communications RSS feed.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://azure-updates.streamlit.app/)

---

## What It Does

This app fetches the Azure Updates RSS feed, filters it to show only items tagged **[Launched]**, and presents them in a clean, searchable dashboard sorted newest to oldest. It's a quick way to stay on top of what's actually gone GA in Azure without wading through previews and announcements.

**Key features:**

- **Live RSS ingestion** — pulls from `microsoft.com/releasecommunications/api/v2/azure/rss` with a 30-minute cache
- **[Launched] filter** — shows only updates that are fully released (no previews or in-progress items)
- **Date range filter** — narrow results to a specific time window via sidebar
- **Full-text search** — filter by keyword across titles and descriptions
- **Status detection** — automatically classifies updates as Generally Available, Public Preview, Private Preview, or Retired based on content
- **Tag display** — shows Azure service categories per update
- **Expandable descriptions** — click to reveal the full update text without cluttering the feed
- **One-click refresh** — clears the cache and re-fetches the latest data

---

## Project Structure

```
Azure_Updates/
├── streamlit_app.py      # Main application
├── requirements.txt      # Python dependencies
├── .devcontainer/        # Dev container config (VS Code / Codespaces)
├── .github/              # GitHub Actions workflows
├── .gitignore
└── LICENSE               # Apache 2.0
```

---

## Getting Started

### Prerequisites

- Python 3.9+

### Installation

1. Clone the repository:

```bash
git clone https://github.com/HashimsGitHub/Azure_Updates.git
cd Azure_Updates
```

2. Install the dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
streamlit run streamlit_app.py
```

The app will open at `http://localhost:8501`.

---

## Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web app framework and UI |
| `feedparser` | Parses the Azure RSS feed |
| `requests` | HTTP requests |
| `beautifulsoup4` | Strips HTML from feed descriptions |

---

## How It Works

1. On load, `feedparser` fetches the Microsoft Azure RSS feed and caches the result for 30 minutes.
2. Each entry is parsed for title, date, link, tags, and description (HTML is stripped via BeautifulSoup).
3. Entries are filtered to only those with `[Launched]` in the title.
4. A regex pass over each entry's text classifies its status (GA, Public Preview, etc.).
5. Results are sorted newest-first and rendered with Streamlit's component layout — metrics bar at the top, filterable card list below.

---

## License

Licensed under the [Apache 2.0 License](LICENSE).
