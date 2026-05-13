import streamlit as st
import asyncio
import random
import uuid
import aiomysql
from playwright.async_api import async_playwright
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


async def run_rank_tracker(pages_per_keyword, created_by):

    results_output = []
    bulk_data = []

    process_id = str(uuid.uuid4())

    pool = await aiomysql.create_pool(**DB_CONFIG)

    try:



        await insert_process(pool, process_id)

        keywords_data = await get_keywords(pool)

        if not keywords_data:

            await update_process_status(
                pool,
                process_id,
                2
            )

            return [{
                "message": "No keywords found"
            }]



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

            for keyword_id, keyword, target_domain in keywords_data:

                st.write(f"Searching: {keyword}")

                search_url = (
                    f"https://www.google.com/search?q="
                    f"{keyword.replace(' ', '+')}"
                )

                await page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                await asyncio.sleep(
                    random.uniform(2, 5)
                )

                current_rank = 1
                found_rank = None
                found_url = ""

                for page_num in range(pages_per_keyword):

                    await asyncio.sleep(
                        random.uniform(2, 4)
                    )

                    results = await page.locator("div.g").all()

                    for res in results:

                        try:

                            link = await res.locator(
                                "a"
                            ).first.get_attribute("href")

                            if link:

                                if target_domain.lower() in link.lower():

                                    found_rank = current_rank
                                    found_url = link

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



                    try:

                        next_btn = page.locator(
                            "a#pnnext"
                        ).first

                        if await next_btn.is_visible():

                            await next_btn.click()

                            await page.wait_for_load_state(
                                "domcontentloaded"
                            )

                        else:
                            break

                    except:
                        break

       

                if not found_rank:

                    found_rank = 51

                    results_output.append({
                        "keyword": keyword,
                        "domain": target_domain,
                        "rank": 51,
                        "url": "Not Found"
                    })

                bulk_data.append((
                    keyword_id,
                    found_rank
                ))


            await bulk_insert_rankings(
                pool,
                bulk_data,
                created_by
            )


            await update_process_status(
                pool,
                process_id,
                2
            )

            await browser.close()

    except Exception as e:

        # ---------------------------------------------
        # UPDATE PROCESS ERROR
        # ---------------------------------------------

        await update_process_status(
            pool,
            process_id,
            3
        )

        raise e

    finally:

        pool.close()
        await pool.wait_closed()

    return results_output

# ---------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------

st.set_page_config(
    page_title="Google Rank Tracker"
)

st.title(
    "Google Ranking Tracker - Playwright Stealth"
)

pages_per_keyword = st.number_input(
    "Pages Per Keyword",
    min_value=1,
    max_value=10,
    value=5
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

            df = pd.DataFrame(results)

            st.dataframe(
                df,
                use_container_width=True
            )

        except Exception as e:

            st.error(str(e))
