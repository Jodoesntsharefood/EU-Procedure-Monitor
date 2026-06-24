import os
import json
import requests

from playwright.sync_api import sync_playwright

URL = "https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025%2F0359%28COD%29"

STATUS_FILE = "last_status.json"


def get_current_events():
    """
    抓取 Key events 表格
    """

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=120000
        )

        page.wait_for_timeout(5000)

        # 找到 Key events 标题
        key_events_heading = page.locator(
            "text=Key events"
        ).first

        key_events_heading.wait_for(timeout=30000)

        # 找最近的 table
        table = key_events_heading.locator(
            "xpath=following::table[1]"
        )

        rows = table.locator("tbody tr")

        count = rows.count()

        print(f"Found {count} key event rows")

        events = []

        for i in range(count):

            row = rows.nth(i)

            cols = row.locator("td")

            col_count = cols.count()

            values = []

            for j in range(col_count):

                text = cols.nth(j).inner_text().strip()

                values.append(text)

            if values:
                events.append(values)

        browser.close()

        return events


def load_old_events():

    if not os.path.exists(STATUS_FILE):
        return []

    with open(
        STATUS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_events(events):

    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            events,
            f,
            indent=2,
            ensure_ascii=False
        )


def compare_events(old_events, new_events):

    old_set = {
        json.dumps(row, ensure_ascii=False)
        for row in old_events
    }

    new_set = {
        json.dumps(row, ensure_ascii=False)
        for row in new_events
    }

    added = new_set - old_set
    removed = old_set - new_set

    return added, removed


def send_email(added, removed):

    resend_api_key = os.environ["RESEND_API_KEY"]

    to_emails = os.environ["TO_EMAILS"].split(",")

    html = """
    <h2>EU Parliament Procedure Monitor</h2>
    """

    if added:

        html += "<h3>New Events</h3>"

        for item in added:

            row = json.loads(item)

            html += "<p>" + " | ".join(row) + "</p>"

    if removed:

        html += "<h3>Removed Events</h3>"

        for item in removed:

            row = json.loads(item)

            html += "<p>" + " | ".join(row) + "</p>"

    html += f"""
    <br>
    <a href="{URL}">
    Open Procedure File
    </a>
    """

    payload = {
        "from": "EU Procedure Monitor <onboarding@resend.dev>",
        "to": to_emails,
        "subject": "[EU Alert] Key Events Changed",
        "html": html
    }

    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://api.resend.com/emails",
        headers=headers,
        json=payload
    )

    print(response.status_code)
    print(response.text)


def main():

    current_events = get_current_events()

    print(
        json.dumps(
            current_events,
            indent=2,
            ensure_ascii=False
        )
    )

    old_events = load_old_events()

    added, removed = compare_events(
        old_events,
        current_events
    )

    if not old_events:

        print("First run")

        save_events(current_events)

        return

    if added or removed:

        print("Changes detected")

        send_email(
            added,
            removed
        )

        save_events(current_events)

    else:

        print("No changes")


if __name__ == "__main__":
    main()
