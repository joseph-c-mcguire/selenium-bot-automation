from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def execute_recorded_actions(wait_time=1):
    # Setup the driver with options
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")  # Suppress specific browser errors
    driver = webdriver.Chrome(options=options)
    actions = ActionChains(driver)
    wait = WebDriverWait(driver, 10)  # Wait up to 10 seconds for elements to be present

    try:
        # Load the recorded actions
        with open("actions.json", "r") as f:
            recorded_actions = json.load(f)

        # Execute each action
        for action in recorded_actions:
            try:
                # Handle different types of quotes and escape characters
                action = action.replace('\\"', '"').replace("\\'", "'")

                # If the action is a driver.get() command
                if action.startswith("driver.get("):
                    url = action[action.find('"') + 1 : action.rfind('"')]
                    logging.info(f"Navigating to URL: {url}")
                    driver.get(url)
                    time.sleep(wait_time)  # Wait for page load

                # If the action is a click command
                elif "find_element" in action:
                    # Extract the XPath from the action string
                    xpath_start = action.find("By.XPATH,") + len("By.XPATH,")
                    xpath_end = action.rfind('").click()')
                    xpath = action[xpath_start:xpath_end].strip().strip('"').strip("'")

                    # Wait for the element to be visible and enabled before clicking
                    logging.info(f"Waiting for element with XPath: {xpath}")
                    element = wait.until(
                        EC.visibility_of_element_located((By.XPATH, xpath))
                    )
                    wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))

                    is_displayed = element.is_displayed()
                    logging.info(f"Element displayed status: {is_displayed}")
                    bounding_rect = driver.execute_script(
                        "return arguments[0].getBoundingClientRect();", element
                    )
                    logging.info(f"Element bounding rectangle: {bounding_rect}")

                    driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(0.5)  # Allow the scroll to finish
                    logging.info(f"Clicking element with XPath: {xpath}")
                    element.click()
                    time.sleep(wait_time)  # Wait for element interaction

                logging.info(f"Executed action: {action}")

            except Exception as e:
                logging.error(f"Error executing action '{action}': {e}")
                driver.save_screenshot(f"error_screenshot_{int(time.time())}.png")
                continue

    except Exception as e:
        logging.error(f"Error reading or processing actions: {e}")

    finally:
        # Clean up
        driver.quit()
        logging.info("Driver quit successfully")


if __name__ == "__main__":
    import sys

    # Allow wait time to be passed as a command-line argument
    wait_time = float(sys.argv[1]) if len(sys.argv) > 1 else 1
    execute_recorded_actions(wait_time)
