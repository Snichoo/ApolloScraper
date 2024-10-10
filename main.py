import os
import json
import asyncio
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

app = Flask(__name__)

# Load config data from environment variables
config = {
    'email': os.environ.get('APOLLO_EMAIL'),
    'password': os.environ.get('APOLLO_PASSWORD')
}

# Singleton for Playwright instance
playwright_instance = None
browser = None
context = None
page = None

async def init_browser():
    global playwright_instance, browser, context, page
    if not browser:
        playwright_instance = await async_playwright().start()
        browser = await playwright_instance.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Ensure we are logged in
        await login_to_site(page)

async def login_to_site(page):
    print('Starting login process...')
    await page.goto('https://app.apollo.io/#/login')

    # Wait for the login form to be present
    await page.wait_for_selector("input[name='email']")

    await page.fill("input[name='email']", config['email'])
    await page.fill("input[name='password']", config['password'])
    await page.click("button[type='submit']")

    # Wait for the URL to change indicating successful login
    print("Waiting for login to complete...")
    try:
        await page.wait_for_url('https://app.apollo.io/#/home', timeout=30000)
        print("Login successful.")
    except Exception:
        print("Login failed: timeout waiting for login to complete.")
        await page.screenshot(path='login_timeout.png')
        print("Saved screenshot to 'login_timeout.png'")
        await browser.close()
        exit(1)

async def reveal_and_collect_email(page):
    try:
        # First, try to find the email directly
        print("Attempting to find the email directly...")
        email_element = await page.query_selector("//span[contains(text(), '@')]")
        if email_element:
            email = await email_element.text_content()
            print(f"Collected email directly: {email}")
            return email
    except Exception as e:
        print(f"Error finding email directly: {e}")

    try:
        # If email is not found, look for the 'Access email' button
        access_email_button = await page.query_selector("//button[.//span[text()='Access email']]")
        if access_email_button:
            print("Found 'Access email' button, clicking...")
            await access_email_button.click()
            print("Clicked 'Access email' button.")

            # Wait for the email to be visible after clicking the button
            print("Waiting for email to be visible...")
            await page.wait_for_selector("//span[contains(text(), '@')]", timeout=30000)
            email_element = await page.query_selector("//span[contains(text(), '@')]")
            email = await email_element.text_content()
            print(f"Collected email after clicking button: {email}")
            return email
        else:
            print("Neither email nor 'Access email' button found.")
            await page.screenshot(path='email_not_found.png')
            print("Saved screenshot to 'email_not_found.png'")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        await page.screenshot(path='reveal_and_collect_email_exception.png')
        print("Saved screenshot to 'reveal_and_collect_email_exception.png'")
        return None

@app.route('/get_email', methods=['POST'])
def get_email():
    data = request.json
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    organization_id = data.get('organization_id')

    if not (first_name and last_name and organization_id):
        return jsonify({'error': 'Missing parameters'}), 400

    # Construct the URL
    url = f"https://app.apollo.io/#/people?sortByField=%5Bnone%5D&sortAscending=false&page=1&qPersonName={first_name}%20{last_name}&organizationIds[]={organization_id}"

    async def process_request():
        await init_browser()

        try:
            # Navigate to the URL
            await page.goto(url)
            print("Waiting for page to load...")
            await page.wait_for_selector("body")
            print("Page loaded successfully.")

            # Call the function to reveal and collect the email
            email = await reveal_and_collect_email(page)

            if email:
                return jsonify({'email': email})
            else:
                return jsonify({'error': 'Email not found'}), 404
        except Exception as e:
            print(f"An error occurred: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    return asyncio.run(process_request())

@app.route('/shutdown', methods=['POST'])
def shutdown():
    async def close_resources():
        global browser, playwright_instance
        if browser:
            await browser.close()
            browser = None
        if playwright_instance:
            await playwright_instance.stop()
            playwright_instance = None
    asyncio.run(close_resources())
    return jsonify({'status': 'Browser closed'}), 200

if __name__ == "__main__":
    try:
        port = int(os.environ.get('PORT', 8080))
        print(f"Starting Flask app on port {port}...")
        app.run(host='0.0.0.0', port=port, threaded=True)
    except Exception as e:
        print(f"Failed to start the application: {e}")
        exit(1)