"""
One-time setup: open a real browser, log into Google, save the session.
After running this, the SERP scraper will use your Google account cookies
and avoid CAPTCHAs.

Run once:
    python tools/setup_serp_session.py

Then run the engine normally — SERP will work without CAPTCHAs.
"""
import os
import json

SESSION_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "google_session.json")


def main():
    from playwright.sync_api import sync_playwright
    try:
        from playwright_stealth import stealth_sync
        has_stealth = True
    except ImportError:
        has_stealth = False

    print("Opening browser — please log into your Google account.")
    print("After logging in, press ENTER here to save the session.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="he-IL",
        )
        page = ctx.new_page()

        if has_stealth:
            stealth_sync(page)

        page.goto("https://accounts.google.com/", wait_until="domcontentloaded")

        input("  >> Log into Google in the browser, then press ENTER here to save session: ")

        # Save session state (cookies + localStorage)
        state = ctx.storage_state()
        os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
        with open(SESSION_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)

        print(f"\n  Session saved to: {SESSION_PATH}")
        print("  The SERP scraper will now use this session automatically.")

        browser.close()


if __name__ == "__main__":
    main()
