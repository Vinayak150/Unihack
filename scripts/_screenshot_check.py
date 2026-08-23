import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://127.0.0.1:8123/")
    page.wait_for_timeout(800)
    page.screenshot(path="/tmp/shot_dashboard.png")

    page.click('button[data-view="enrichment"]')
    page.wait_for_timeout(1200)
    page.screenshot(path="/tmp/shot_enrichment.png")

    page.click('button[data-view="upload"]')
    page.wait_for_timeout(500)
    page.set_input_files("#file-input", "/home/user/Unihack/data/raw/sample_1000_items_input.csv")
    page.wait_for_timeout(1500)
    page.screenshot(path="/tmp/shot_upload.png")
    page.click("text=Run Enrichment Pipeline on Full Batch")
    page.wait_for_timeout(3000)
    page.screenshot(path="/tmp/shot_upload_done.png")

    page.click('button[data-view="dashboard"]')
    page.wait_for_timeout(500)
    page.screenshot(path="/tmp/shot_dashboard2.png")

    page.click('button[data-view="review"]')
    page.wait_for_timeout(1000)
    page.screenshot(path="/tmp/shot_review.png")

    page.click('button[data-view="health"]')
    page.wait_for_timeout(600)
    page.screenshot(path="/tmp/shot_health.png")

    browser.close()
print("done")
