import streamlit as st
import random
import uuid
import aiomysql
import pandas as pd
import subprocess
import time

from seleniumbase import Driver


# ---------------- Install (kept same idea) ----------------
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["seleniumbase", "install", "chromedriver"], check=True)
    except Exception as e:
        st.error(f"Install error: {e}")

install_browser()


# ---------------- DB CONFIG ----------------
DB_CONFIG = {
    "host": "43.230.202.147",
    "user": "ewayswork_seotoo",
    "password": "kCPZk9wkL.1GfoZP",
    "db": "ewayswork_seotool",
}


# ---------------- DB FUNCTIONS (UNCHANGED LOGIC) ----------------
async def update_process_status(pool, process_id, status_code):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE scrapdata_process
                SET ProcessStatus = %s
                WHERE ProcessID = %s
            """, (status_code, process_id))
            await conn.commit()


async def insert_process(pool, process_id):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO scrapdata_process
                (ProcessID, ProcessStatus, type)
                VALUES (%s, %s, %s)
            """, (process_id, 1, 2))
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
            await cur.executemany("""
                INSERT INTO keywords_ranking_history
                (KeywordNo, Ranking, CreatedAt, CreatedBy)
                VALUES (%s, %s, NOW(), %s)
            """, [(k, r, created_by) for (k, r) in data])
            await conn.commit()


# ---------------- MAIN TRACKER (SELENIUM CDP VERSION) ----------------
def run_rank_tracker(pages_per_keyword, created_by):
    import asyncio

    results_output = []
    bulk_data = []

    async def runner():
        process_id = str(uuid.uuid4())
        pool = await aiomysql.create_pool(**DB_CONFIG)

        try:
            await insert_process(pool, process_id)
            keywords_data = await get_keywords(pool)

            st.write(keywords_data)

            if not keywords_data:
                await update_process_status(pool, process_id, 2)
                return [{"message": "No keywords found"}]

            # ---------------- SELENIUM CDP DRIVER ----------------
            driver = Driver(uc=True, headless=True)

            for keyword_id, keyword, target_domain in keywords_data:
                st.write(f"Searching: {keyword}")

                search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
                driver.get(search_url)
                time.sleep(random.uniform(2, 5))

                page_source = driver.page_source

                # CAPTCHA CHECK
                is_captcha = "captcha" in page_source.lower() or "unusual traffic" in page_source.lower()

                if is_captcha:
                    st.warning(f"CAPTCHA detected for: {keyword}")

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
                found_url = ""

                for _ in range(pages_per_keyword):
                    time.sleep(random.uniform(2, 4))

                    results = driver.find_elements("css selector", "div.g")

                    for res in results:
                        try:
                            link_el = res.find_element("css selector", "a")
                            link = link_el.get_attribute("href")

                            if link and target_domain.lower() in link.lower():
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

                    # NEXT PAGE
                    try:
                        next_buttons = driver.find_elements("css selector", "a#pnnext")

                        if next_buttons:
                            next_buttons[0].click()
                            time.sleep(2)

                            # CAPTCHA AGAIN CHECK
                            if "captcha" in driver.page_source.lower():
                                st.warning("CAPTCHA triggered on pagination")
                                results_output.append({
                                    "keyword": keyword,
                                    "domain": target_domain,
                                    "rank": "CAPTCHA",
                                    "url": "CAPTCHA Encountered"
                                })
                                found_rank = "CAPTCHA"
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

            driver.quit()

            await bulk_insert_rankings(pool, bulk_data, created_by)
            await update_process_status(pool, process_id, 2)

        except Exception as e:
            await update_process_status(pool, process_id, 3)
            raise e

        finally:
            pool.close()
            await pool.wait_closed()

        return results_output

    return asyncio.run(runner())


# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="Google Rank Tracker")

st.title("Google Ranking Tracker - Selenium CDP")

fixed_number = 10
fixed_number2 = 33

pages_per_keyword = st.number_input(
    "Pages Per Keyword",
    min_value=1,
    max_value=10,
    value=fixed_number
)

created_by = st.number_input(
    "Created By",
    value=fixed_number2,
    disabled=True
)

if st.button("Start Tracking"):

    with st.spinner("Tracking Rankings..."):
        try:
            results = run_rank_tracker(pages_per_keyword, created_by)

            st.success("Tracking Completed")

            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(str(e))
