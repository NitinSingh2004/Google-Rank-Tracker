import streamlit as st
import asyncio
import random
import subprocess
from seleniumbase import cdp_driver
from playwright.async_api import async_playwright

# --- ASYNC RUNTIME PATCH FOR STREAMLIT ---
# Streamlit already runs an event loop. We use a helper helper to handle nested loops cleanly.
def run_async_task(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        # If an event loop is already running, schedule the task
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)

# --- ENVIRONMENT BINARY CHECK ---
@st.cache_resource
def install_playwright_binaries():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Playwright binary installation warning: {e}")

install_playwright_binaries()


async def scrape_top_3_cakes():
    driver = None
    browser = None
    titles_found = []
    
    try:
        st.write("🔄 Step 1: Initializing undetected cdp_driver backend...")
        driver = await cdp_driver.start_async(
            headless=True,  # Must be True for Streamlit Cloud (No GUI)
            undetected=True,
            extra_params=[
                "--no-sandbox",
                "--disable-dev-shm-usage",  # Crucial for resource-constrained Linux containers
                "--disable-gpu",            # Bypasses graphic rendering demands
                "--disable-setuid-sandbox"
            ]
        )
        
        endpoint_url = driver.get_endpoint_url()
        st.write(f"✅ CDP Endpoint secured: `{endpoint_url}`")

        st.write("🔄 Step 2: Bridging Playwright orchestration...")
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(endpoint_url)
            
            # Create an isolated context to inject human-like headers
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            st.write("🔄 Step 3: Dispatching search request for *'cakes'*...")
            # Appending localized parameters handles layout variations cleaner on cloud nodes
            await page.goto("https://www.google.com/search?q=cakes&hl=en&gl=us", wait_until="domcontentloaded")
            
            # Human-like observation delay
            await asyncio.sleep(random.uniform(3.5, 5.0))
            
            st.write("🔄 Step 4: Scraping DOM trees...")
            
            # Target standard search cards ('div.g') and alternative structural card variations
            search_cards = await page.locator("div.g, div[data-hveid]").all()
            
            for card in search_cards:
                if len(titles_found) >= 3:
                    break
                    
                try:
                    # Isolate the main header text tag inside the element block
                    h3_element = card.locator("h3").first
                    if await h3_element.is_visible():
                        title_text = await h3_element.text_content()
                        title_text = title_text.strip() if title_text else ""
                        
                        # Deduplicate entries and filter out auxiliary/people-also-ask layouts
                        if title_text and title_text not in titles_found and not title_text.startswith(("People also ask", "Images for")):
                            titles_found.append(title_text)
                except:
                    continue

            # --- RENDER RESULTS TO UI ---
            if titles_found:
                st.success("🎉 Scraping complete!")
                st.markdown("### 🎂 Top 3 Google Search Result Titles:")
                for i, title in enumerate(titles_found[:3], start=1):
                    st.markdown(f"**{i}.** {title}")
            else:
                # Check if it was caught by a verification filter
                page_source = await page.content()
                if "captcha" in page_source.lower() or "unusual traffic" in page_source.lower():
                    st.error("⚠️ Google served a CAPTCHA. The Cloud infrastructure IP has been temporarily restricted.")
                else:
                    st.warning("⚠️ Page loaded but elements could not be extracted. Google layout might have changed.")

            await browser.close()

    except Exception as e:
        st.error(f"❌ Automation Error: {str(e)}")
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


# --- STREAMLIT USER INTERFACE ---
st.set_page_config(page_title="Cakes Search Test", page_icon="🎂")
st.title("🎂 Google 'Cakes' Title Scraper")
st.caption("Utilizes SeleniumBase cdp_driver bridged with native Playwright CDP connection loops.")

if st.button("Execute Search Query", type="primary"):
    with st.spinner("Processing browser routines inside cloud container..."):
        # Executes our async block safely inside Streamlit's runtime thread pool
        run_async_task(scrape_top_3_cakes())
