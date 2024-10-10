import os
import json
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Load config data from environment variables
config = {
    'email': os.environ.get('APOLLO_EMAIL'),
    'password': os.environ.get('APOLLO_PASSWORD')
}

# Validate environment variables
if not config['email'] or not config['password']:
    print("APOLLO_EMAIL and APOLLO_PASSWORD environment variables must be set.")
    exit(1)

# Constants
STORAGE_STATE_PATH = '/tmp/apollo_login.json'

def init_browser(playwright_instance):
    print("Starting browser...")
    if os.path.exists(STORAGE_STATE_PATH):
        print("Storage state file found. Using saved session.")
        browser = playwright_instance.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = context.new_page()
    else:
        print("No storage state file found. Logging in manually.")
        browser = playwright_instance.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()
        login_to_site(page)
        # Save the authenticated state
        context.storage_state(path=STORAGE_STATE_PATH)
        print(f"Saved storage state to {STORAGE_STATE_PATH}")
    return browser, context, page

def login_to_site(page):
    print("Starting login process...")
    page.goto('https://app.apollo.io/#/login')

    # Wait for the login form to be present
    print("Waiting for login form to be present...")
    page.wait_for_selector("input[name='email']")

    print("Filling in email and password...")
    page.fill("input[name='email']", config['email'])
    page.fill("input[name='password']", config['password'])
    print("Submitting login form...")
    page.click("button[type='submit']")

    # Wait for the URL to change indicating successful login
    print("Waiting for login to complete...")
    try:
        page.wait_for_url('https://app.apollo.io/#/home', timeout=30000)
        print("Login successful.")
    except Exception as e:
        print(f"Login failed: {e}")
        screenshot_path = '/tmp/login_failed.png'
        page.screenshot(path=screenshot_path)
        print(f"Saved screenshot to '{screenshot_path}'")
        raise Exception("Login failed.")

def reveal_and_collect_email(page):
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
                access_email_button.click()
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
                page.screenshot(path='/tmp/email_not_found.png')
                print("Saved screenshot to '/tmp/email_not_found.png'")

        except Exception as e:
            print(f"An error occurred while revealing email: {e}")
            page.screenshot(path='/tmp/reveal_and_collect_email_exception.png')
            print("Saved screenshot to '/tmp/reveal_and_collect_email_exception.png'")

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
            page.wait_for_selector("body")
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
    try:
        port = int(os.environ.get('PORT', 8080))
        print(f"Starting Flask app on port {port}...")
        app.run(host='0.0.0.0', port=port, threaded=True)
    except Exception as e:
        print(f"Failed to start the application: {e}")
        exit(1)
