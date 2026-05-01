###### Full text with no format ######
# import asyncio
# from playwright.async_api import async_playwright
# from seleniumbase import cdp_driver

# keyword="cakes"
# async def main():
#     driver = await cdp_driver.start_async(locale="en")
#     endpoint_url = driver.get_endpoint_url()

#     async with async_playwright() as p:
#         browser = await p.chromium.connect_over_cdp(endpoint_url)
#         context = browser.contexts[0]
#         page = context.pages[0]

#         await page.goto("https://www.google.com", wait_until="load")
#         # Accept cookies (if appears)
#         await page.fill("textarea[name='q']", keyword)
#         await page.keyboard.press("Enter")
#         # await page.wait_for_selector("h3", timeout=10000)

#         parents = await page.locator("div.yhQgZb").all()
#         print(parents)

#         for parent in parents:
#             print("--- New Group ---")

#             # 2. Find only the MjjYud divs INSIDE this specific parent
#             children = await parent.locator("div.MjjYud").all()

#             for child in children:
#                 content = await child.inner_text()
#                 print(f"Item text: {content}...")
                
#         await driver.sleep(3)
#         await driver.solve_captcha()
#         await driver.sleep(3)
#         await browser.close()

# if __name__ == "__main__":
#     loop = asyncio.new_event_loop()
#     loop.run_until_complete(main())




####### full Working for Google Page Extractor #######

# import random
# import asyncio
# import json
# from playwright.async_api import async_playwright
# from seleniumbase import cdp_driver


# async def main():
#     # 1. Configuration
#     keywords = ["anniversary flowers"]
#     pages_per_keyword = 2  # Set how many pages you want to scrape per keyword

#     driver = await cdp_driver.start_async(locale="en")
#     endpoint_url = driver.get_endpoint_url()

#     async with async_playwright() as p:
#         browser = await p.chromium.connect_over_cdp(endpoint_url)
#         page = browser.contexts[0].pages[0]

#         all_results = {}

#         for keyword in keywords:
#             print(f"--- Starting Keyword: {keyword} ---")
#             search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
#             await page.goto(search_url, wait_until="networkidle")

#             final_data = []
#             current_rank = 1

#             for page_num in range(pages_per_keyword):
#                 print(f"Scraping Page {page_num + 1} for '{keyword}'...")

#                 # Ensure content is loaded
#                 await page.evaluate("window.scrollBy(0, 1000)")
#                 await asyncio.sleep(2)

#                 results = await page.locator('div[data-hveid], div.g').all()

#                 for res in results:
#                     item = await res.evaluate("""(node) => {
#                         const clean = (str) => {
#                             if (!str) return "";
#                             return str.normalize("NFKD")
#                                 .replace(/\\u00b7/g, ' | ')
#                                 .replace(/[\\r\\n\\t]+/g, ' ')
#                                 .replace(/\\s\\s+/g, ' ')
#                                 .trim();
#                         };

#                         const h3 = node.querySelector('h3');
#                         if (!h3) return null;

#                         let snippetEl = node.querySelector('div[style*="-webkit-line-clamp"]');
#                         let description = snippetEl ? snippetEl.innerText : "";

#                         if (!description) {
#                             const lines = node.innerText.split('\\n');
#                             description = lines.reduce((a, b) => a.length > b.length ? a : b);
#                         }

#                         const rangeRegex = /([₹$]|Rs\\.?)\\s?\\d{1,3}(,?\\d{3})*(\\.\\d{2})?(?!-?\\s?hour|\\s?day)(\\s*(to|-)\\s*([₹$]|Rs\\.?)\\s?\\d{1,3}(,?\\d{3})*(\\.\\d{2})?)?/i;
#                         const priceMatch = node.innerText.match(rangeRegex);

#                         return {
#                             title: clean(h3.innerText),
#                             link: node.querySelector('a')?.href,
#                             price: priceMatch ? clean(priceMatch[0]) : "N/A",
#                             description: clean(description.split('Read more')[0])
#                         };
#                     }""")

#                     if item and item['title'] and "google.com" not in (item['link'] or ""):
#                         if not any(d['title'] == item['title'] for d in final_data):
#                             item['rank'] = current_rank
#                             final_data.append(item)
#                             current_rank += 1

#                 # 2. PAGINATION LOGIC
#                 if page_num < pages_per_keyword - 1:
#                     next_button = page.locator(
#                         'a#pnnext, a:has-text("Next")').first
#                     if await next_button.is_visible():
#                         await next_button.click()
#                         await page.wait_for_load_state("networkidle")
#                         await asyncio.sleep(2)
#                     else:
#                         print("No more pages available.")
#                         break

#             all_results[keyword] = final_data

#         print(json.dumps(all_results, indent=2, ensure_ascii=False))

#     await browser.close()

# if __name__ == "__main__":
#     asyncio.run(main())


# import asyncio
# import json
# import random
# from playwright.async_api import async_playwright
# from seleniumbase import cdp_driver

# async def main():
#     # --- CONFIGURATION ---
#     keywords = ["anniversary flowers", "best flower delivery", "luxury roses"]

#     # Add your own websites here to track their rank
#     target_urls = ["fnp.com"]

#     pages_per_keyword = 2

#     # Start the stealth driver
#     driver = await cdp_driver.start_async(locale="en")
#     endpoint_url = driver.get_endpoint_url()

#     async with async_playwright() as p:
#         browser = await p.chromium.connect_over_cdp(endpoint_url)
#         page = browser.contexts[0].pages[0]

#         all_results = {}

#         for keyword in keywords:
#             print(f"\n--- Processing Keyword: {keyword} ---")
#             search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"

#             # Navigate with a human-like delay
#             await page.goto(search_url, wait_until="networkidle")

#             final_data = []
#             current_rank = 1
#             target_matches = []

#             for page_num in range(pages_per_keyword):
#                 print(f"  > Scraping Page {page_num + 1}...")

#                 # FEATURE 1: RANDOM DELAY (Human-like behavior)
#                 # Helps avoid detection without using proxies
#                 await asyncio.sleep(random.uniform(3.5, 6.2))

#                 # Smooth scroll to trigger lazy loading
#                 await page.evaluate("window.scrollBy(0, 800)")

#                 results = await page.locator('div[data-hveid], div.g').all()

#                 for res in results:
#                     item = await res.evaluate("""(node) => {
#                         const clean = (str) => {
#                             if (!str) return "";
#                             return str.normalize("NFKD")
#                                 .replace(/\\u00b7/g, ' | ')
#                                 .replace(/[\\r\\n\\t]+/g, ' ')
#                                 .replace(/\\s\\s+/g, ' ')
#                                 .trim();
#                         };

#                         const h3 = node.querySelector('h3');
#                         if (!h3) return null;

#                         let snippetEl = node.querySelector('div[style*="-webkit-line-clamp"]');
#                         let description = snippetEl ? snippetEl.innerText : "";

#                         if (!description) {
#                             const lines = node.innerText.split('\\n');
#                             description = lines.reduce((a, b) => a.length > b.length ? a : b);
#                         }

#                         const rangeRegex = /([₹$]|Rs\\.?)\\s?\\d{1,3}(,?\\d{3})*(\\.\\d{2})?(?!-?\\s?hour|\\s?day)(\\s*(to|-)\\s*([₹$]|Rs\\.?)\\s?\\d{1,3}(,?\\d{3})*(\\.\\d{2})?)?/i;
#                         const priceMatch = node.innerText.match(rangeRegex);

#                         return {
#                             title: clean(h3.innerText),
#                             link: node.querySelector('a')?.href,
#                             price: priceMatch ? clean(priceMatch[0]) : "N/A",
#                             description: clean(description.split('Read more')[0])
#                         };
#                     }""")


#                     if item and item['title'] and "google.com" not in (item['link'] or ""):
#                         # Prevent duplicate results
#                         if not any(d['title'] == item['title'] for d in final_data):

#                             # FEATURE 2: RANKING ID
#                             item['rank'] = current_rank

#                             # FEATURE 3: TARGET WEBSITE TRACKING
#                             link_lower = item['link'].lower()
#                             for target in target_urls:
#                                 if target.lower() in link_lower:
#                                     match_info = {
#                                         "target": target, "rank": current_rank, "url": item['link']}
#                                     target_matches.append(match_info)
#                                     print(
#                                         f"    [!] FOUND {target} at Rank {current_rank}")

#                             final_data.append(item)
#                             current_rank += 1

#                 # PAGINATION LOGIC
#                 if page_num < pages_per_keyword - 1:
#                     next_button = page.locator(
#                         'a#pnnext, a:has-text("Next")').first
#                     if await next_button.is_visible():
#                         # Random delay before clicking "Next"
#                         await asyncio.sleep(random.uniform(2, 4))
#                         await next_button.click()
#                         await page.wait_for_load_state("networkidle")
#                     else:
#                         break

#             # Store summary and full data for this keyword
#             all_results[keyword] = {
#                 "target_summary": target_matches,
#                 "total_results": len(final_data),
#                 "results": final_data
#             }

#         # Output final findings
#         print("\n" + "="*30)
#         print("SCRAPING COMPLETE")
#         print("="*30)
#         print(json.dumps(all_results, indent=2, ensure_ascii=False))

#     await browser.close()

# if __name__ == "__main__":
#     asyncio.run(main())


import streamlit as st
import asyncio
import json
import random
from playwright.async_api import async_playwright
from seleniumbase import cdp_driver

# Set page config
st.set_page_config(page_title="Google Rank Tracker", layout="wide")


async def scrape_google(keywords, target_urls, pages_per_keyword):
    """Core scraping logic wrapped for Streamlit."""
    results_container = st.empty()
    all_results = {}

    # Start the stealth driver
    driver = await cdp_driver.start_async(locale="en")
    endpoint_url = driver.get_endpoint_url()

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(endpoint_url)
        page = browser.contexts[0].pages[0]

        for keyword in keywords:
            st.write(f"🔍 **Processing:** {keyword}")
            search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"

            await page.goto(search_url, wait_until="networkidle")

            final_data = []
            current_rank = 1
            target_matches = []

            for page_num in range(pages_per_keyword):
                # Random delays to mimic human behavior
                await asyncio.sleep(random.uniform(2.5, 4.5))
                await page.evaluate("window.scrollBy(0, 800)")

                elements = await page.locator('div[data-hveid], div.g').all()

                for res in elements:
                    item = await res.evaluate("""(node) => {
                                            const clean = (str) => {
                                                if (!str) return "";
                                                return str.normalize("NFKD")
                                                    .replace(/\\u00b7/g, ' | ')
                                                    .replace(/[\\r\\n\\t]+/g, ' ')
                                                    .replace(/\\s\\s+/g, ' ')
                                                    .trim();
                                            };

                                            const h3 = node.querySelector('h3');
                                            if (!h3) return null;

                                            let snippetEl = node.querySelector('div[style*="-webkit-line-clamp"]');
                                            let description = snippetEl ? snippetEl.innerText : "";

                                            if (!description) {
                                                const lines = node.innerText.split('\\n');
                                                description = lines.reduce((a, b) => a.length > b.length ? a : b);
                                            }

                                            const rangeRegex = /([₹$]|Rs\\.?)\\s?\\d{1,3}(,?\\d{3})*(\\.\\d{2})?(?!-?\\s?hour|\\s?day)(\\s*(to|-)\\s*([₹$]|Rs\\.?)\\s?\\d{1,3}(,?\\d{3})*(\\.\\d{2})?)?/i;
                                            const priceMatch = node.innerText.match(rangeRegex);

                                            return {
                                                title: clean(h3.innerText),
                                                link: node.querySelector('a')?.href,
                                                price: priceMatch ? clean(priceMatch[0]) : "N/A",
                                                description: clean(description.split('Read more')[0])
                                            };
                                        }""")

                    if item and item['title'] and "google.com" not in (item['link'] or ""):
                        if not any(d['title'] == item['title'] for d in final_data):
                            item['rank'] = current_rank

                            # Check for Target URLs
                            link_lower = item['link'].lower()
                            for target in target_urls:
                                if target.strip().lower() in link_lower:
                                    match_info = {
                                        "target": target, "rank": current_rank, "url": item['link']}
                                    target_matches.append(match_info)
                                    st.success(
                                        f"🎯 Found **{target}** at Rank {current_rank}")

                            final_data.append(item)
                            current_rank += 1

                # Pagination
                if page_num < pages_per_keyword - 1:
                    next_button = page.locator(
                        'a#pnnext, a:has-text("Next")').first
                    if await next_button.is_visible():
                        await asyncio.sleep(random.uniform(1.5, 3))
                        await next_button.click()
                        await page.wait_for_load_state("networkidle")
                    else:
                        break

            all_results[keyword] = {
                "target_summary": target_matches,
                "total_results": len(final_data),
                "results": final_data
            }

        await browser.close()
    return all_results

# --- STREAMLIT UI ---
st.title("🚀 Google SEO Rank Tracker")
st.markdown(
    "Track your website rankings across multiple keywords without paid proxies.")

with st.sidebar:
    st.header("Settings")
    kw_input = st.text_area("Keywords (one per line)",
                            value="anniversary flowers")
    target_input = st.text_area(
        "Target Domains (one per line)", value="1800flowers.com")
    pages = st.slider("Pages per keyword", 1, 5, 2)

    start_button = st.button("Start Scraping", type="primary")

if start_button:
    keywords_list = [k.strip() for k in kw_input.split('\n') if k.strip()]
    targets_list = [t.strip() for t in target_input.split('\n') if t.strip()]

    if not keywords_list:
        st.error("Please enter at least one keyword.")
    else:
        with st.status("Scraping in progress...", expanded=True) as status:
            # Run the async scraper
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data = loop.run_until_complete(
                scrape_google(keywords_list, targets_list, pages))
            status.update(label="Scraping Complete!",
                          state="complete", expanded=False)

        st.divider()
        st.subheader("Results Overview")

        # Display summarized results
        for kw, content in data.items():
            with st.expander(f"Keyword: {kw} ({len(content['target_summary'])} matches)"):
                if content['target_summary']:
                    st.table(content['target_summary'])
                else:
                    st.info("No target domains found in the top results.")

                st.json(content['results'])

        # Download Button
        json_string = json.dumps(data, indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 Download JSON Results",
            file_name="google_rank_results.json",
            mime="application/json",
            data=json_string,
        )
