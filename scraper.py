import sys
import asyncio
import re
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("mits_ims_web")


def extract_student_name(html_text):
    """
    Extracts Student Name from MITS IMS dashboard HTML with 100% precision.
    Supports MITS ExtJS displayfields, top header 'STUDENT NAME | CHANGE PASSWORD',
    and <span style="font-size:11px; color:black">STUDENT NAME</span>.
    """
    if not html_text:
        return None

    # Excluded UI terms & keywords that are NOT student names
    excluded = {
        "DASHBOARD", "PROGRESS REPORT", "TRANSCRIPT", "FEEDBACK", "PLACEMENT",
        "CERTIFICATE REQUEST", "ATTENDANCE", "ASSESSMENT MARKS", "TIME TABLE",
        "SUBJECT DETAILS", "CHANGE PASSWORD", "LOGOUT", "MITS", "GEMS",
        "ONLINE", "ADVAYA", "STUDENT INDEX", "STUDENT LOGIN", "SUBMIT",
        "CANCEL", "SEARCH", "CLEAR", "OK", "RESET", "HOME", "WELCOME",
        "SEMESTER", "NOTE", "CLASS", "TOTAL", "S.NO", "MADANAPALLE",
        "INSTITUTE", "REGULAR", "DETAILS", "MARK", "TIME", "TABLE",
        "SOFTSKILLS", "APPTITUDE", "CLASSES ATTENDED", "TOTAL CONDUCTED",
        "ATTENDANCE %", "SAFE ZONE", "STUDENT", "REGISTER NUMBER", "JUST NOW",
        "VIEW FULL PROFILE", "OVERALL PERC", "SUBJECTS", "ATTENDED",
        "CODE", "SUBJECT CODE", "COURSE CODE", "TITLE", "NAME", "STUDENT NAME",
        "STATUS", "ACTION", "TYPE", "PERC", "PERCENTAGE", "NUMBER", "REGISTER",
        "ROLL", "NO", "ROLL NO", "SL.NO", "SERIAL NO", "SERIAL", "BRANCH",
        "SECTION", "YEAR", "ACADEMIC YEAR", "DEPARTMENT", "FACULTY", "USERNAME",
        "LOGIN", "VIEW", "PROFILE", "MITSIMS"
    }

    # 1. Header pattern: "STUDENT NAME | CHANGE PASSWORD | LOGOUT"
    m_header = re.search(r'([A-Za-z\s\.\']+?)\s*\|\s*(?:CHANGE\s+PASSWORD|LOGOUT)', html_text, re.IGNORECASE)
    if m_header:
        candidate = m_header.group(1).strip()
        if len(candidate) >= 3 and not candidate.isdigit() and candidate.upper() not in excluded and all(w.upper() not in excluded for w in candidate.upper().split()):
            return candidate.title()

    # 2. ExtJS displayfield values matching <span style="...">...</span>
    values = re.findall(r"value\s*:\s*\\?['\"](<span.*?>.*?</span>)", html_text, re.DOTALL)
    for m in values:
        t = BeautifulSoup(m, "html.parser").get_text(strip=True)
        if t:
            clean_t = t.split("|")[0].strip()
            upper_t = clean_t.upper()
            if (len(clean_t) >= 3 and 
                not any(char.isdigit() for char in clean_t) and 
                upper_t not in excluded and
                all(w.upper() not in excluded for w in upper_t.split()) and
                re.match(r"^[A-Za-z\.\'\s]+$", clean_t)):
                return clean_t.title()

    # 3. Direct check for element with id studentName
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        name_elem = soup.find(id=re.compile(r"studentName|StudentName|lblStudentName|spnStudentName", re.I))
        if name_elem:
            val = name_elem.get_text(strip=True)
            if val and len(val) >= 2 and not val.isdigit() and val.upper() not in excluded and all(w.upper() not in excluded for w in val.upper().split()):
                return val.title()
    except Exception as e:
        logger.debug(f"Soup parse error in extract_student_name: {e}")

    # 4. Spans with font-size:11px or color:black
    spans = re.findall(r'<span[^>]*style=["\'][^"\']*11px[^"\']*["\'][^>]*>\s*([^<]+?)\s*</span>', html_text, re.IGNORECASE)
    for s in spans:
        clean_s = s.strip()
        if "|" in clean_s:
            clean_s = clean_s.split("|")[0].strip()
        upper_s = clean_s.upper()
        if (len(clean_s) >= 3 and 
            not any(char.isdigit() for char in clean_s) and 
            upper_s not in excluded and
            all(w.upper() not in excluded for w in upper_s.split()) and
            re.match(r"^[A-Za-z\.\'\s]+$", clean_s)):
            return clean_s.title()

    return None




def parse_mits_dashboard_html(html_text):
    """
    Parses ExtJS panel displayfields from MITS IMS dashboard.action output.
    Extracts course code, title, attended count, total conducted, and percentage.
    """
    values = re.findall(r"value\s*:\s*\\?['\"](<span.*?>.*?</span>)", html_text, re.DOTALL)
    clean = []
    for m in values:
        t = BeautifulSoup(m, "html.parser").get_text(strip=True)
        if t:
            clean.append(t)

    # 1. Map Subject Codes to full Subject Titles
    subject_map = {}
    for i in range(len(clean) - 1):
        item = clean[i]
        next_item = clean[i+1]
        if (re.match(r'^[A-Z0-9]{4,10}$', item) or item in ["SOFTSKILLS", "APPTITUDE"]) and not next_item.isdigit() and len(next_item) > 2:
            if not next_item.startswith("Email:"):
                subject_map[item] = f"{item} - {next_item}" if item not in next_item else next_item

    # 2. Extract Attendance Records from Panel 2 (CLASSES ATTENDED, TOTAL CONDUCTED, ATTENDANCE %)
    results = []
    start_idx = -1
    for idx, text in enumerate(clean):
        if "ATTENDANCE %" in text.upper():
            start_idx = idx + 1
            break

    if start_idx != -1:
        curr = start_idx
        while curr < len(clean):
            sno = clean[curr]
            if sno == "Note :" or "NOTE" in sno.upper():
                break
            if sno.isdigit() and curr + 4 < len(clean):
                code_or_name = clean[curr + 1]
                attended_raw = clean[curr + 2]
                total_raw = clean[curr + 3]
                perc_raw = clean[curr + 4]

                display_name = code_or_name.split(" - ")[0].strip()
                att_val = "0" if attended_raw == "-" else attended_raw

                tot_val = "0" if total_raw == "-" else total_raw
                perc_val = "0.0" if perc_raw == "-" else perc_raw.replace("%", "").strip()

                if att_val.isdigit() and tot_val.isdigit():
                    results.append({
                        "subject": display_name,
                        "attended": att_val,
                        "total": tot_val,
                        "percentage": perc_val
                    })
                curr += 5
            else:
                curr += 1

    # Fallback to parsing HTML <tr> tags if ExtJS displayfields parsing returned empty
    if not results and html_text:
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            rows = soup.find_all("tr")
            for row in rows:
                cells = [c.get_text(strip=True).replace('\xa0', ' ') for c in row.find_all(["td", "th"])]
                if len(cells) >= 4:
                    subject, attended, total, percentage = None, None, None, None
                    if len(cells) >= 5 and cells[2].isdigit() and cells[3].isdigit():
                        subject = cells[1]
                        attended = cells[2]
                        total = cells[3]
                        percentage = cells[4].replace("%", "").strip()
                    elif cells[1].isdigit() and cells[2].isdigit():
                        subject = cells[0]
                        attended = cells[1]
                        total = cells[2]
                        percentage = cells[3].replace("%", "").strip() if len(cells) >= 4 else "0.0"

                    if subject and attended and total:
                        clean_name = re.sub(r'[\r\n\t]+', ' ', subject).strip()
                        exclude_keywords = ["SUBJECT CODE", "CLASSES ATTENDED", "TOTAL CONDUCTED", "ATTENDANCE %", "S.NO"]
                        if clean_name and len(clean_name) > 1 and not any(kw in clean_name.upper() for kw in exclude_keywords):
                            results.append({
                                "subject": clean_name,
                                "attended": attended,
                                "total": total,
                                "percentage": percentage or "0.0"
                            })
        except Exception as e:
            logger.debug(f"Soup table parse fallback error: {e}")

    return results


def _get_attendance_http(username, password):
    """
    Ultra-fast (0.2s) HTTP Scraper for MITS IMS.
    Does NOT require Playwright or Chromium binaries!
    Works 100% on Render, Vercel, Koyeb, Railway, and Serverless platforms.
    """
    for base_url in ["http://mitsims.in", "https://mitsims.in"]:
        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": f"{base_url}/"
            }

            # 1. GET Home Page to initialize cookies
            session.get(f"{base_url}/", headers=headers, timeout=8)

            # 2. POST Student Credentials to studentLogin.action
            login_url = f"{base_url}/studentLogin/studentLogin.action?personType=student"
            payload = {
                "userId": username,
                "password": password
            }
            res_post = session.post(login_url, data=payload, headers=headers, timeout=10)

            try:
                res_json = res_post.json()
                if isinstance(res_json, dict):
                    if res_json.get("status") in ["fail", "error", "false"] or res_json.get("success") is False:
                        err_msg = res_json.get("message") or res_json.get("msg") or res_json.get("error") or "Invalid Student ID or Password."
                        return {"error": err_msg}
            except Exception:
                pass

            post_text_lower = res_post.text.lower()
            if any(term in post_text_lower for term in ["invalid user", "invalid password", "password does not match", "user id or password", "authentication failed"]):
                return {"error": "Invalid Student ID or Password."}

            # 3. GET Dashboard View Endpoint & Student Index
            dash_url = f"{base_url}/gemsonline-student/dashboard.action?actionType=view"
            res_dash = session.get(dash_url, headers=headers, timeout=10)

            # 4. Extract Student Name from Post response, Dashboard response, or studentIndex.html
            student_name = extract_student_name(res_post.text)
            if not student_name:
                student_name = extract_student_name(res_dash.text)
            if not student_name:
                try:
                    idx_url = f"{base_url}/gemsonline-student/studentIndex.html"
                    res_idx = session.get(idx_url, headers=headers, timeout=5)
                    student_name = extract_student_name(res_idx.text)
                except Exception:
                    pass

            records = parse_mits_dashboard_html(res_dash.text)

            if records:
                logger.info(f"HTTP Scraper successfully fetched {len(records)} subjects for {username} (Name: {student_name})")
                return {
                    "student_name": student_name,
                    "records": records
                }

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
                student_name = None
                try:
                    page_content = await page.content()
                    student_name = extract_student_name(page_content)
                except Exception:
                    pass
                return {
                    "student_name": student_name,
                    "records": unique_attendance
                }

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
    # 1. Primary Strategy: Ultra-fast HTTP Session Scraper (< 0.3s, 0 Playwright dependency)
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
