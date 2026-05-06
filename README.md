# 🚀 SEO Rank Tracker (No SerpAPI)

A powerful **SEO Rank Tracking & Scraping Tool** built using Python, Playwright, and CDP that tracks **website rankings on Google based on keywords** — without using paid APIs like SerpAPI.

---

## 📌 Project Overview

This project allows you to:

- 🔍 Search any keyword on Google  
- 🌐 Extract top ranking websites  
- 📊 Track where **your website ranks** for that keyword  
- 📁 Store and monitor ranking data over time  

It simulates a real browser to bypass bot detection and ensures **accurate, real-time SERP data**.

---

## ⚙️ Tech Stack

- **Python**
- **Playwright (Browser Automation)**
- **CDP Driver (SeleniumBase)**
- **BeautifulSoup (HTML Parsing)**
- **Asyncio (Concurrency)**
- **JSON / CSV (Data Storage)**

---

## 🔧 How It Works

1. User inputs:
   - Target keyword  
   - Target website (domain)

2. System:
   - Opens Google search  
   - Scrapes top results (e.g., top 50)  
   - Extracts:
     - Title
     - URL
     - Position (Rank)

3. Ranking Detection:
   - Compares each result with your domain  
   - Finds exact ranking position  

4. Output:
   - Displays ranking in terminal  
   - Saves results to file  

---

## ▶️ Installation

```bash
pip install playwright seleniumbase beautifulsoup4
playwright install
