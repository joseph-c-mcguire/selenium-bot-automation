from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import json
import time


def execute_recorded_actions():
    # Setup the driver
    driver = webdriver.Chrome()
    actions = ActionChains(driver)

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
                    driver.get(url)
                    time.sleep(1)  # Wait for page load

                # If the action is a click command
                elif "find_element" in action:
                    # Extract the XPath from the action string
                    xpath_start = action.find("By.XPATH,") + len("By.XPATH,")
                    xpath_end = action.rfind('").click()')
                    xpath = action[xpath_start:xpath_end].strip().strip('"').strip("'")

                    # Execute the click
                    driver.find_element(By.XPATH, xpath).click()
                    time.sleep(0.5)  # Wait for element interaction

                print(f"Executed action: {action}")

            except Exception as e:
                print(f"Error executing action '{action}': {e}")
                continue

    except Exception as e:
        print(f"Error reading or processing actions: {e}")

    finally:
        # Clean up
        driver.quit()


if __name__ == "__main__":
    execute_recorded_actions()
