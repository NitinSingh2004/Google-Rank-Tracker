# streamlit_app.py

import streamlit as st
import asyncio
import random
import uuid
import pandas as pd

from playwright_stealth import stealth_async  # NEW: Stealth plugin
from playwright.async_api import async_playwright
import aiomysql


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
    "host": st.secrets["DB_HOST"],
    "user": st.secrets["DB_USER"],
    "password": st.secrets["DB_PASSWORD"],
    "db": st.secrets["DB_NAME"],
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

from playwright_stealth import stealth_async  # Ensure this is in requirements.txt

async def run_scraper():
    process_id = str(uuid.uuid4())
    pool = None
    # 'driver' is no longer needed as we use Playwright directly

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

        add_log("Launching Stealth Browser...")

        # ---------------------------------------------------
        # UPDATED: START PLAYWRIGHT DIRECTLY WITH STEALTH
        # ---------------------------------------------------
        async with async_playwright() as p:
            # Launch Chromium (Railway/Render will find the path automatically)
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )

            # Create a context with a real-world User-Agent
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()

            # Apply stealth to hide Playwright fingerprints
            await stealth_async(page)

            bulk_data = []
            results_table = []

            # ---------------------------------------------------
            # LOOP KEYWORDS (Rest of your logic remains the same)
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

                for page_num in range(pages_per_keyword):
                    await asyncio.sleep(random.uniform(2, 4))

                    # Use a more reliable selector for Google results
                    results = await page.locator("div.g").all()

                    for res in results:
                        # Extracting link using your existing evaluate logic
                        item = await res.evaluate("""
                            (node) => {
                                const h3 = node.querySelector('h3');
                                return h3 ? { link: node.querySelector('a')?.href } : null;
                            }
                        """)

                        if item and item.get("link"):
                            link = item["link"]
                            add_log(f"Checking Rank {current_rank}")

                            if target_domain.lower() in link.lower():
                                found_rank = current_rank
                                add_log(f"FOUND at Rank {current_rank}")
                                break
                            current_rank += 1

                    if found_rank:
                        break

                    next_btn = page.locator("a#pnnext").first
                    if await next_btn.is_visible():
                        await next_btn.click()
                        await page.wait_for_load_state("domcontentloaded")
                    else:
                        break

                final_rank = found_rank if found_rank else 51
                bulk_data.append((keyword_id, final_rank))
                results_table.append({
                    "Keyword": keyword,
                    "Domain": target_domain,
                    "Rank": final_rank
                })

            # ---------------------------------------------------
            # INSERT DATA
            # ---------------------------------------------------
            await bulk_insert_rankings(pool, bulk_data, created_by)
            await update_process_status(pool, process_id, 2)
            add_log("Scraping Completed")
            await browser.close()

            st.subheader("Ranking Results")
            st.dataframe(pd.DataFrame(results_table), use_container_width=True)

    except Exception as e:
        add_log(f"\nSCRAPER ERROR:\n{str(e)}")
        if pool:
            await update_process_status(pool, process_id, 3)

    finally:
        if pool:
            pool.close()
            await pool.wait_closed()

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
            await update_process_status(pool, process_id, 3)

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
