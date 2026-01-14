
import time
from datetime import datetime, timezone
import html
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup

UPDATES_URL = "https://azure.microsoft.com/en-us/updates/"

st.set_page_config(page_title="Azure Updates — Launched", page_icon="🚀", layout="wide")
st.title("🚀 Azure Updates — Launched (Newest → Oldest)")
st.caption("Source: Azure Updates webpage (scraped)")

# ----------------------------- Helpers ----------------------------------------
@st.cache_data(ttl=60 * 30)  # cache for 30 minutes
def fetch_updates_page(url: str) -> str:
    headers = {"User-Agent": "Streamlit-App (Azure-Updates-Launched)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text

def parse_updates(html_text: str):
    """
    Parse the Azure Updates page and return a list of dicts:
    {
      'status': 'Launched' | 'In preview' | ...,
      'title': str,
      'date': datetime (UTC),
      'tags': [str],
      'link': str,
      'description_html': str
    }
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # The page is built with cards; selectors may change if Microsoft updates the markup.
    # We'll search generically for card-like elements that include status, title, date.
    updates = []

    # Common containers: divs with data attributes or known classes.
    # Try several patterns to be robust.
    # Pattern A: Modern card list items
    card_candidates = soup.select("li, div")
    for el in card_candidates:
        # Identify card elements by the presence of a status label and title link
        status_el = el.select_one('[class*="status"], [class*="Status"], .status, .azure-status, .update-status')
        title_el = el.select_one("a[href*='/updates/'], a[href*='azure.microsoft.com/en-us/updates']")
        date_el = el.find(lambda tag: tag.name in ["time", "div", "span"] and ("date" in (tag.get("class") or []) or re.search(r"\b\d{4}\b", tag.get_text(strip=True) or "")))
        desc_el = el.select_one("p, .description, [class*='description'], [class*='summary']")

        if not title_el or not status_el:
            continue

        # Extract fields
        status = status_el.get_text(strip=True)
        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")
        if link and link.startswith("/"):
            link = "https://azure.microsoft.com" + link

        # Tags/categories (optional—often shown as chips)
        tag_els = el.select('[class*="tag"], [class*="chip"], .azure-tag, .category, a[href*="/topics/"]')
        tags = list({t.get_text(strip=True) for t in tag_els if t.get_text(strip=True)})

        # Parse date (Azure Updates cards print human-readable dates; fallback to now if absent)
        date_dt = None
        dt_text = ""
        if date_el:
            dt_text = date_el.get_text(strip=True)
        # Try strong patterns like 'December 2025', 'Dec 5, 2025', etc.
        parsed = None
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%B %Y", "%b %Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(dt_text, fmt).replace(tzinfo=timezone.utc)
                break
            except Exception:
                continue
        date_dt = parsed or datetime.fromtimestamp(0, tz=timezone.utc)

        description_html = ""
        if desc_el:
            # Keep original HTML fragment for richer rendering
            description_html = str(desc_el)

        updates.append({
            "status": status,
            "title": title,
            "date": date_dt,
            "tags": tags,
            "link": link,
            "description_html": description_html
        })

    return updates

def is_launched(status_text: str) -> bool:
    return bool(re.search(r"\blaunched\b", (status_text or "").lower()))

# ----------------------------- Fetch & Parse ----------------------------------
with st.spinner("Fetching Azure Updates page…"):
    try:
        html_text = fetch_updates_page(UPDATES_URL)
    except Exception as e:
        st.error(f"Failed to load the updates page: {e}")
        st.stop()

updates = parse_updates(html_text)

launched = [u for u in updates if is_launched(u.get("status", ""))]
launched.sort(key=lambda x: x["date"], reverse=True)

# ----------------------------- Header -----------------------------------------
cols = st.columns([1, 1, 2])
with cols[0]:
    st.metric("Launched items found", len(launched))
with cols[1]:
    st.caption(f"Scraped at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
with cols[2]:
    st.caption("If Microsoft changes the page layout, selectors may need updates.")

st.divider()

# ----------------------------- Render -----------------------------------------
if not launched:
    st.info("No 'Launched' items detected on the page.")
else:
    for u in launched:
        with st.container():
            st.subheader(u["title"])
            meta_cols = st.columns([1.2, 1, 2])
            with meta_cols[0]:
                if u["link"]:
                    st.markdown(f"**Link:** {u['link']}")
            with meta_cols[1]:
                st.markdown(f"**Published:** {u['date'].strftime('%Y-%m-%d %H:%M UTC') if u['date'] else '—'}")
            with meta_cols[2]:
                if u["tags"]:
                    st.markdown("**Tags:** " + ", ".join(u["tags"]))

            if u["description_html"]:
                st.markdown(html.unescape(u["description_html"]), unsafe_allow_html=True)
            else:
                st.caption("_No description block found on the card; open the link for full details._")

            st.divider()
