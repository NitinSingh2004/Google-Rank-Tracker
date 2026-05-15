import streamlit as st
import asyncio
import random
from seleniumbase import cdp_driver
from playwright.async_api import async_playwright

async def test_scraper():
    driver = None
    try:
        st.write("🔄 Step 1: Starting cdp_driver in headless cloud mode...")
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
        st.write(f"✅ Driver active at endpoint: `{endpoint_url}`")

        st.write("🔄 Step 2: Connecting Playwright context...")
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(endpoint_url)
            page = browser.contexts[0].pages[0]
            await page.set_viewport_size({"width": 1920, "height": 1080})

            st.write("🔄 Step 3: Searching Google for *'cakes'*...")
            await page.goto("https://www.google.com/search?q=cakes", wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 4))
            
            st.write("🔄 Step 4: Extracting top 3 website titles...")
            
            # Select Google's primary result card components containing links and H3 elements
            results = await page.locator("div.g").all()
            
            titles_found = []
            for res in results:
                # Break once we successfully collect the top 3 items
                if len(titles_found) >= 3:
                    break
                    
                try:
                    # Target the H3 tag which holds the actual visible text title of the website result
                    h3_element = res.locator("h3").first
                    if await h3_element.is_visible():
                        title_text = await h3_element.text_content()
                        if title_text and title_text not in titles_found:
                            titles_found.append(title_text)
                except:
                    continue

            # Output the results neatly to the Streamlit UI
            if titles_found:
                st.success("🎉 Successfully retrieved data!")
                st.write("### 🎂 Top 3 Website Titles Found:")
                for index, title in enumerate(titles_found, start=1):
                    st.write(f"**{index}.** {title}")
            else:
                st.warning("⚠️ Connected successfully, but couldn't parse the elements. Google might be presenting a structural variant or a CAPTCHA.")

            await browser.close()

    except Exception as e:
        st.error(f"❌ Scraper Failed: {e}")
        
    finally:
        if driver:
            driver.quit()

st.title("🌐 Streamlit Cloud Scraper Test - Cakes Query")

if st.button("Run Cakes Scraper"):
    asyncio.run(test_scraper())
