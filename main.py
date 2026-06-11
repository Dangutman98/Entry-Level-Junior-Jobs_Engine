import asyncio
import csv
import re
import datetime
import logging
import urllib.parse
import time
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import pandas as pd

import sys
import io
import json
import urllib.request
import urllib.parse
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper_log.txt", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
WHITELIST = ['backend', 'cloud infrastructure', 'ai', 'machine learning', 'cyber security', 'cyber', 'automation developer', 'sdet', 'devops']
BLACKLIST = ['senior', 'sênior', 'lead', 'principal', 'architect', 'manager', 'head', 'director', 'vp', 'data analyst', 'hr', 'sales', 'marketing', 'product', 'sr.', 'sr ']
ISRAEL_LOCATIONS = [
    'israel', r'\bil\b', 'tel aviv', 'tel-aviv', 'herzliya', 'haifa', 
    'petah tikva', 'petach tikva', 'jerusalem', 'raanana', "ra'anana", 
    'rehovot', 'kfar saba', 'netanya', 'yavne', 'hod hasharon', 'beer sheva',
    'ramat gan', 'bnei brak', 'givatayim', 'rishon', 'ashdod', 'holon', 'bat yam'
]
URL_BLACKLIST = [
    '/blog/', '/article/', '/news/', '/insights/', '/story/', 
    'medium.com', 'nucamp.co', 'builtin.com', 'techcrunch.com',
    'glassdoor.com/Reviews', 'glassdoor.com/Salary'
]
TECH_KEYWORDS = [
    'aws', 'docker', 'terraform', 'kubernetes', 'k8s', 'python', 'java', 
    'node.js', 'nodejs', 'react', 'vue', 'angular', 'c++', 'c#', 'go', 'golang', 
    'sql', 'nosql', 'mongodb', 'postgresql', 'mysql', 'gcp', 'azure', 
    'ci/cd', 'jenkins', 'git', 'linux', 'typescript', 'javascript', 'ruby'
]
EXCLUDE_REMOTE = [
    'us only', 'us remote', 'uk only', 'europe only', 'eu only', 
    'est time zone', 'pst time zone', 'remote - us', 'remote us', 
    'united states', 'must reside in us', 'north america only'
]

def discover_job_links():
    logger.info("Step 1: Aggressive Discovery (Israel Only)...")
    queries = [
        'site:greenhouse.io israel jobs backend',
        'site:lever.co israel startup developer',
        'site:comeet.com jobs tel aviv',
        'tech startups Israel career page jobs',
        'junior software engineering jobs Israel'
    ]
    
    found_urls = set()
    job_urls = []
    
    for query in queries:
        logger.info(f"Querying: {query}")
        try:
            r = requests.post('https://html.duckduckgo.com/html/', data={'q': query}, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.select('.result__url'):
                url = a.get('href', '').strip()
                if url.startswith('//'): url = 'https:' + url
                elif url.startswith('/'): url = 'https://duckduckgo.com' + url
                    
                if url and url not in found_urls and url.startswith('http'):
                    found_urls.add(url)
                    job_urls.append(url)
                    if len(job_urls) >= 100: break
            time.sleep(2)
        except Exception as e:
            logger.error(f"Search error {query}: {e}")
            
        if len(job_urls) >= 100: break
        
    return job_urls

async def extract_page_data(page):
    """Extract Title, Company, Location from page structure"""
    try:
        title = await page.title()
        company = urllib.parse.urlparse(page.url).netloc.replace('job-boards.', '').replace('jobs.', '').split('.')[0].capitalize()
        
        # Try to find a header for the job title
        h1s = await page.locator('h1').all_inner_texts()
        job_title = h1s[0].strip() if h1s else title.split('-')[0].strip()
        
        # Extract tech stack
        content = await page.content()
        content_lower = content.lower()
        found_tech = []
        for kw in TECH_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', content_lower):
                if kw == 'nodejs': kw = 'node.js'
                if kw == 'k8s': kw = 'kubernetes'
                found_tech.append(kw.capitalize() if len(kw) > 3 else kw.upper())
        tech_stack = ", ".join(list(set(found_tech))) if found_tech else "Not Specified"
        
        return job_title, company, tech_stack, content
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return "Unknown", "Unknown", "Unknown", ""

async def verify_job_posting(page, url):
    """Deep navigation to verify if job is active and valid."""
    # Check URL against Blacklist
    url_lower = url.lower()
    if any(blacklisted in url_lower for blacklisted in URL_BLACKLIST):
        logger.info(f"Skipping blog/article URL: {url}")
        return None, None, None, None

    logger.info(f"Step 2: Availability Verification -> {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Handle simple redirects to homepage or 404s
        if "404" in await page.title() or "not found" in (await page.title()).lower():
            return None, None, None, None
            
        content = await page.content()
        negative_signals = ['no longer accepting', 'closed', 'filled', 'not available']
        if any(signal in content.lower() for signal in negative_signals):
            return None, None, None, None

        # Self-Check: Apply button existence
        apply_selectors = ['text=/apply/i', 'text=/הגש/i', 'button:has-text("Apply")', 'a:has-text("Apply")', 'input[type="submit"]']
        found_apply = False
        for selector in apply_selectors:
            if await page.locator(selector).count() > 0:
                found_apply = True
                break
        
        if not found_apply:
            logger.warning("No apply button found. Discarding generic page.")
            return None, None, None, None
            
        job_title, company, tech_stack, content = await extract_page_data(page)
        return job_title, company, tech_stack, content
    except Exception as e:
        logger.error(f"Failed to verify {url}: {e}")
        return None, None, None, None

def is_strictly_israel(text):
    text_lower = text.lower()
    for loc in ISRAEL_LOCATIONS:
        if loc == r'\bil\b':
            if re.search(loc, text_lower): return True
        else:
            if loc in text_lower: return True
    return False

def check_blacklist_and_qa(text):
    text_lower = text.lower()
    if 'data analyst' in text_lower: return False
    
    # QA is blacklisted unless accompanied by automation/sdet
    if re.search(r'\bqa\b', text_lower) and not any(x in text_lower for x in ['automation', 'sdet']):
        return False
        
    # Check for aggregator/search pages
    bad_patterns = ["jobs in", "all jobs", "search", "results", "?q="]
    if any(p in text_lower for p in bad_patterns):
        logger.warning(f"Discarding aggregator/search page: {text}")
        return False
        
    return not any(b in text_lower for b in BLACKLIST)

def update_jobs_js():
    try:
        df = pd.read_csv("relevant_jobs.csv", encoding="utf-8-sig")
        jobs_list = []
        for _, row in df.iterrows():
            title = str(row.get('Job Title', '')).lower()
            category = 'Backend'
            if 'frontend' in title or 'fullstack' in title or 'full stack' in title or 'react' in title:
                category = 'Frontend'
            elif 'devops' in title or 'cloud' in title or 'sre' in title:
                category = 'DevOps'
            elif 'data' in title or 'ai' in title or 'machine learning' in title or 'algorithm' in title:
                category = 'Data'
            elif 'qa' in title or 'automation' in title or 'test' in title:
                category = 'QA'
            elif 'cyber' in title or 'security' in title:
                category = 'Cyber'
                
            tech_raw = str(row.get('Tech Stack', ''))
            techs = [t.strip() for t in tech_raw.split(',') if t.strip()]
            
            jobs_list.append({
                'company': str(row.get('Company', 'Unknown')),
                'title': str(row.get('Job Title', '')),
                'location': str(row.get('Location', '')),
                'type': 'Entry Level',
                'techStack': techs,
                'link': str(row.get('Job Link', '')),
                'category': category,
                'status': str(row.get('Application Status', 'Not Applied')),
                'dateFound': str(row.get('Date Found', ''))
            })
        
        # Write directly to dashboard.html to avoid local script loading issues
        with open("dashboard.html", "r", encoding="utf-8") as f:
            html_content = f.read()
            
        # Find the script block and replace window.jobsData = ...
        pattern = r"window\.jobsData\s*=\s*\[.*?\];"
        new_data = "window.jobsData = " + json.dumps(jobs_list, ensure_ascii=False, indent=4) + ";"
        
        # Replace the entire array block using a lambda to prevent parsing escape sequences like \n
        if re.search(pattern, html_content, re.DOTALL):
            html_content = re.sub(pattern, lambda m: new_data, html_content, flags=re.DOTALL)
        else:
            # If not found, we insert it right after <script>
            html_content = html_content.replace("<script>", "<script>\n        " + new_data)
            
        with open("dashboard.html", "w", encoding="utf-8") as f:
            f.write(html_content)
            
        logger.info("Successfully updated dashboard.html with new jobs.")
    except Exception as e:
        logger.error(f"Failed to update dashboard.html: {e}")

def send_email_notification(new_jobs):
    email_user = os.environ.get("EMAIL_USERNAME")
    email_pass = os.environ.get("EMAIL_PASSWORD")
    
    if not email_user or not email_pass:
        logger.warning("Email credentials not found. Skipping email notification.")
        return
        
    if not new_jobs:
        return
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚀 New Tech Jobs Found - Daily Digest"
        msg["From"] = email_user
        msg["To"] = email_user
        
        # Create HTML table
        html = """
        <html>
          <body>
            <h2>Here are the new entry-level jobs found today:</h2>
            <table border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse; width: 100%;">
              <tr style="background-color: #f2f2f2;">
                <th>Company</th>
                <th>Job Title</th>
                <th>Location</th>
                <th>Link</th>
              </tr>
        """
        for job in new_jobs:
            html += f"""
              <tr>
                <td><b>{job.get('Company', 'N/A')}</b></td>
                <td>{job.get('Job Title', 'N/A')}</td>
                <td>{job.get('Location', 'N/A')}</td>
                <td><a href="{job.get('Job Link', '#')}">Apply Here</a></td>
              </tr>
            """
        html += """
            </table>
            <br>
            <p>Check your full <a href="https://Dangutman98.github.io/Entry-Level-Junior-Jobs_Engine/dashboard.html">Live Dashboard</a> for more details.</p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(html, "html"))
        
        # Connect and send
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_user, msg.as_string())
            
        logger.info("Email notification sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send Email notification: {e}")

async def run_scraper():
    logger.info("Starting Self-Verifying Job Hunting Engine...")
    
    # Step 1: Discovery
    job_urls = discover_job_links()
    if not job_urls:
        logger.error("No URLs discovered.")
        return
        
    results = []
    seen_jobs = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = await context.new_page()

        for url in job_urls:
            # Step 2: Ghost Filter
            job_title, company, tech_stack, job_desc = await verify_job_posting(page, url)
            if not job_desc:
                continue
                
            dedup_id = f"{company}_{job_title}".lower()
            if dedup_id in seen_jobs:
                continue
                
            # Step 3: Intent Matching
            job_desc_lower = job_desc.lower()
            
            if not check_blacklist_and_qa(job_desc_lower):
                logger.info(f"Discarded {job_title} due to Blacklist.")
                continue
                
            if not any(term in job_desc_lower for term in WHITELIST):
                logger.info(f"Discarded {job_title} due to missing Whitelist terms.")
                continue
                
            if not is_strictly_israel(job_desc_lower):
                logger.info(f"Discarded {job_title} due to Location (Not Israel).")
                continue
                
            if any(exc in job_desc_lower for exc in EXCLUDE_REMOTE):
                logger.info(f"Discarded {job_title} due to remote exclusion.")
                continue
            
            # Experience Check
            years_match = re.search(r'(\d+)\+?\s*(?:to|-)?\s*(\d+)?\s*\+?\s*(?:years?|yrs?)', job_desc_lower)
            if years_match:
                exp_req = int(years_match.group(1))
                if exp_req >= 3:
                    logger.info(f"Discarded {job_title} due to Experience ({exp_req} years).")
                    continue
            
            # Step 4: Extraction Self-Check
            if not job_title or not company or not url:
                logger.warning(f"Discarded due to missing critical fields: {company} - {job_title}")
                continue
                
            seen_jobs.add(dedup_id)
            results.append({
                'Company': company,
                'Job Title': job_title,
                'Location': 'Israel',
                'Tech Stack': tech_stack,
                'Job Link': url,
                'Date Found': datetime.date.today().strftime("%Y-%m-%d"),
                'Application Status': 'Not Applied'
            })
            
        await browser.close()
        
    # Send Email Notification if new jobs are found
    if results:
        send_email_notification(results)

    # Final Export
    if results:
        out_csv = "relevant_jobs.csv"
        try:
            existing_df = pd.read_csv(out_csv, encoding='utf-8-sig')
            df_out = pd.DataFrame(results)
            combined_df = pd.concat([existing_df, df_out]).drop_duplicates(subset=['Job Link', 'Job Title'], keep='last')
            combined_df.to_csv(out_csv, index=False, encoding='utf-8-sig')
            logger.info(f"Engine Run Complete! {len(results)} fully verified new jobs added to {out_csv}.")
        except Exception as e:
            fallback = f"relevant_jobs_engine_{int(time.time())}.csv"
            df_out = pd.DataFrame(results)
            df_out.to_csv(fallback, index=False, encoding='utf-8-sig')
            logger.error(f"Could not merge with existing CSV: {e}. Saved to {fallback}.")
            
    else:
        logger.info("Engine Run Complete! No new verified jobs found matching all criteria.")

    # Always update jobs.js for the HTML dashboard
    update_jobs_js()

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.run(run_scraper())
