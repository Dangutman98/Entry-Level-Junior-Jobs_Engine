import asyncio
import pandas as pd
from playwright.async_api import async_playwright
from main import verify_job_posting, check_blacklist_and_qa, is_strictly_israel, WHITELIST, logger
import re

async def clean_csv():
    df = pd.read_csv("relevant_jobs.csv", encoding="utf-8-sig")
    pass # print(f"Starting cleanup of {len(df)} jobs...")
    valid_jobs = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = await context.new_page()

        for idx, row in df.iterrows():
            url = str(row["Job Link"])
            pass # print(f"Checking {idx+1}/{len(df)}: {url}")
            job_title, company, tech_stack, job_desc = await verify_job_posting(page, url)
            if not job_desc:
                pass # print(f" -> Failed verification.")
                continue
                
            job_desc_lower = job_desc.lower()
            if not check_blacklist_and_qa(job_desc_lower, job_title.lower()):
                pass # print(f" -> Blacklisted.")
                continue
                
            whitelist_matched = False
            for term in WHITELIST:
                if re.search(rf"\b{re.escape(term)}\b", job_desc_lower):
                    whitelist_matched = True
                    break
                    
            if not whitelist_matched:
                pass # print(f" -> No Whitelist match.")
                continue
                
            if not is_strictly_israel(job_desc_lower):
                pass # print(f" -> Not strictly Israel.")
                continue
                
            pass # print(f" -> Valid!")
            valid_jobs.append(row)
            
        await browser.close()
        
    new_df = pd.DataFrame(valid_jobs)
    new_df.to_csv("relevant_jobs.csv", index=False, encoding="utf-8-sig")
    from main import update_jobs_js
    update_jobs_js()
    pass # print(f"Cleanup done! Kept {len(new_df)}/{len(df)} jobs.")

if __name__ == "__main__":
    asyncio.run(clean_csv())
