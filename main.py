import os
import json
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Load config data from environment variables
config = {
    'email': os.environ.get('APOLLO_EMAIL'),    # Set 'APOLLO_EMAIL' in environment variables
    'password': os.environ.get('APOLLO_PASSWORD')  # Set 'APOLLO_PASSWORD' in environment variables
}

# Constants
STORAGE_STATE_PATH = 'apollo_login.json'

def init_browser(playwright_instance):
    print("Starting browser...")
    browser = playwright_instance.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
        ]
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/94.0.4606.81 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        accept_downloads=True,
    )
    page = context.new_page()

    # Add script to remove navigator.webdriver property
    page.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    """)

    if os.path.exists(STORAGE_STATE_PATH):
        print("Storage state file found. Loading session.")
        context = browser.new_context(
            storage_state=STORAGE_STATE_PATH,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/94.0.4606.81 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            accept_downloads=True,
        )
        page = context.new_page()

        # Add script to remove navigator.webdriver property
        page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """)

        # Navigate to a page that requires authentication
        page.goto('https://app.apollo.io/#/home')
        page.wait_for_load_state('networkidle')

        # Check if the session is still valid
        if is_logged_in(page):
            print("Session is valid. Proceeding.")
        else:
            print("Session is invalid or expired. Logging in again.")
            os.remove(STORAGE_STATE_PATH)
            context.close()
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/94.0.4606.81 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True,
            )
            page = context.new_page()
            # Add script to remove navigator.webdriver property
            page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """)
            login_to_site(page)
            context.storage_state(path=STORAGE_STATE_PATH)
            print(f"Saved storage state to {STORAGE_STATE_PATH}")
    else:
        print("No storage state file found. Logging in manually.")
        login_to_site(page)
        context.storage_state(path=STORAGE_STATE_PATH)
        print(f"Saved storage state to {STORAGE_STATE_PATH}")

    return browser, context, page

def is_logged_in(page):
    try:
        # Try to find an element that's only present when logged in
        page.wait_for_selector("div[class*='nav-menu']", timeout=10000)
        print("Logged in session detected.")
        return True
    except:
        print("Not logged in.")
        return False

def login_to_site(page):
    print("Starting login process...")
    page.goto('https://app.apollo.io/#/login')

    # Wait for the login form to be present
    print("Waiting for login form to be present...")
    page.wait_for_selector("input[name='email']", timeout=10000)

    print("Filling in email and password...")
    page.fill("input[name='email']", config['email'])
    page.fill("input[name='password']", config['password'])
    print("Submitting login form...")
    page.click("button[type='submit']")

    # Wait for the URL to change from the login URL
    print("Waiting for login to complete...")
    try:
        # Wait until the URL does not contain '#/login'
        page.wait_for_function("!window.location.href.includes('#/login')", timeout=60000)
        page.wait_for_load_state('networkidle')
        print("Login successful.")
    except Exception as e:
        print(f"Login failed: {e}")
        raise Exception("Login failed.")

def reveal_and_collect_email(page):
    # Your existing code for collecting the email
    # ...

    retry_count = 0
    max_retries = 1  # Set the maximum retry count to 1

    while retry_count <= max_retries:
        try:
            # Attempt to find the email directly
            print("Attempting to find the email directly...")
            email_element = page.query_selector("//span[contains(text(), '@')]")
            if email_element:
                email = email_element.text_content()
                print(f"Collected email directly: {email}")
                return email
            else:
                print("Email not found directly.")

            # Look for the 'Access email' button if email is not found
            print("Searching for 'Access email' button...")
            access_email_button = page.query_selector("//button[.//span[text()='Access email']]")
            if access_email_button:
                print("Found 'Access email' button, clicking...")
                page.evaluate("button => button.click()", access_email_button)
                print("Clicked 'Access email' button.")

                # Wait for the email to become visible
                print("Waiting for email to be visible...")
                page.wait_for_selector("//span[contains(text(), '@')]", timeout=30000)
                email_element = page.query_selector("//span[contains(text(), '@')]")
                email = email_element.text_content()
                print(f"Collected email after clicking button: {email}")
                return email
            else:
                print("Neither email nor 'Access email' button found.")

        except Exception as e:
            print(f"An error occurred while revealing email: {e}")

        # Retry after waiting for 1 second if email was not found
        retry_count += 1
        if retry_count <= max_retries:
            print("Retrying after 1 second...")
            page.wait_for_timeout(1000)  # Wait for 1 second before retrying

    print("Email not found after retries.")
    return None

@app.route('/get_email', methods=['POST'])
def get_email():
    data = request.json
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    organization_id = data.get('organization_id')

    if not (first_name and last_name and organization_id):
        print("Missing parameters in request.")
        return jsonify({'error': 'Missing parameters'}), 400

    # Construct the URL
    url = (
        "https://app.apollo.io/#/people?"
        "sortByField=%5Bnone%5D&sortAscending=false&page=1"
        f"&qPersonName={first_name}%20{last_name}&organizationIds[]={organization_id}"
    )
    print(f"Constructed URL: {url}")

    print("Processing request to get email...")

    with sync_playwright() as playwright_instance:
        browser = None
        context = None
        try:
            browser, context, page = init_browser(playwright_instance)

            print(f"Navigating to URL: {url}")
            page.goto(url)
            print("Waiting for page to load...")
            # Wait for a specific element that indicates the page is fully loaded
            page.wait_for_selector("button[datacy='add-contact-account-dropdown']", timeout=30000)
            print("Page loaded successfully.")
            page.wait_for_timeout(1000)  # Wait for 1 second

            # Call the function to reveal and collect the email
            email = reveal_and_collect_email(page)

            if email:
                print(f"Email found: {email}")
                return jsonify({'email': email})
            else:
                print("Email not found.")
                return jsonify({'error': 'Email not found'}), 404
        except Exception as e:
            print(f"An error occurred during email retrieval: {e}")
            return jsonify({'error': 'Internal server error'}), 500
        finally:
            # Close the browser and context after the request
            if context:
                context.close()
            if browser:
                browser.close()

@app.route('/shutdown', methods=['POST'])
def shutdown():
    # No need for shutdown logic since we're not using global instances
    print("Shutdown endpoint called, but no resources to clean up.")
    return jsonify({'status': 'Nothing to shut down'}), 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 7070))
    print(f"Starting Flask app on port {port}...")
    app.run(host='0.0.0.0', port=port, threaded=True)  # Listen on all IPv4 addresses
