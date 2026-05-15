import asyncio
import uuid
import random
import streamlit as st

from seleniumbase import cdp_driver
from playwright.async_api import async_playwright
import aiomysql

# -----------------------------
# DB CONFIG (UNCHANGED)
# -----------------------------
DB_CONFIG = {
    "host": "43.230.202.147",
    "user": "ewayswork_seotoo",
    "password": "kCPZk9wkL.1GfoZP",
    "db": "ewayswork_seotool",
}

# -----------------------------
# STATUS UPDATE
# -----------------------------
async def update_process_status(pool, process_id, status_code):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE scrapdata_process
                SET ProcessStatus = %s
                WHERE ProcessID = %s
            """, (status_code, process_id))
            await conn.commit()

# -----------------------------
# INSERT PROCESS
# -----------------------------
async def insert_process(pool, process_id):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO scrapdata_process
                (ProcessID, ProcessStatus, type)
                VALUES (%s, %s, %s)
            """, (process_id, 1, 2))
            await conn.commit()

# -----------------------------
# GET KEYWORDS
# -----------------------------
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
                LIMIT 4;
            """)
            return await cur.fetchall()

# -----------------------------
# BULK INSERT
# -----------------------------
async def bulk_insert_rankings(pool, data, created_by):
    if not data:
        return

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany("""
                INSERT INTO keywords_ranking_history
                (KeywordNo, Ranking, CreatedAt, CreatedBy)
                VALUES (%s, %s, NOW(), %s)
            """, [(k, r, created_by) for (k, r) in data])

            await conn.commit()

# -----------------------------
# SCRAPING LOGIC (UNCHANGED)
# -----------------------------
async def run_scraping_logic(process_id, created_by, pages_per_keyword):
    driver = None
    pool = None

    try:
        pool = await aiomysql.create_pool(**DB_CONFIG)
        keywords_data = await get_keywords(pool)

        st.write("Fetched Keywords:", keywords_data)

        if not keywords_data:
            await update_process_status(pool, process_id, 2)
            return

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
                st.write(f"Searching: {keyword} → {target_domain}")

                await page.goto(search_url, wait_until="domcontentloaded")

                current_rank = 1
                found_rank = None

                for page_num in range(pages_per_keyword):

                    await asyncio.sleep(random.uniform(2, 4))

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
                                st.success(f"Rank {current_rank}: {link}")
                                break

                            current_rank += 1

                    if found_rank:
                        break

                    if page_num < pages_per_keyword - 1:
                        next_btn = page.locator("a#pnnext").first
                        if await next_btn.is_visible():
                            await next_btn.click()
                            await page.wait_for_load_state("domcontentloaded")
                        else:
                            break
                    else:
                        break

                bulk_data.append((
                    keyword_id,
                    found_rank if found_rank else 51
                ))

            if bulk_data:
                await bulk_insert_rankings(pool, bulk_data, created_by)

            await update_process_status(pool, process_id, 2)

            await browser.close()
            st.success("Scraping Completed")

    except Exception as e:
        st.error(f"Scraper Error: {e}")
        if pool:
            await update_process_status(pool, process_id, 3)

    finally:
        if driver:
            driver.quit()
        if pool:
            pool.close()
            await pool.wait_closed()

# -----------------------------
# STREAMLIT UI (REPLACES FASTAPI)
# -----------------------------
st.title("Keyword Ranking Scraper")

pages_per_keyword = st.number_input("Pages per keyword", min_value=1, max_value=10, value=5)
created_by = st.number_input("Created By", value=33)

if st.button("Start Scraping"):

    process_id = str(uuid.uuid4())
    st.session_state["process_id"] = process_id

    async def runner():
        pool = await aiomysql.create_pool(**DB_CONFIG)
        await insert_process(pool, process_id)
        pool.close()
        await pool.wait_closed()

        # IMPORTANT: same argument order as your original bug (kept unchanged)
        await run_scraping_logic(process_id, created_by, pages_per_keyword)

    asyncio.run(runner())

    st.success(f"Process started: {process_id}")

  
