import re
from datetime import datetime, timezone
import streamlit as st
import feedparser
import requests
from bs4 import BeautifulSoup

# Azure Updates RSS Feed
RSS_URL = 'https://www.microsoft.com/releasecommunications/api/v2/azure/rss'

st.set_page_config(page_title="Azure Updates — Launched", page_icon="🚀", layout="wide")
st.title("🚀 Azure Updates — All Updates (Newest → Oldest)")
st.caption("Source: Azure Release Communications RSS Feed")

# ----------------------------- Helpers ----------------------------------------
@st.cache_data(ttl=60 * 30, show_spinner=False)  # cache for 30 minutes
def fetch_rss_feed(url: str):
    """Fetch and parse the Azure RSS feed."""
    try:
        feed = feedparser.parse(url)
        return feed
    except Exception as e:
        st.error(f"Error fetching RSS feed: {e}")
        return None

def clean_html(html_content: str) -> str:
    """Remove HTML tags and clean up text."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text()
    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    return text

def parse_feed_entry(entry):
    """Parse a single RSS feed entry into structured data."""
    # Title
    title = entry.get('title', 'Untitled')
    
    # Link
    link = entry.get('link', '')
    
    # Published date
    date_dt = None
    if 'published_parsed' in entry and entry.published_parsed:
        try:
            date_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except:
            pass
    
    if not date_dt and 'published' in entry:
        try:
            date_dt = datetime.fromisoformat(entry.published.replace('Z', '+00:00'))
        except:
            pass
    
    if not date_dt:
        date_dt = datetime.now(timezone.utc)
    
    # Summary/Description
    summary_html = entry.get('summary', '')
    summary_text = clean_html(summary_html)
    
    # Content (might be more complete than summary)
    content_html = ''
    if 'content' in entry and entry.content:
        content_html = entry.content[0].value if isinstance(entry.content, list) else entry.content
    
    description = content_html if content_html else summary_html
    description_text = clean_html(description)
    
    # Tags/Categories
    tags = []
    if 'tags' in entry:
        tags = [tag.term for tag in entry.tags if hasattr(tag, 'term')]
    
    # Try to extract status from title or content
    status = "Update"
    status_patterns = [
        (r'\b(generally available|GA)\b', 'Generally Available'),
        (r'\b(public preview)\b', 'Public Preview'),
        (r'\b(private preview)\b', 'Private Preview'),
        (r'\b(launched?)\b', 'Launched'),
        (r'\b(available)\b', 'Available'),
        (r'\b(retired?|retirement)\b', 'Retired'),
    ]
    
    search_text = f"{title} {description_text}".lower()
    for pattern, status_name in status_patterns:
        if re.search(pattern, search_text, re.IGNORECASE):
            status = status_name
            break
    
    return {
        'title': title,
        'link': link,
        'date': date_dt,
        'status': status,
        'tags': tags,
        'description_html': description,
        'description_text': description_text[:500],  # First 500 chars
    }

# ----------------------------- Fetch & Parse ----------------------------------
with st.spinner("Fetching Azure Updates from RSS feed…"):
    feed = fetch_rss_feed(RSS_URL)
    
    if not feed or not feed.entries:
        st.error("Failed to fetch RSS feed or no entries found.")
        st.info("The RSS feed might be temporarily unavailable. Try again later.")
        st.stop()

# Parse all entries
updates = [parse_feed_entry(entry) for entry in feed.entries]

# Sort by date (newest first)
updates.sort(key=lambda x: x['date'], reverse=True)

# ----------------------------- Filters ----------------------------------------
st.sidebar.header("🔍 Filters")

# Status filter
all_statuses = sorted(set(u['status'] for u in updates))
selected_statuses = st.sidebar.multiselect(
    "Filter by Status",
    options=all_statuses,
    default=all_statuses
)

# Date range filter
if updates:
    min_date = min(u['date'] for u in updates).date()
    max_date = max(u['date'] for u in updates).date()
    
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # Handle single date vs range
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range if not isinstance(date_range, tuple) else date_range[0]

# Search filter
search_query = st.sidebar.text_input("🔎 Search in title/description")

# Apply filters
filtered_updates = updates

if selected_statuses:
    filtered_updates = [u for u in filtered_updates if u['status'] in selected_statuses]

if updates:
    filtered_updates = [
        u for u in filtered_updates 
        if start_date <= u['date'].date() <= end_date
    ]

if search_query:
    query_lower = search_query.lower()
    filtered_updates = [
        u for u in filtered_updates 
        if query_lower in u['title'].lower() or query_lower in u['description_text'].lower()
    ]

# ----------------------------- Header -----------------------------------------
cols = st.columns([1, 1, 1, 1])
with cols[0]:
    st.metric("Total Updates", len(updates))
with cols[1]:
    st.metric("Filtered", len(filtered_updates))
with cols[2]:
    st.caption(f"Scraped: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
with cols[3]:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ----------------------------- Render -----------------------------------------
if not filtered_updates:
    st.info("No updates match your current filters. Try adjusting the filters in the sidebar.")
else:
    for idx, update in enumerate(filtered_updates):
        with st.container():
            # Header row
            col1, col2 = st.columns([5, 1])
            with col1:
                st.subheader(f"{idx + 1}. {update['title']}")
            with col2:
                if update['link']:
                    st.markdown(f"[🔗 View]({update['link']})")
            
            # Metadata row
            meta_cols = st.columns([2, 2, 3])
            with meta_cols[0]:
                date_str = update['date'].strftime('%b %d, %Y')
                st.caption(f"📅 **Date:** {date_str}")
            with meta_cols[1]:
                status_colors = {
                    'Generally Available': '🟢',
                    'Launched': '🟢',
                    'Available': '🟢',
                    'Public Preview': '🔵',
                    'Private Preview': '🟡',
                    'Retired': '🔴',
                }
                icon = status_colors.get(update['status'], '⚪')
                st.caption(f"{icon} **Status:** {update['status']}")
            with meta_cols[2]:
                if update['tags']:
                    tags_str = ", ".join(update['tags'][:3])
                    if len(update['tags']) > 3:
                        tags_str += f" +{len(update['tags']) - 3} more"
                    st.caption(f"🏷️ **Tags:** {tags_str}")
            
            # Description
            if update['description_text']:
                with st.expander("📄 View Description", expanded=False):
                    # Show cleaned text version
                    st.write(update['description_text'])
                    if len(update['description_text']) >= 499:
                        st.caption("_Click the link above for full details_")
            
            st.divider()

# ----------------------------- Footer -----------------------------------------
st.sidebar.divider()
st.sidebar.caption(f"💾 Data cached for 30 minutes")
st.sidebar.caption(f"📊 Feed contains {len(feed.entries)} total entries")