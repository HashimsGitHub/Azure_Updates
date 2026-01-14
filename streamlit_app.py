import time
from datetime import datetime, timezone
import html
import re
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
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
    Fetch the Azure Updates page using Selenium to handle dynamic content.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = None
    try:
        # Initialize the Chrome driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Load the page
        driver.get(url)
        
        # Wait for update cards to load (adjust selector as needed)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='update'], article, .card")))
        
        # Scroll to load more content if pagination exists
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Get the page source
        html_content = driver.page_source
        return html_content
        
    except Exception as e:
        st.error(f"Error fetching page with Selenium: {e}")
        return ""
    finally:
        if driver:
            driver.quit()

def parse_updates(html_text: str):
    """
    Parse the Azure Updates page and return a list of dicts.
    Updated selectors to match actual Azure Updates page structure.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    updates = []
    
    # Try multiple selector strategies
    # Strategy 1: Look for article tags or update containers
    containers = soup.select('article, div[class*="update-item"], div[class*="card"]')
    
    if not containers:
        # Strategy 2: Find all links to update pages
        links = soup.select('a[href*="/updates/"]')
        for link in links:
            # Get parent container
            container = link.parent
            for _ in range(5):  # Walk up tree
                if container and container.parent:
                    container = container.parent
                    if container.name in ['article', 'div', 'section']:
                        if container not in containers:
                            containers.append(container)
                        break
    
    for container in containers:
        # Find title and link
        title_link = container.select_one('a[href*="/updates/"]')
        if not title_link:
            continue
            
        title = title_link.get_text(strip=True)
        href = title_link.get("href", "")
        
        if not title or not href:
            continue
        
        link = href if href.startswith("http") else "https://azure.microsoft.com" + href
        
        # Status
        status_el = container.select_one('[class*="status"], [class*="badge"], [class*="tag"]')
        status = status_el.get_text(strip=True) if status_el else "Launched"
        
        # Date
        date_dt = None
        time_el = container.select_one("time")
        if time_el:
            dt_attr = time_el.get("datetime") or time_el.get_text(strip=True)
            try:
                date_dt = datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
            except:
                pass
        
        if not date_dt:
            # Try to find date in text
            date_patterns = [
                r'\b(\w+ \d{1,2}, \d{4})\b',
                r'\b(\w+ \d{4})\b',
                r'\b(\d{4}-\d{2}-\d{2})\b'
            ]
            text = container.get_text()
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    date_str = match.group(1)
                    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y", "%Y-%m-%d"):
                        try:
                            date_dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                            break
                        except:
                            continue
                    if date_dt:
                        break
        
        if not date_dt:
            date_dt = datetime.fromtimestamp(0, tz=timezone.utc)
        
        # Tags/Categories
        tag_els = container.select('[class*="tag"]:not([class*="status"]), [class*="category"], [class*="chip"]')
        tags = list({t.get_text(strip=True) for t in tag_els if t.get_text(strip=True) and len(t.get_text(strip=True)) < 50})
        
        # Description
        desc_el = container.select_one('p, div[class*="description"], div[class*="summary"]')
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
    return bool(re.search(r"\b(launched|available|ga)\b", (status_text or "").lower()))

# ----------------------------- Fetch & Parse ----------------------------------
with st.spinner("Fetching Azure Updates (this may take 10-20 seconds)…"):
    try:
        html_text = fetch_updates_page(UPDATES_URL)
        if not html_text:
            st.error("Failed to fetch page content.")
            st.stop()
    except Exception as e:
        st.error(f"Failed to load the updates page: {e}")
        st.stop()

updates = parse_updates(html_text)

# Filter for launched items
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
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ----------------------------- Render -----------------------------------------
if not launched:
    st.warning("No 'Launched' items detected on the page. The page structure may have changed.")
    st.info("💡 Try refreshing or check the Azure Updates page manually.")
else:
    for u in launched:
        with st.container():
            st.subheader(u["title"])
            meta_cols = st.columns([1.3, 1, 2])
            with meta_cols[0]:
                if u["link"]:
                    st.markdown(f"[🔗 View Update]({u['link']})")
            with meta_cols[1]:
                date_str = u['date'].strftime('%Y-%m-%d') if u['date'] and u['date'].year > 1970 else '—'
                st.markdown(f"**Published:** {date_str}")
            with meta_cols[2]:
                if u["tags"]:
                    st.markdown("**Tags:** " + ", ".join(u["tags"]))

            if u["description_html"]:
                st.markdown(html.unescape(u["description_html"]), unsafe_allow_html=True)
            else:
                st.caption("_No description found; click the link for full details._")

            st.divider()