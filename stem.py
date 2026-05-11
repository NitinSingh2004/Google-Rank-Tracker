import streamlit as st
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import os
import subprocess
import streamlit as st

# This function ensures the browser is installed only once per session
@st.cache_resource
def install_playwright():
    try:
        # Check if the browser is already present to save time
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Error installing Playwright: {e}")

# Call the install function
install_playwright()

async def run_playwright():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page()

        await page.goto("https://thegiftportal.com/")

        title = await page.title()
        content = await page.content()

        await browser.close()

        return title, content


st.title("Playwright Stealth with Streamlit")

if st.button("Run Browser"):
    with st.spinner("Opening website..."):
        try:
            title, content = asyncio.run(run_playwright())

            st.success("Website Loaded Successfully")
            st.write("Page Title:")
            st.code(title)

            st.write("HTML Preview:")
            st.code(content[:3000])

        except Exception as e:
            st.error(f"Error: {e}")
