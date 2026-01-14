
import time
from datetime import datetime, timezone
import html
import re
import feedparser
import requests
import streamlit as st

FEED_URL = "https://www.microsoft.com/releasecommunications/api/v2/azure/rss"

st.set_page_config(page_title="Azure Updates — Launched", page_icon="🚀", layout="wide")
st.title("🚀 Azure Updates — Launched (Newest → Oldest)")
st.caption("Source: Microsoft Release Communications (Azure) RSS")

# ---- Helper functions --------------------------------------------------------
@st.cache_data(ttl=60 * 30)  # cache for 30 minutes
def fetch_feed(url: str):
    """
    Fetch RSS with a short timeout, return feedparser-parsed structure.
    """
    headers = {
        "User-Agent": "Streamlit-App (Azure-Updates-Launched)"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return feedparser.parse(resp.content)

def is_launched(entry):
    """
    Determine if entry is 'Launched'.
    Strategy:
      1) Check entry title prefix like '[Launched] ...'
      2) Check tags/categories if present.
      3) Fallback: look for 'Launched' anywhere in title or summary.
    """
    title = entry.get("title", "") or ""
    summary = entry.get("summary", "") or ""
    tags = entry.get("tags", []) or []

    title_clean = title.strip()
    summary_clean = summary.strip()

    # Some entries come with a status prefix in square brackets.
    if title_clean.lower().startswith("[launched]") or "[Launched]" in title_clean:
        return True

    # Check categories/tags
    for t in tags:
        # feedparser normalizes tags with "term"
        term = (t.get("term") or "").lower()
        if term == "launched":
            return True

    # Fallback heuristic
    if re.search(r"\blaunched\b", title_clean.lower()) or re.search(r"\blaunched\b", summary_clean.lower()):
        return True

    return False

def entry_published_dt(entry):
    """
    Robustly get publication datetime (UTC). If missing, return epoch 0 for sorting last.
    """
    # feedparser may provide 'published_parsed' as time.struct_time
    if entry.get("published_parsed"):
        return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
    # Some feeds use 'updated_parsed'
    if entry.get("updated_parsed"):
        return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
    # If only ISO strings present
    for key in ("published", "updated"):
        if entry.get(key):
            try:
                # Attempt to parse common ISO formats
                return datetime.fromisoformat(entry[key].replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.fromtimestamp(0, tz=timezone.utc)

# ---- Fetch and filter --------------------------------------------------------
with st.spinner("Fetching Azure 'Launched' updates…"):
    try:
        feed = fetch_feed(FEED_URL)
        entries = feed.get("entries", []) or []
    except Exception as e:
        st.error(f"Failed to load RSS: {e}")
        st.stop()

launched_entries = [e for e in entries if is_launched(e)]
# Sort newest → oldest by published date
launched_entries.sort(key=entry_published_dt, reverse=True)

# ---- Controls ----------------------------------------------------------------
left, right = st.columns([1, 1])
with left:
    st.metric("Launched items", len(launched_entries))
with right:
    # Show last updated time from the feed if present, else now
    last_build = feed.get("feed", {}).get("updated") or feed.get("feed", {}).get("published")
    last_build_dt = None
    if last_build:
        try:
            last_build_dt = datetime.fromisoformat(last_build.replace("Z", "+00:00"))
        except Exception:
            pass
    st.caption(
        f"Last feed update: {last_build_dt.isoformat() if last_build_dt else datetime.now(timezone.utc).isoformat()}"
    )

st.divider()

# ---- Rendering ---------------------------------------------------------------
if not launched_entries:
    st.info("No 'Launched' items found in the current feed.")
else:
    for e in launched_entries:
        pub_dt = entry_published_dt(e)
        title = e.get("title", "Untitled")
        link = e.get("link") or e.get("id") or ""
        summary = e.get("summary", "")
        tags = ", ".join([t.get("term", "") for t in e.get("tags", []) if t.get("term")])

        with st.container():
            st.subheader(f"{title}")
            meta_cols = st.columns([1.2, 1, 1])
            with meta_cols[0]:
                if link:
                    st.markdown(f"**Link:** [{link}]({link})")
            with meta_cols[1]:
                st.markdown(f"**Published:** {pub_dt.strftime('%Y-%m-%d %H:%M UTC')}")
            with meta_cols[2]:
                if tags:
                    st.markdown(f"**Tags:** {tags}")

            if summary:
                # Summaries may contain HTML; lightly sanitize/unescape
                st.markdown(html.unescape(summary), unsafe_allow_html=True)

            st.divider()
``
