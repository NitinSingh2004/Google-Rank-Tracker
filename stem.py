import streamlit as st
import random
import uuid
import aiomysql
import pandas as pd
import asyncio
import time

from seleniumbase import Driver

# ---------------- DB CONFIG ----------------
DB_CONFIG = {
    "host": "43.230.202.147",
    "user": "ewayswork_seotoo",
    "password": "kCPZk9wkL.1GfoZP",
    "db": "ewayswork_seotool",
}

# ---------------- DB FUNCTIONS ----------------
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
            # Note: Verify your schema uses 'KeywordNo' or 'KeywordID' to match your history table structure
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

# ---------------- MAIN ASYNC RUNNER ----------------
async def run_rank_tracker_async(pages_per_keyword, created_by):
    results_output = []
    bulk_data = []
    process_id = str(uuid.uuid4())
    
    pool = await aiomysql.create_pool(**DB_CONFIG)

    try:
        await insert_process(pool, process_id)
        keywords_data = await get_keywords(pool)

        st.write(f"Found {len(keywords_data)} keywords to track.")

        if not keywords_data:
            await update_process_status(pool, process_id, 2)
            return [{"message": "No keywords found"}]

        # Initialize UC Driver via SeleniumBase
        driver = Driver(uc=True, headless=True)

        for keyword_id, keyword, target_domain in keywords_data:
            st.write(f"🔍 Searching: **{keyword}** for domain *{target_domain}*")
            search_url = "https://www.google.com/search?q=" + keyword.replace(" ", "+")

            driver.get(search_url)
            time.sleep(random.uniform(2, 4))

            page_source = driver.page_source
            if "captcha" in page_source.lower() or "unusual traffic" in page_source.lower():
                st.warning(f"⚠️ CAPTCHA detected on initial search for: {keyword}")
                results_output.append({
                    "keyword": keyword, "domain": target_domain,
                    "rank": "CAPTCHA", "url": "CAPTCHA Encountered"
                })
                bulk_data.append((keyword_id, 0))
                continue

            current_rank = 1
            found_rank = None
            captcha_triggered = False

            for page in range(pages_per_keyword):
                time.sleep(random.uniform(1.5, 3))
                results = driver.find_elements("css selector", "div.g")

                for res in results:
                    try:
                        link_element = res.find_elements("css selector", "a")
                        if not link_element:
                            continue
                        link = link_element[0].get_attribute("href")

                        if link and target_domain.lower() in link.lower():
                            found_rank = current_rank
                            results_output.append({
                                "keyword": keyword, "domain": target_domain,
                                "rank": current_rank, "url": link
                            })
                            break
                        
                        current_rank += 1
                    except Exception:
                        pass

                if found_rank:
                    break  # Found the domain target, move to next keyword

                # If not found on this page, attempt pagination
                if page < pages_per_keyword - 1:
                    try:
                        next_btn = driver.find_elements("css selector", "a#pnnext")
                        if next_btn:
                            next_btn[0].click()
                            time.sleep(2)
                            
                            if "captcha" in driver.page_source.lower():
                                st.warning(f"⚠️ CAPTCHA triggered on pagination for: {keyword}")
                                captcha_triggered = True
                                break
                        else:
                            break # No more Google pages available
                    except Exception:
                        break

            # Process final status assignment for this keyword loop
            if captcha_triggered:
                results_output.append({
                    "keyword": keyword, "domain": target_domain,
                    "rank": "CAPTCHA", "url": "CAPTCHA Encountered"
                })
                bulk_data.append((keyword_id, 0))
            elif not found_rank:
                results_output.append({
                    "keyword": keyword, "domain": target_domain,
                    "rank": 100, "url": "Not Found"
                })
                bulk_data.append((keyword_id, 100))
            else:
                bulk_data.append((keyword_id, found_rank))

        driver.quit()
        
        if bulk_data:
            await bulk_insert_rankings(pool, bulk_data, created_by)
        await update_process_status(pool, process_id, 2)

    except Exception as e:
        # Avoid crashing if pool failed to initialize early
        if 'pool' in locals():
            await update_process_status(pool, process_id, 3)
        raise e
    finally:
        if 'pool' in locals():
            pool.close()
            await pool.wait_closed()

    return results_output


# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="Google Rank Tracker", layout="wide")
st.title("Google Ranking Tracker - SeleniumBase CDP")

pages_per_keyword = st.number_input(
    "Pages Per Keyword",
    min_value=1,
    max_value=10,
    value=10
)

created_by = st.number_input(
    "Created By",
    value=33,
    disabled=True
)

if st.button("Start Tracking"):
    with st.spinner("Tracking Rankings..."):
        try:
            # Streamlit safe async helper execution engine
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            results = loop.run_until_complete(
                run_rank_tracker_async(pages_per_keyword, created_by)
            )

            st.success("Tracking Completed 🎉")
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
