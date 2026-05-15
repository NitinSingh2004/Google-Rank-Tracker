import streamlit as st
import asyncio
from seleniumbase import cdp_driver
from playwright.async_api import async_playwright

async def test_scraper():
    driver = None
    try:
        st.write("🔄 Step 1: Starting cdp_driver in headless mode...")
        driver = await cdp_driver.start_async(
            headless=True,
            undetected=True,
            extra_params=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox"
            ]
        )
        
        endpoint_url = driver.get_endpoint_url()
        st.write(f"✅ Driver started! Endpoint: `{endpoint_url}`")

        st.write("🔄 Step 2: Connecting Playwright over CDP...")
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(endpoint_url)
            page = browser.contexts[0].pages[0]
            await page.set_viewport_size({"width": 1920, "height": 1080})

            st.write("🔄 Step 3: Navigating to Google Search...")
            # Using a basic search query to check if it gets blocked or works
            await page.goto("https://www.google.com/search?q=streamlit+cloud+test", wait_until="domcontentloaded")
            
            # Extract the page title as proof of success
            title = await page.title()
            st.success(f"🎉 Success! Page Title: **{title}**")
            
            await browser.close()

    except Exception as e:
        st.error(f"❌ Scraper Failed: {e}")
        
    finally:
        if driver:
            driver.quit()

st.title("🌐 Streamlit Cloud Scraper Test")

if st.button("Run Test Scraper"):
    asyncio.run(test_scraper())
  
