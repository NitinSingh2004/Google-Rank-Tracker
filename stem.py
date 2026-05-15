import streamlit as st
import asyncio
import random
import uuid
import aiomysql
import subprocess
import pandas as pd
from seleniumbase import cdp_driver
from playwright.async_api import async_playwright

# # --- PLAYWRIGHT DEPENDENCY INSTALLATION ---
# @st.cache_resource
# def install_playwright():
#     try:
#         subprocess.run(
#             ["playwright", "install", "chromium"],
#             check=True
#         )
#     except Exception as e:
#         st.error(f"Playwright install error: {e}")

# install_playwright()


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
    driver = None
    browser = None

    process_id = str(uuid.uuid4())
    pool = await aiomysql.create_pool(**DB_CONFIG)

    try:
        await insert_process(pool, process_id)
        keywords_data = await get_keywords(pool)
        st.write(keywords_data)

        if not keywords_data:
            await update_process_status(pool, process_id, 2)
            return [{"message": "No keywords found"}]

        # ---------------------------------------------------
        # START CDP_DRIVER (SeleniumBase Undetected Core)
        # ---------------------------------------------------
        driver = await cdp_driver.start_async(
            headless=True,  # Mandatory for Streamlit Cloud deployments
            undetected=True,
            extra_params=[
                "--no-sandbox",
                "--disable-dev-shm-usage",  # Shared memory fix for small container limits
                "--disable-gpu",            # Hardware graphics emulation workaround
                "--disable-setuid-sandbox"
            ]
        )

        endpoint_url = driver.get_endpoint_url()

        # ---------------------------------------------------
        # CONNECT PLAYWRIGHT OVER THE LIVE CDP ENDPOINT
        # ---------------------------------------------------
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(endpoint_url)
            page = browser.contexts[0].pages[0]
            await page.set_viewport_size({"width": 1366, "height": 768})

            for keyword_id, keyword, target_domain in keywords_data:
                st.write(f"Searching: {keyword}")

                search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"

                await page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                await asyncio.sleep(random.uniform(2, 5))

                # --- 1. CAPTCHA CHECK ON INITIAL LOAD ---
                is_captcha = await page.locator("#captcha-form, input[name='captcha']").count() > 0
                page_text = await page.content()
                
                if is_captcha or "unusual traffic from your computer network" in page_text:
                    st.warning(f"Google blocked the request with a CAPTCHA for keyword: {keyword}")
                    results_output.append({
                        "keyword": keyword,
                        "domain": target_domain,
                        "rank": "CAPTCHA",
                        "url": "CAPTCHA Encountered"
                    })
                    bulk_data.append((keyword_id, 0)) 
                    continue 

                current_rank = 1
                found_rank = None

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

                    try:
                        next_btn = page.locator("a#pnnext").first
                        if await next_btn.is_visible():
                            await next_btn.click()
                            await page.wait_for_load_state("domcontentloaded")
                            
                            # --- 2. CAPTCHA CHECK ON PAGINATION ---
                            if await page.locator("#captcha-form").count() > 0:
                                st.warning("CAPTCHA triggered on pagination.")
                                found_rank = "CAPTCHA"
                                results_output.append({
                                    "keyword": keyword,
                                    "domain": target_domain,
                                    "rank": "CAPTCHA",
                                    "url": "CAPTCHA Encountered"
                                })
                                break
                        else:
                            break
                    except:
                        break

                if not found_rank:
                    found_rank = 100
                    results_output.append({
                        "keyword": keyword,
                        "domain": target_domain,
                        "rank": found_rank,
                        "url": "Not Found"
                    })
                
                db_rank = 0 if found_rank == "CAPTCHA" else found_rank
                bulk_data.append((keyword_id, db_rank))

            # Database updates & clean closures
            await bulk_insert_rankings(pool, bulk_data, created_by)
            await update_process_status(pool, process_id, 2)
            await browser.close()

    except Exception as e:
        if pool:
            await update_process_status(pool, process_id, 3)
        raise e
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass
        if driver:
            try:
                driver.quit()
            except:
                pass
        if pool:
            pool.close()
            await pool.wait_closed()

    return results_output


# --- STREAMLIT UI LAYOUT ---
st.set_page_config(
    page_title="Google Rank Tracker"
)

st.title(
    "Google Ranking Tracker - CDP Driver Mode"
)

fixed_number = 10
fixed_number2 = 33

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
