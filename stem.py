# streamlit_app.py

import streamlit as st
import asyncio
import random
import uuid
import pandas as pd

from seleniumbase import cdp_driver
from playwright.async_api import async_playwright
import aiomysql
import pymysql


# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------

st.set_page_config(
    page_title="SEO Rank Tracker",
    page_icon="🚀",
    layout="wide"
)

# ---------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------

st.markdown("""
<style>

.main {
    background-color: #0e1117;
}

.stButton > button {
    width: 100%;
    background-color: #1f6feb;
    color: white;
    height: 3em;
    font-size: 18px;
    border-radius: 10px;
    border: none;
}

.stTextInput input {
    background-color: #161b22;
    color: white;
}

.metric-card {
    background: #161b22;
    padding: 20px;
    border-radius: 12px;
    text-align: center;
}

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# TITLE
# ---------------------------------------------------

st.title("🚀 SEO Rank Tracker Dashboard")

st.write("Google Keyword Ranking Scraper using Playwright + Streamlit")

# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------

st.sidebar.title("Settings")

pages_per_keyword = st.sidebar.slider(
    "Pages Per Keyword",
    1,
    10,
    5
)

created_by = st.sidebar.number_input(
    "Created By",
    value=33
)

start_button = st.sidebar.button(
    "Start Scraping"
)

# ---------------------------------------------------
# DB CONFIG
# ---------------------------------------------------

DB_CONFIG = {
    "host": st.secrets["mysql"]["host"],
    "user": st.secrets["mysql"]["user"],
    "password": st.secrets["mysql"]["password"],
    "db": st.secrets["mysql"]["db"],
}

# ---------------------------------------------------
# LIVE LOG AREA
# ---------------------------------------------------

log_box = st.empty()

logs = []


def add_log(message):

    logs.append(message)

    log_box.code(
        "\n".join(logs),
        language="bash"
    )


# ---------------------------------------------------
# UPDATE PROCESS STATUS
# ---------------------------------------------------

async def update_process_status(
    pool,
    process_id,
    status_code
):

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


# ---------------------------------------------------
# INSERT PROCESS
# ---------------------------------------------------

async def insert_process(pool, process_id):

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
                )
                AND domain IS NOT NULL
                LIMIT 2;
            """)

            return await cur.fetchall()


# ---------------------------------------------------
# BULK INSERT
# ---------------------------------------------------

async def bulk_insert_rankings(
    pool,
    data,
    created_by
):

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


# ---------------------------------------------------
# SCRAPER
# ---------------------------------------------------

async def run_scraper():

    process_id = str(uuid.uuid4())

    pool = None
    driver = None

    try:

        add_log("Creating Database Pool...")

        pool = await aiomysql.create_pool(
            **DB_CONFIG
        )

        await insert_process(
            pool,
            process_id
        )

        add_log(f"Process ID: {process_id}")

        keywords_data = await get_keywords(pool)

        if not keywords_data:

            add_log("No keywords found")
            return

        add_log("Launching Browser...")

        # ---------------------------------------------------
        # START CHROME
        # ---------------------------------------------------

        driver = await cdp_driver.start_async(
            headless=True,
            undetected=True,
            browser_executable_path=(
                "C:/Program Files/Google/Chrome/Application/chrome.exe"
            ),
            extra_params=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )

        endpoint_url = driver.get_endpoint_url()

        async with async_playwright() as p:

            browser = await p.chromium.connect_over_cdp(
                endpoint_url
            )

            page = browser.contexts[0].pages[0]

            bulk_data = []

            results_table = []

            # ---------------------------------------------------
            # LOOP KEYWORDS
            # ---------------------------------------------------

            for keyword_id, keyword, target_domain in keywords_data:

                add_log(f"\nSearching Keyword: {keyword}")

                search_url = (
                    "https://www.google.com/search?q="
                    f"{keyword.replace(' ', '+')}"
                )

                await page.goto(
                    search_url,
                    wait_until="domcontentloaded"
                )

                current_rank = 1
                found_rank = None

                for page_num in range(
                    pages_per_keyword
                ):

                    await asyncio.sleep(
                        random.uniform(2, 4)
                    )

                    results = await page.locator(
                        "div[data-hveid], div.g"
                    ).all()

                    for res in results:

                        item = await res.evaluate("""
                            (node) => {
                                const h3 = node.querySelector('h3');

                                return h3
                                    ? {
                                        link: node.querySelector('a')?.href
                                      }
                                    : null;
                            }
                        """)

                        if item and item.get("link"):

                            link = item["link"]

                            add_log(
                                f"Checking Rank {current_rank}"
                            )

                            if (
                                target_domain.lower()
                                in link.lower()
                            ):

                                found_rank = current_rank

                                add_log(
                                    f"FOUND at Rank {current_rank}"
                                )

                                break

                            current_rank += 1

                    if found_rank:
                        break

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

                final_rank = (
                    found_rank
                    if found_rank
                    else 51
                )

                bulk_data.append(
                    (
                        keyword_id,
                        final_rank
                    )
                )

                results_table.append({
                    "Keyword": keyword,
                    "Domain": target_domain,
                    "Rank": final_rank
                })

            # ---------------------------------------------------
            # INSERT DATA
            # ---------------------------------------------------

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

            add_log("Scraping Completed")

            await browser.close()

            # ---------------------------------------------------
            # SHOW TABLE
            # ---------------------------------------------------

            st.subheader("Ranking Results")

            df = pd.DataFrame(results_table)

            st.dataframe(
                df,
                use_container_width=True
            )

    except Exception as e:

        add_log(f"\nSCRAPER ERROR:\n{str(e)}")

        if pool:

            await update_process_status(
                pool,
                process_id,
                3
            )

    finally:

        if driver:
            driver.quit()

        if pool:
            pool.close()
            await pool.wait_closed()


# ---------------------------------------------------
# START BUTTON
# ---------------------------------------------------

if start_button:

    asyncio.run(
        run_scraper()
    )
