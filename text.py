import asyncio
import json
import random
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright
from seleniumbase import cdp_driver

app = FastAPI(title="SEO Rank Tracker API")


class SearchRequest(BaseModel):
    keywords: List[str] = ["anniversary flowers"]
    target_urls: List[str] = [ "fnp.com"]
    pages_per_keyword: int = 1


async def run_seo_scraper(keywords, target_urls, pages_per_keyword):
    results_output = {}

    # Capture the driver instance so we can quit it later
    driver = await cdp_driver.start_async(locale="en")
    endpoint_url = driver.get_endpoint_url()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(endpoint_url)
            page = browser.contexts[0].pages[0]

            for keyword in keywords:
                search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
                await page.goto(search_url, wait_until="networkidle")

                final_data = []
                current_rank = 1
                found_targets = []

                for page_num in range(pages_per_keyword):
                    await asyncio.sleep(random.uniform(2, 4))
                    await page.evaluate("window.scrollBy(0, 800)")

                    results = await page.locator('div[data-hveid], div.g').all()

                    for res in results:
                        item = await res.evaluate("""(node) => {
                            const clean = (str) => {
                                if (!str) return "";
                                return str.normalize("NFKD").replace(/[\\r\\n\\t]+/g, ' ').trim();
                            };
                            const h3 = node.querySelector('h3');
                            if (!h3) return null;
                            return {
                                title: clean(h3.innerText),
                                link: node.querySelector('a')?.href,
                            };
                        }""")

                        if item and item['title'] and "google.com" not in (item['link'] or ""):
                            if not any(d['title'] == item['title'] for d in final_data):
                                item['rank'] = current_rank

                                link_lower = item['link'].lower()
                                for target in target_urls:
                                    if target.lower() in link_lower:
                                        item['is_target'] = True
                                        item['target_name'] = target
                                        found_targets.append(
                                            f"Found {target} at Rank {current_rank}")

                                final_data.append(item)
                                current_rank += 1

                    if page_num < pages_per_keyword - 1:
                        next_button = page.locator(
                            'a#pnnext, a:has-text("Next")').first
                        if await next_button.is_visible():
                            await asyncio.sleep(random.uniform(1, 2))
                            await next_button.click()
                            await page.wait_for_load_state("networkidle")
                        else:
                            break

                results_output[keyword] = {
                    "summary": found_targets,
                    "data": final_data
                }

            await browser.close()
            return results_output

    finally:
       
         driver.quit()


@app.post("/track-rankings")
async def track_rankings(request: SearchRequest):
    try:
        data = await run_seo_scraper(
            request.keywords,
            request.target_urls,
            request.pages_per_keyword
        )
        return data
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

