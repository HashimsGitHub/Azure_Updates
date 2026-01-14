
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

# ---- Controls ----------------------------------------------------------------
st.sidebar.header("Options")
attempt_http_fulltext = st.sidebar.checkbox(
    "Try to fetch full text from article page when feed lacks it",
    value=False,
    help="If the RSS item doesn't include full content, try retrieving the main text from the linked page."
)


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
    if entry.get("published_parsed"):
        return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
    if entry.get("updated_parsed"):
        return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
    for key in ("published", "updated"):
        if entry.get(key):
            try:
                return datetime.fromisoformat(entry[key].replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.fromtimestamp(0, tz=timezone.utc)

@st.cache_data(ttl=60 * 30)
def fetch_page(url: str) -> str:
    """
    Fetch raw HTML from a page with a short timeout.
    """
    headers = {
        "User-Agent": "Streamlit-App (Azure-Updates-Launched)"
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.text

def extract_fulltext_from_entry(entry) -> str:
    """
    Prefer full text from the feed (e.g., content:encoded via feedparser -> entry.content[].value).
    Fallback to summary. Optionally attempt best-effort page extraction.
    """
    # 1) Prefer content:encoded (feedparser exposes it via entry.content if available)
    content_blocks = entry.get("content") or []
    for c in content_blocks:
        val = c.get("value", "")
        if val and val.strip():
            # Full text often includes HTML; return as-is
            return val

    # 2) Fallback to summary from the feed
    summary = entry.get("summary", "")
    if summary and summary.strip():
        return summary

    # 3) Optional: fetch linked page and attempt a simple heuristic extraction
    if attempt_http_fulltext:
        url = entry.get("link") or entry.get("id") or ""
        if url:
            try:
                html_text = fetch_page(url)

                # --- Simple heuristic ---
                # Try to locate main content blocks likely used on Azure Updates pages.
                # This is intentionally minimal (no heavy parsing libs) to keep requirements light.
                # We search for article-like sections and remove script/style tags.
                cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", "", html_text)
                # Try to find a main content region by common containers
                candidates = re.findall(
                    r'(?is)<(article|main|section|div)[^>]*(?:id|class)="[^"]*(content|article|main|post|update)[^"]*"[^>]*>(.*?)</\\1>',
                    cleaned
                )
                if candidates:
                    # Pick the largest candidate body
                    largest = max(candidates, key=lambda x: len(x[2]))[2]
                    return largest

                # If no match, return the entire cleaned HTML (last resort)
                return cleaned
            except Exception:
                pass

    # 4) Nothing usable
    return ""

# ---- Fetch and filter --------------------------------------------------------
with st.spinner("Fetching Azure 'Launched' updates…"):
    try:
        feed = fetch_feed(FEED_URL)
        entries = feed.get("entries", []) or []
    except Exception as e:
        st.error(f"Failed to load RSS: {e}")
        st.stop()

launched_entries = [e for e in entries if is_launched(e)]
launched_entries.sort(key=entry_published_dt, reverse=True)

# ---- Header stats ------------------------------------------------------------
left, right = st.columns([1, 1])
with left:
    st.metric("Launched items", len(launched_entries))
with right:
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
        tags = ", ".join([t.get("term", "") for t in e.get("tags", []) if t.get("term")])

        with st.container():
            st.subheader(f"{title}")
            meta_cols = st.columns([1.2, 1, 1])
            with meta_cols[0]:
                if link:
                    st.markdown(f"**Link:** {link}")
            with meta_cols[1]:
                st.markdown(f"**Published:** {pub_dt.strftime('%Y-%m-%d %H:%M UTC')}")
            with meta_cols[2]:
                if tags:
                    st.markdown(f"**Tags:** {tags}")

            full_text_html = extract_fulltext_from_entry(e)
            if full_text_html and full_text_html.strip():
                st.markdown(html.unescape(full_text_html), unsafe_allow_html=True)
            else:
                st.warning("No full text available for this item.")

            st.divider()
