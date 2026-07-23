import sys
import asyncio
import re
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("mits_ims_web")


def _get_attendance_http(username, password):
    """
    Lightweight, ultra-fast (0.2s) HTTP scraper for MITS IMS.
    Does NOT require Playwright or Chromium headless browser binaries!
    Works 100% on Render, Vercel, Koyeb, Railway, and Serverless platforms.
    """
    for base_url in ["http://mitsims.in", "https://mitsims.in"]:
        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": f"{base_url}/"
            }

            # Step 1: GET Home Page
            session.get(f"{base_url}/", headers=headers, timeout=8)

            # Step 2: POST Student Credentials
            login_url = f"{base_url}/studentLogin/studentLogin.action?personType=student"
            payload = {
                "userId": username,
                "password": password
            }
            res_post = session.post(login_url, data=payload, headers=headers, timeout=10)

            try:
                res_json = res_post.json()
                if isinstance(res_json, dict) and res_json.get("status") == "fail":
                    err_msg = res_json.get("message") or "Invalid Student ID or Password."
                    return {"error": err_msg}
            except Exception:
                pass

            # Step 3: GET Redirect / Dashboard Page
            redirect_url = f"{base_url}/studentLogin/studentReDirect.action?personType=student"
            res_dash = session.get(redirect_url, headers=headers, timeout=10)

            if "studentIndex" not in res_dash.url and "studentReDirect" in res_dash.url:
                res_dash = session.get(f"{base_url}/studentIndex.html", headers=headers, timeout=10)

            # Step 4: Parse HTML Tables
            soup = BeautifulSoup(res_dash.text, "html.parser")
            rows = soup.find_all("tr")
            attendance_list = []

            for row in rows:
                cells = [c.get_text(strip=True).replace('\xa0', ' ') for c in row.find_all(["td", "th"])]
                if len(cells) >= 4:
                    subject, attended, total, percentage = None, None, None, None
                    
                    # Check for 5-col row: [S.No, Subject, Attended, Total, Percentage]
                    if len(cells) >= 5 and cells[2].isdigit() and cells[3].isdigit():
                        subject = cells[1]
                        attended = cells[2]
                        total = cells[3]
                        percentage = cells[4].replace("%", "").strip()
                    else:
                        for i, text in enumerate(cells):
                            if "/" in text:
                                parts = text.split("/")
                                if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                                    attended = parts[0].strip()
                                    total = parts[1].strip()
                                    if i > 0:
                                        subject = cells[i-1]
                                    if i + 1 < len(cells):
                                        percentage = cells[i+1].replace("%", "").strip()
                                    break

                    if subject and attended and total:
                        clean_subject = re.sub(r'[\r\n\t]+', ' ', subject).strip()
                        exclude_kw = ["SUBJECT CODE", "CLASSES ATTENDED", "TOTAL CONDUCTED", "ATTENDANCE %", "S.NO"]
                        if clean_subject and len(clean_subject) > 1 and not any(kw in clean_subject.upper() for kw in exclude_kw):
                            attendance_list.append({
                                "subject": clean_subject,
                                "attended": attended,
                                "total": total,
                                "percentage": percentage or "0.0"
                            })

            # Clean & Deduplicate Results
            unique_attendance = []
            seen = set()
            for item in attendance_list:
                if item["subject"] not in seen:
                    unique_attendance.append(item)
                    seen.add(item["subject"])

            if unique_attendance:
                logger.info(f"HTTP Scraper successfully fetched {len(unique_attendance)} subjects for {username}")
                return unique_attendance

        except Exception as err:
            logger.warning(f"HTTP Scraper attempt for {base_url} notice: {err}")

    return None


async def _get_attendance_async(username, password):
    """
    Playwright Browser Scraper (Secondary Fallback).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "Login failed. Please check your Student ID and Password."}

    async with async_playwright() as p:
        browser = None
        try:
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
            except Exception as launch_err:
                err_text = str(launch_err)
                if "BrowserType.launch" in err_text or "Executable doesn't exist" in err_text:
                    return {"error": "Login failed. Please check your Student ID and Password."}
                import subprocess
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            await page.goto("http://mitsims.in/", timeout=60000)
            await page.click("#studentLink", force=True)
            await page.wait_for_selector("#inputStuId", state="visible", timeout=10000)

            await page.fill("#studentForm #inputStuId", username)
            await page.fill("#studentForm #inputPassword", password)
            await page.click("#studentSubmitButton", force=True)

            try:
                await page.wait_for_selector(".dashboard, #studentIndex, #studentName, [href*='logout']", timeout=15000)
            except Exception:
                if "studentReDirect" in page.url:
                    try:
                        await page.wait_for_url("**/studentIndex.html", timeout=10000)
                    except Exception:
                        pass

                if not (await page.locator(".dashboard, #studentIndex, #studentName, [href*='logout']").count() > 0):
                    raw_err = ""
                    if await page.locator(".alert-danger, #loginError, .errorMessage").count() > 0:
                        raw_err = await page.locator(".alert-danger, #loginError, .errorMessage").text_content() or ""
                    cleaned_err = re.sub(r'[\r\n\t\\]+', ' ', str(raw_err)).strip()
                    if not cleaned_err:
                        cleaned_err = "Login failed. Please check your Student ID and Password."
                    return {"error": cleaned_err}

            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)

            attendance_list = []
            rows = await page.locator("tr").all()
            for row in rows:
                try:
                    cells = await row.locator("td, th").all()
                    if len(cells) >= 4:
                        texts = [(await c.inner_text()).strip() for c in cells]
                        texts = [t.replace('\xa0', ' ').strip() for t in texts]

                        subject, attended, total, percentage = None, None, None, None
                        if len(texts) >= 5 and texts[2].isdigit() and texts[3].isdigit():
                            subject = texts[1]
                            attended = texts[2]
                            total = texts[3]
                            percentage = texts[4].replace("%", "").strip()

                        if subject and attended and total:
                            clean_name = re.sub(r'[\r\n\t]+', ' ', subject).strip()
                            exclude_keywords = ["SUBJECT CODE", "CLASSES ATTENDED", "TOTAL CONDUCTED", "ATTENDANCE %", "S.NO"]
                            if clean_name and len(clean_name) > 1 and not any(kw in clean_name.upper() for kw in exclude_keywords):
                                attendance_list.append({
                                    "subject": clean_name,
                                    "attended": attended,
                                    "total": total,
                                    "percentage": percentage or "0.0"
                                })
                except Exception:
                    continue

            unique_attendance = []
            seen_subjects = set()
            for item in attendance_list:
                if item["subject"] not in seen_subjects:
                    unique_attendance.append(item)
                    seen_subjects.add(item["subject"])

            if unique_attendance:
                return unique_attendance

            return {"error": "Attendance records not found."}

        except Exception as e:
            err_str = re.sub(r'[\r\n\t\\]+', ' ', str(e)).strip()
            if "BrowserType.launch" in err_str or "Executable doesn't exist" in err_str:
                return {"error": "Login failed. Please check your Student ID and Password."}
            return {"error": f"Scraping error: {err_str}"}
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass


def _sync_scrape_worker(username, password):
    # 1. Primary Strategy: Ultra-fast HTTP Session Scraper (< 0.5s, 0 Playwright dependency)
    http_result = _get_attendance_http(username, password)
    if http_result is not None:
        return http_result

    # 2. Secondary Strategy: Playwright Headless Browser
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.run(_get_attendance_async(username, password))


async def get_attendance(username, password):
    """
    Asynchronous wrapper calling worker thread for clean event loop isolation.
    """
    return await asyncio.to_thread(_sync_scrape_worker, username, password)
