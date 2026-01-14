
import time
from datetime import datetime, timezone
import html
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup

# Filtered "Launched" URL
UPDATES_URL = 'https://azure.microsoft.com/en-us/updates?filters=["Launched"]'

st.set_page_config(page_title="Azure Updates — Launched", page_icon="🚀", layout="wide")
st.title("🚀 Azure Updates — Launched (Newest → Oldest)")
st.caption("Source: Azure Updates (filtered to Launched)")

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
      'status': 'Launched',
      'title': str,
      'date': datetime (UTC),
      'tags': [str],
      'link': str,
      'description_html': str
    }
    """
    soup = BeautifulSoup(html_text, "html.parser")
    updates = []

    # Heuristic selectors for update cards.
    # Microsoft may change classes/structure; adjust if needed.
    # Strategy: find anchors to individual update pages, then walk up to the card container.
    for a in soup.select('a[href*="/updates/"]'):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue

        link = href if href.startswith("http") else "https://azure.microsoft.com" + href

        # Card container (walk up a few levels)
        container = a
        for _ in range(3):
            if container and container.parent:
                container = container.parent

        # Status label (page is pre-filtered to Launched, but we read it anyway)
        status_el = None
        # Common status class names
        for sel in ('.status', '[class*="status"]', '.azure-status', '.update-status'):
            status_el = container.select_one(sel)
            if status_el:
                break
        status = (status_el.get_text(strip=True) if status_el else "Launched")

        # Date element (try <time> first)
        date_dt = datetime.fromtimestamp(0, tz=timezone.utc)
        date_el = container.select_one("time")
        if date_el and date_el.get("datetime"):
            try:
                date_dt = datetime.fromisoformat(date_el["datetime"].replace("Z", "+00:00"))
            except Exception:
                pass
        else:
            # Fallback: text-based date inside spans/divs
            date_text_el = container.find(lambda tag: tag.name in ["div", "span"] and re.search(r"\b\d{4}\b", tag.get_text(strip=True) or ""))
            dt_text = date_text_el.get_text(strip=True) if date_text_el else ""
            parsed = None
            for fmt in ("%b %d, %Y", "%B %d, %Y", "%B %Y", "%b %Y", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(dt_text, fmt).replace(tzinfo=timezone.utc)
                    break
                except Exception:
                    continue
            date_dt = parsed or date_dt

        # Tags
        tag_els = container.select('[class*="tag"], [class*="chip"], .category, a[href*="/topics/"]')
        tags = list({t.get_text(strip=True) for t in tag_els if t.get_text(strip=True)})

        # Description/summary block
        desc_el = None
        for sel in ("p", ".description", "[class*='description']", "[class*='summary']"):
            desc_el = container.select_one(sel)
            if desc_el:
                break
        description_html = str(desc_el) if desc_el else ""

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
with st.spinner("Fetching Azure Updates (Launched)…"):
    try:
        html_text = fetch_updates_page(UPDATES_URL)
    except Exception as e:
        st.error(f"Failed to load the updates page: {e}")
        st.stop()

updates = parse_updates(html_text)

# Even though the page is pre-filtered, double-check status.
launched = [u for u in updates if is_launched(u.get("status", "Launched"))]
# Sort newest → oldest
launched.sort(key=lambda x: x["date"], reverse=True)

# ----------------------------- Header -----------------------------------------
cols = st.columns([1, 1, 2])
with cols[0]:
    st.metric("Launched items found", len(launched))
with cols[1]:
    st.caption(f"Scraped at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
with cols[2]:
    st.caption("If Microsoft changes the page layout or filters, selectors may need updates.")

st.divider()

# ----------------------------- Render -----------------------------------------
if not launched:
    st.info("No 'Launched' items detected on the page.")
else:
    for u in launched:
        with st.container():
            st.subheader(u["title"])
            meta_cols = st.columns([1.3, 1, 2])
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
