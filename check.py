# -*- coding: utf-8 -*-
"""Springer Nature paper status check - designed for GitHub Actions.

Reads credentials from env vars, compares against state/snapshot.txt,
sends an email on change, and rewrites the snapshot so the workflow can
commit it back to the repo (that is how state survives between runs).

Verdicts: FIRST_RUN / NO_CHANGE / CHANGED / ERROR
"""
import os, re, sys, difflib, smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, "state")
os.makedirs(STATE, exist_ok=True)
SNAP = os.path.join(STATE, "snapshot.txt")

SN_EMAIL = os.environ["SN_EMAIL"]
SN_PASSWORD = os.environ["SN_PASSWORD"]
SMTP_AUTH = os.environ["SMTP_AUTH"]
MAIL_TO = os.environ.get("MAIL_TO", "32400920@qq.com")
SMTP_USER = os.environ.get("SMTP_USER", MAIL_TO)

HOME = "https://link.springernature.com/home/"
SUBMISSIONS = "https://link.springernature.com/home/submissions"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def parse_submissions(body_text):
    lines = [l.strip() for l in body_text.splitlines()]
    records, notes, cur = [], {}, []

    def flush(note):
        if len(cur) >= 3:
            rec = f"{' '.join(cur[:-2])} | {cur[-2]} | {cur[-1]}"
            records.append(rec)
            notes[rec] = note
        cur.clear()

    note = ""
    for l in lines:
        if re.match(r"Updated\s+.+$", l):
            note = l
            flush(note)
            continue
        if re.match(r"^\d+ submissions$", l):
            cur.clear()
            continue
        cur.append(l)
    flush(note)
    return records


def send_mail(subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr(("论文状态监控", SMTP_USER))
    msg["To"] = MAIL_TO
    s = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30)
    s.login(SMTP_USER, SMTP_AUTH)
    s.sendmail(SMTP_USER, [MAIL_TO], msg.as_string())
    s.quit()


def login_and_fetch():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=UA, locale="en-US",
                                      viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            page.goto(HOME, wait_until="domcontentloaded", timeout=60000)

            try:
                banner = page.locator("dialog.cc-banner")
                if banner.count() > 0 and banner.first.is_visible():
                    for label in ["Accept all cookies", "Allow all", "Accept"]:
                        btn = page.locator(f'button:has-text("{label}")')
                        if btn.count() > 0:
                            btn.first.click(timeout=5000)
                            break
                    else:
                        page.evaluate(
                            "document.querySelectorAll('dialog.cc-banner').forEach(d => d.remove())")
                    page.wait_for_timeout(500)
            except Exception:
                pass

            box = page.locator('input[name="user_id"]')
            box.wait_for(state="visible", timeout=30000)
            if box.input_value() != SN_EMAIL:
                box.fill(SN_EMAIL)
            page.locator('button:has-text("Continue")').first.click()

            pwd = page.locator('input[name="passwd"]')
            pwd.wait_for(state="visible", timeout=30000)
            pwd.fill(SN_PASSWORD)
            page.locator('button:has-text("Continue")').first.click()

            import time
            t0 = time.time()
            while time.time() - t0 < 90:
                u = page.url
                if "link.springernature.com" in u:
                    break
                if "idp-personal-authenticator" in u and "gateway" in u and "password" not in u:
                    page.wait_for_timeout(3000)
                    break
                page.wait_for_timeout(1000)

            if "link.springernature.com" not in page.url:
                raise RuntimeError("登录失败，被退回登录页。url=" + page.url[:160])

            page.goto(SUBMISSIONS, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            text = re.sub(r"\n{3,}", "\n\n", page.inner_text("body")).strip()
            return parse_submissions(text)
        finally:
            browser.close()


def fmt_diff(detail):
    out = []
    for l in detail.splitlines():
        if l.startswith("+"):
            out.append("【新】" + l[1:].strip())
        elif l.startswith("-"):
            out.append("【旧】" + l[1:].strip())
        elif l.startswith("@@"):
            out.append("—— 变更位置 ——")
    return "\n".join(out)


def main():
    try:
        records = login_and_fetch()
    except Exception as e:
        print("ERROR:", e)
        try:
            send_mail("【论文状态检查失败】",
                      "GitHub Actions 检查失败：\n\n%r\n\n请稍后手动访问 https://link.springernature.com/home/ 确认。" % e)
        except Exception as me:
            print("mail failed:", me)
        sys.exit(1)

    norm = "\n".join(records)
    print("records:", len(records))

    if not os.path.exists(SNAP):
        open(SNAP, "w", encoding="utf-8").write(norm)
        print("FIRST_RUN")
        send_mail("【部署成功】GitHub Actions 论文状态监控已启动",
                  "首次检查完成，已建立基线：共 %d 条投稿记录。\n"
                  "之后每天北京时间 09:00 与 21:00 自动检查，有变化时发邮件通知。\n\n"
                  "查看：https://link.springernature.com/home/" % len(records))
        return

    old = open(SNAP, encoding="utf-8").read()
    if old.strip() == norm.strip():
        print("NO_CHANGE")
        return

    diff = [l for l in difflib.unified_diff(old.splitlines(), norm.splitlines(),
                                           fromfile="previous", tofile="current",
                                           lineterm="", n=1)
            if l.startswith(("+", "-", "@")) and not l.startswith(("+++", "---"))]
    detail = "\n".join(diff[:300])
    open(SNAP, "w", encoding="utf-8").write(norm)
    print("CHANGED")
    print(detail)
    send_mail("【论文状态更新】Springer Nature 投稿状态有变化",
              "检测到投稿状态变化：\n\n%s\n\n查看详情：https://link.springernature.com/home/" % fmt_diff(detail))


if __name__ == "__main__":
    main()
