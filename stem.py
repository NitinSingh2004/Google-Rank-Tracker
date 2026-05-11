import streamlit as st
import asyncio
import random
import aiomysql
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import os
import subprocess
import pandas as pd



@st.cache_resource
def install_playwright():
    try:
        # Check if the browser is already present to save time
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Error installing Playwright: {e}")

# Call the install function
install_playwright()
# ---------------------------------------------------
# DATABASE CONFIG
# ---------------------------------------------------

DB_CONFIG = {
    "host": "43.230.202.147",
    "user": "ewayswork_seotoo",
    "password": "kCPZk9wkL.1GfoZP",
    "db": "ewayswork_seotool",
}

# ---------------------------------------------------
# GET KEYWORDS
# ---------------------------------------------------

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
            ) and domain is not null
            LIMIT 2;
            """)
            return await cur.fetchall()


# ---------------------------------------------------
# INSERT RANKING HISTORY
# ---------------------------------------------------

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


# ---------------------------------------------------
# MAIN SCRAPER
# ---------------------------------------------------

async def run_rank_tracker(pages_per_keyword, created_by):

    results_output = []
    bulk_data = []

    pool = await aiomysql.create_pool(**DB_CONFIG)

    keywords_data = await get_keywords(pool)

    if not keywords_data:
        return ["No keywords found"]

    # ---------------------------------------------------
    # PLAYWRIGHT STEALTH MODE
    # ---------------------------------------------------

    async with Stealth().use_async(async_playwright()) as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        )

        page = await context.new_page()

        # ---------------------------------------------------
        # LOOP KEYWORDS
        # ---------------------------------------------------

        for keyword_id, keyword, target_domain in keywords_data:

            st.write(f"Searching Keyword: {keyword}")

            search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"

            await page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await asyncio.sleep(random.uniform(2, 5))

            current_rank = 1
            found_rank = None

            # ---------------------------------------------------
            # PAGINATION LOOP
            # ---------------------------------------------------

            for page_num in range(pages_per_keyword):

                await asyncio.sleep(random.uniform(2, 4))

                results = await page.locator("div.g").all()

                for res in results:

                    try:
                        link = await res.locator("a").first.get_attribute("href")

                        if link:

                            if target_domain.lower() in link.lower():

                                found_rank = current_rank

                                results_output.append({
                                    "keyword": keyword,
                                    "domain": target_domain,
                                    "rank": current_rank,
                                    "url": link
                                })

                                break

                            current_rank += 1

                    except:
                        pass

                if found_rank:
                    break

                # NEXT PAGE
                try:
                    next_btn = page.locator("a#pnnext").first

                    if await next_btn.is_visible():
                        await next_btn.click()
                        await page.wait_for_load_state("domcontentloaded")

                    else:
                        break

                except:
                    break

            # NOT FOUND
            if not found_rank:

                found_rank = 51

                results_output.append({
                    "keyword": keyword,
                    "domain": target_domain,
                    "rank": 51,
                   
                })

            bulk_data.append((
                keyword_id,
                found_rank
            ))

        # ---------------------------------------------------
        # SAVE DATABASE
        # ---------------------------------------------------

        await bulk_insert_rankings(
            pool,
            bulk_data,
            created_by
        )

        await browser.close()

    pool.close()
    await pool.wait_closed()

    return results_output


# ---------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------

st.set_page_config(page_title="Google Rank Tracker")

st.title("Google Ranking Tracker - Playwright Stealth")

pages_per_keyword = st.number_input(
    "Pages Per Keyword",
    min_value=1,
    max_value=6,
    value=3
)

created_by = st.number_input(
    "Created By",
    value=33
)

if st.button("Start Tracking"):

    with st.spinner("Tracking Rankings..."):

        try:

            results = asyncio.run(
                run_rank_tracker(
                    pages_per_keyword,
                    created_by
                )
            )

            st.success("Tracking Completed")

# Convert the list of dicts to a DataFrame
            df = pd.DataFrame(results)

# Display as an interactive table
            st.dataframe(df, use_container_width=True)


