import sys
import asyncio
import re
from playwright.async_api import async_playwright

async def _get_attendance_async(username, password):
    """
    Scrapes attendance data from MITS IMS portal using Playwright.
    """
    async with async_playwright() as p:
        browser = None
        try:
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
            except Exception as launch_err:
                import subprocess
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # 1. Open the website
            await page.goto("http://mitsims.in/", timeout=60000)

            # 2. Click the student login link
            await page.click("#studentLink", force=True)
            
            # Wait for student fields
            await page.wait_for_selector("#inputStuId", state="visible", timeout=10000)

            # 3. Enter credentials
            await page.fill("#studentForm #inputStuId", username)
            await page.fill("#studentForm #inputPassword", password)

            # 4. Click login
            await page.click("#studentSubmitButton", force=True)
            
            # 5. Handle potential errors or redirects
            try:
                # Wait for any of the success indicators
                await page.wait_for_selector(".dashboard, #studentIndex, #studentName, [href*='logout']", timeout=15000)
            except Exception:
                current_url = page.url
                # If stuck on redirect page, give it a moment
                if "studentReDirect" in current_url:
                    try:
                        await page.wait_for_url("**/studentIndex.html", timeout=10000)
                    except Exception:
                        pass

                # Re-check for success indicators after redirect wait
                if not (await page.locator(".dashboard, #studentIndex, #studentName, [href*='logout']").count() > 0):
                    raw_err = ""
                    if await page.locator(".alert-danger, #loginError, .errorMessage").count() > 0:
                        raw_err = await page.locator(".alert-danger, #loginError, .errorMessage").text_content() or ""
                    
                    cleaned_err = re.sub(r'[\r\n\t\\]+', ' ', str(raw_err)).strip()
                    if not cleaned_err:
                        cleaned_err = "Login failed. Please check your Student ID and Password."

                    return {"error": cleaned_err}

            # 6. Scraping Task - Primary Strategy: DOM Table Extraction
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(4)

            attendance_list = []

            # Strategy 1: Parse HTML <tr> table rows directly
            rows = await page.locator("tr").all()
            for row in rows:
                try:
                    cells = await row.locator("td, th").all()
                    if len(cells) >= 4:
                        texts = [(await c.inner_text()).strip() for c in cells]
                        texts = [t.replace('\xa0', ' ').strip() for t in texts]

                        subject, attended, total, percentage = None, None, None, None

                        # 5-column table row: [S.NO, SUBJECT CODE/NAME, CLASSES ATTENDED, TOTAL CONDUCTED, ATTENDANCE %]
                        if len(texts) >= 5 and re.match(r'^\d+$', texts[0]):
                            subject = texts[1]
                            attended = texts[2]
                            total = texts[3]
                            percentage = texts[4]
                        # 4-column table row: [SUBJECT CODE/NAME, CLASSES ATTENDED, TOTAL CONDUCTED, ATTENDANCE %]
                        elif len(texts) == 4 and not any(kw in texts[0].upper() for kw in ["SUBJECT", "S.NO", "SERIAL", "CODE"]):
                            subject = texts[0]
                            attended = texts[1]
                            total = texts[2]
                            percentage = texts[3]

                        if subject and len(subject) > 1 and not any(kw in subject.upper() for kw in ["SUBJECT", "S.NO", "TOTAL CONDUCTED", "CLASSES ATTENDED"]):
                            # Normalize hyphen/dash values: '-' -> '0' or '0.0'
                            att_clean = "0" if attended == "-" else attended
                            tot_clean = "0" if total == "-" else total
                            perc_clean = "0.0" if percentage == "-" else percentage.replace("%", "").strip()

                            attendance_list.append({
                                "subject": subject,
                                "attended": att_clean,
                                "total": tot_clean,
                                "percentage": perc_clean
                            })
                except Exception:
                    continue

            # Strategy 2: Hybrid Text-Line Fallback (if DOM table rows were empty)
            if len(attendance_list) < 3:
                full_text = await page.inner_text("body")
                lines = [l.strip() for l in full_text.split('\n') if l.strip()]

                for i, line in enumerate(lines):
                    is_subject_code = re.match(r'^\d*[A-Z]+\d+[A-Z0-9]*$', line)
                    is_subject_name = (line.isupper() and len(line) > 5 and not re.search(r'\d', line[:5]))
                    exclude_keywords = ["TOTAL", "ATTENDANCE", "SUBJECT", "CLASSES", "CONDUCTED", "S.NO", "SERIAL"]
                    if (is_subject_code or is_subject_name) and not any(kw in line.upper() for kw in exclude_keywords):
                        try:
                            lookahead = lines[i+1 : i+12]
                            tokens = []
                            for sub_line in lookahead:
                                match = re.search(r'^(\d+\.?\d*|-)$', sub_line)
                                if match:
                                    tokens.append(match.group(1))
                                if len(tokens) >= 3:
                                    break

                            if len(tokens) >= 3:
                                att_clean = "0" if tokens[0] == "-" else tokens[0]
                                tot_clean = "0" if tokens[1] == "-" else tokens[1]
                                perc_clean = "0.0" if tokens[2] == "-" else tokens[2]

                                attendance_list.append({
                                    "subject": line,
                                    "attended": att_clean,
                                    "total": tot_clean,
                                    "percentage": perc_clean
                                })
                        except Exception:
                            continue

            # Clean & Deduplicate Results
            unique_attendance = []
            seen_subjects = set()
            for item in attendance_list:
                clean_name = item["subject"].replace(":", "").strip()
                exclude_keywords = ["SUBJECT CODE", "CLASSES ATTENDED", "TOTAL CONDUCTED", "ATTENDANCE %", "S.NO"]
                if clean_name not in seen_subjects and len(clean_name) > 1 and not any(kw in clean_name.upper() for kw in exclude_keywords):
                    unique_attendance.append({
                        "subject": clean_name,
                        "attended": item["attended"],
                        "total": item["total"],
                        "percentage": item["percentage"]
                    })
                    seen_subjects.add(clean_name)

            if not unique_attendance:
                return {"error": "Attendance data not found. Please ensure you have access to the dashboard and try again."}


            return unique_attendance

        except Exception as e:
            err_str = re.sub(r'[\r\n\t\\]+', ' ', str(e)).strip()
            if not err_str:
                err_str = type(e).__name__
            return {"error": f"Scraping error: {err_str}"}
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass


def _sync_scrape_worker(username, password):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.run(_get_attendance_async(username, password))


async def get_attendance(username, password):
    """
    Asynchronous wrapper calling worker thread for clean event loop isolation.
    Solves Windows Uvicorn asyncio NotImplementedError for Playwright subprocesses.
    """
    return await asyncio.to_thread(_sync_scrape_worker, username, password)
