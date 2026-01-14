import time
from datetime import datetime, timezone
import html
import re
import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

# Filtered "Launched" URL
UPDATES_URL = 'https://azure.microsoft.com/en-us/updates?filters=["Launched"]'

st.set_page_config(page_title="Azure Updates — Launched", page_icon="🚀", layout="wide")
st.title("🚀 Azure Updates — Launched (Newest → Oldest)")
st.caption("Source: Azure Updates (filtered to Launched)")

# ----------------------------- Helpers ----------------------------------------
@st.cache_data(ttl=60 * 30, show_spinner=False)  # cache for 30 minutes
def fetch_updates_page(url: str) -> str:
    """
    Fetch the Azure Updates page using Playwright to handle dynamic content.
    """
    try:
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            # Navigate to the page
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for content to load - try multiple possible selectors
            try:
                page.wait_for_selector('article, div[class*="update"], a[href*="/updates/"]', timeout=15000)
            except PlaywrightTimeout:
                st.warning("Page took longer than expected to load. Proceeding anyway...")
            
            # Scroll to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Get the HTML content
            html_content = page.content()
            
            browser.close()
            return html_content
            
    except Exception as e:
        st.error(f"Error fetching page: {e}")
        return ""

def parse_updates(html_text: str):
    """
    Parse the Azure Updates page and return a list of dicts.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    updates = []
    
    # Find all links to individual update pages
    update_links = soup.select('a[href*="/updates/"]')
    
    seen_links = set()
    
    for link in update_links:
        href = link.get("href", "")
        if not href or href in seen_links:
            continue
        
        # Skip navigation links, just focus on actual updates
        if '/updates/?query=' in href or '/updates/#' in href or href.endswith('/updates/') or href.endswith('/updates'):
            continue
            
        seen_links.add(href)
        
        # Get title
        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        
        full_link = href if href.startswith("http") else "https://azure.microsoft.com" + href
        
        # Find the parent container (walk up the tree)
        container = link
        for _ in range(6):
            if container and container.parent:
                container = container.parent
                # Stop at likely container elements
                if container.name in ['article', 'li'] or (
                    container.name == 'div' and container.get('class') and 
                    any('card' in c.lower() or 'item' in c.lower() for c in container.get('class', []))
                ):
                    break
        
        # Extract status
        status_el = container.select_one('[class*="status"], [class*="badge"], span[class*="tag"]')
        status = status_el.get_text(strip=True) if status_el else "Launched"
        
        # Extract date
        date_dt = None
        
        # Try <time> element first
        time_el = container.select_one("time")
        if time_el:
            dt_str = time_el.get("datetime") or time_el.get_text(strip=True)
            try:
                # Handle ISO format
                date_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except:
                # Try parsing text date
                for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y", "%Y-%m-%d"):
                    try:
                        date_dt = datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
                        break
                    except:
                        continue
        
        # Fallback: search container text for dates
        if not date_dt:
            container_text = container.get_text()
            date_patterns = [
                (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', "%B %d, %Y"),
                (r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b', "%b %d, %Y"),
                (r'\b\d{4}-\d{2}-\d{2}\b', "%Y-%m-%d"),
            ]
            for pattern, fmt in date_patterns:
                match = re.search(pattern, container_text)
                if match:
                    try:
                        date_dt = datetime.strptime(match.group(0).replace(',', ''), fmt).replace(tzinfo=timezone.utc)
                        break
                    except:
                        continue
        
        if not date_dt:
            date_dt = datetime.now(timezone.utc)
        
        # Extract tags/categories
        tag_elements = container.select('[class*="category"], [class*="tag"]:not([class*="status"]), [class*="chip"]')
        tags = []
        for tag_el in tag_elements:
            tag_text = tag_el.get_text(strip=True)
            if tag_text and len(tag_text) < 50 and tag_text.lower() not in ['launched', 'preview', 'available']:
                tags.append(tag_text)
        tags = list(dict.fromkeys(tags))  # Remove duplicates while preserving order
        
        # Extract description
        desc_el = container.select_one('p, div[class*="description"], div[class*="summary"], div[class*="excerpt"]')
        description_html = str(desc_el) if desc_el else ""
        
        updates.append({
            "status": status,
            "title": title,
            "date": date_dt,
            "tags": tags,
            "link": full_link,
            "description_html": description_html
        })
    
    return updates

def is_launched(status_text: str) -> bool:
    """Check if status indicates launched/available."""
    return bool(re.search(r"\b(launched|available|ga|general availability)\b", (status_text or "").lower()))

# ----------------------------- Fetch & Parse ----------------------------------
with st.spinner("Fetching Azure Updates (this may take 10-20 seconds)…"):
    try:
        html_text = fetch_updates_page(UPDATES_URL)
        if not html_text:
            st.error("Failed to fetch page content.")
            st.stop()
    except Exception as e:
        st.error(f"Failed to load the updates page: {e}")
        st.info("💡 Make sure Playwright is installed: `pip install playwright && playwright install chromium`")
        st.stop()

updates = parse_updates(html_text)

# Filter and sort
launched = [u for u in updates if is_launched(u.get("status", "Launched")) or "Launched" in UPDATES_URL]
# Remove duplicates by link
seen = set()
unique_launched = []
for u in launched:
    if u["link"] not in seen:
        seen.add(u["link"])
        unique_launched.append(u)
launched = unique_launched

# Sort newest → oldest
launched.sort(key=lambda x: x["date"], reverse=True)

# ----------------------------- Header -----------------------------------------
cols = st.columns([1, 1, 2])
with cols[0]:
    st.metric("Launched items found", len(launched))
with cols[1]:
    st.caption(f"Scraped at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
with cols[2]:
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ----------------------------- Render -----------------------------------------
if not launched:
    st.warning("No 'Launched' items detected. The page structure may have changed.")
    st.info("💡 Try the refresh button or check https://azure.microsoft.com/en-us/updates manually.")
else:
    for idx, u in enumerate(launched):
        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.subheader(f"{idx + 1}. {u['title']}")
            with col2:
                st.markdown(f"[🔗 View]({u['link']})")
            
            meta_cols = st.columns([1, 1, 2])
            with meta_cols[0]:
                date_str = u['date'].strftime('%b %d, %Y') if u['date'] else '—'
                st.caption(f"📅 {date_str}")
            with meta_cols[1]:
                st.caption(f"🏷️ {u['status']}")
            with meta_cols[2]:
                if u["tags"]:
                    st.caption("**Categories:** " + ", ".join(u["tags"][:5]))

            if u["description_html"]:
                try:
                    st.markdown(html.unescape(u["description_html"]), unsafe_allow_html=True)
                except:
                    st.caption("_Description available at link_")
            
            st.divider()