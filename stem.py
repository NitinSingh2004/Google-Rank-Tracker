import streamlit as st
import asyncio
import random
import uuid
import aiomysql
from playwright.async_api import async_playwright
from seleniumbase import cdp_driver

from playwright_stealth import Stealth
import subprocess
import pandas as pd


@st.cache_resource
def install_playwright():
    try:
        subprocess.run(
            ["playwright", "install", "chromium"],
            check=True
        )
    except Exception as e:
        st.error(f"Playwright install error: {e}")

install_playwright()


DB_CONFIG = {
    "host": "43.230.202.147",
    "user": "ewayswork_seotoo",
    "password": "kCPZk9wkL.1GfoZP",
    "db": "ewayswork_seotool",
}



async def update_process_status(pool, process_id, status_code):
    """
    Status:
    1 = Running
    2 = Completed
    3 = Error
    """

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:

            await cur.execute(
                """
                UPDATE scrapdata_process
                SET ProcessStatus = %s
                WHERE ProcessID = %s
                """,
                (status_code, process_id)
            )

            await conn.commit()


async def insert_process(pool, process_id):
    """
    type = 2 => ranking scraper
    """

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:

            await cur.execute(
                """
                INSERT INTO scrapdata_process
                (ProcessID, ProcessStatus, type)
                VALUES (%s, %s, %s)
                """,
                (process_id, 1, 2)
            )

            await conn.commit()



async def get_keywords(pool):

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:

            await cur.execute("""
                SELECT DISTINCT
                    k.KeywordID,
                    k.KeywordName,
                    p.domain
                FROM keywords k
                LEFT JOIN projects p
                    ON p.ProjectID = k.ProjectNo
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM keywords_ranking_history krh
                    WHERE krh.KeywordNo = k.KeywordID
                    AND krh.CreatedAt >= NOW() - INTERVAL 30 DAY
                )
                AND domain IS NOT NULL
                LIMIT 20;
            """)

            return await cur.fetchall()



async def bulk_insert_rankings(pool, data, created_by):

    if not data:
        return

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:

            await cur.executemany(
                """
                INSERT INTO keywords_ranking_history
                (KeywordNo, Ranking, CreatedAt, CreatedBy)
                VALUES (%s, %s, NOW(), %s)
                """,
                [(k, r, created_by) for (k, r) in data]
            )

            await conn.commit()


async def run_scraping_logic( pages_per_keyword,created_by,):
    driver = None
    pool = None
    results_output = [] # To return to the UI if needed
    process_id="1234455"
    try:
        pool = await aiomysql.create_pool(**DB_CONFIG)
        keywords_data = await get_keywords(pool)

        if not keywords_data:
            await update_process_status(pool, process_id, 2)
            return []

        # START BROWSER USING CDP
        driver = await cdp_driver.start_async(
            headless=False,
            undetected=True,
            extra_params=["--no-sandbox"]
        )

        endpoint_url = driver.get_endpoint_url()

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(endpoint_url)
            page = browser.contexts[0].pages[0]

            bulk_data = []

            for keyword_id, keyword, target_domain in keywords_data:
                search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
                print(f"Searching: {keyword} for domain: {target_domain}")

                await page.goto(search_url, wait_until="domcontentloaded")
                
                # --- CAPTCHA CHECK 1 ---
                content = await page.content()
                if "detected unusual traffic" in content or await page.locator("#captcha-form").count() > 0:
                    print(f"CAPTCHA DETECTED for {keyword}")
                    bulk_data.append((keyword_id, 0)) # Using 0 to represent CAPTCHA in DB
                    results_output.append({"keyword": keyword, "rank": "CAPTCHA"})
                    continue 

                current_rank = 1
                found_rank = None

                for page_num in range(pages_per_keyword):
                    await asyncio.sleep(random.uniform(2, 4))

                    # Select result containers
                    results = await page.locator("div[data-hveid], div.g").all()

                    for res in results:
                        item = await res.evaluate("""
                            (node) => {
                                const h3 = node.querySelector('h3');
                                return h3 ? { link: node.querySelector('a')?.href } : null;
                            }
                        """)

                        if item and item.get("link"):
                            link = item["link"]
                            if target_domain.lower() in link.lower():
                                found_rank = current_rank
                                break
                            current_rank += 1

                    if found_rank:
                        break

                    # NEXT PAGE LOGIC
                    if page_num < pages_per_keyword - 1:
                        next_btn = page.locator("a#pnnext").first
                        if await next_btn.is_visible():
                            await next_btn.click()
                            await page.wait_for_load_state("domcontentloaded")
                            
                            # --- CAPTCHA CHECK 2 (During Pagination) ---
                            if "detected unusual traffic" in await page.content():
                                found_rank = "CAPTCHA"
                                break
                        else:
                            break
                    else:
                        break

                # Determine final rank to save
                if found_rank == "CAPTCHA":
                    final_rank = 0
                    rank_display = "CAPTCHA"
                elif found_rank:
                    final_rank = found_rank
                    rank_display = found_rank
                else:
                    final_rank = 100
                    rank_display = 100

                bulk_data.append((keyword_id, final_rank))
                results_output.append({"keyword": keyword, "rank": rank_display})

            # SAVE DATA
            if bulk_data:
                await bulk_insert_rankings(pool, bulk_data, created_by)

            await update_process_status(pool, process_id, 2)
            await browser.close()
            print("Scraping Completed")

    except Exception as e:
        print(f"Scraper Error: {e}")
        if pool:
            await update_process_status(pool, process_id, 3)
    finally:
        if driver:
            driver.quit()
        if pool:
            pool.close()
            await pool.wait_closed()
    
    return results_output
st.set_page_config(
    page_title="Google Rank Tracker"
)

st.title(
    "Google Ranking Tracker - Playwright Stealth"
)
fixed_number = 10
fixed_number2=33
pages_per_keyword = st.number_input(
    "Pages Per Keyword",
    min_value=1,
    max_value=10,
    value=fixed_number,
    
)

created_by = st.number_input(
    "Created By",
    value=fixed_number2,
     disabled=True
)

if st.button("Start Tracking"):

    with st.spinner("Tracking Rankings..."):

        try:

            results = asyncio.run(
                run_scraping_logic(
                    pages_per_keyword,
                    created_by
                )
            )

            st.success("Tracking Completed")

            df = pd.DataFrame(results)

            st.dataframe(
                df,
                use_container_width=True
            )

        except Exception as e:

            st.error(str(e))
