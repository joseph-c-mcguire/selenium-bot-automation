import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import json
import sys
import time
import requests
import os
from flask_cors import CORS
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class ActionRecorder:
    def __init__(self):
        self.actions = []

    def record_action(self, action):
        self.actions.append(action)

    def save_actions(self, filename):
        with open(filename, "w") as f:
            json.dump(self.actions, f)

    def load_actions(self, filename):
        with open(filename, "r") as f:
            self.actions = json.load(f)

    def generate_script(self, filename):
        with open(filename, "w") as f:
            f.write("from selenium import webdriver\n")
            f.write("from selenium.webdriver.common.by import By\n")
            f.write(
                "from selenium.webdriver.common.action_chains import ActionChains\n\n"
            )
            f.write("driver = webdriver.Chrome()\n")
            f.write("actions = ActionChains(driver)\n\n")
            for action in self.actions:
                # Clean up any potential quote issues in the action string
                if "By.XPATH" in action:
                    # Ensure XPath is properly quoted
                    parts = action.split("By.XPATH,")
                    xpath = parts[1].strip().replace('"', "'")
                    action = f"{parts[0]}By.XPATH, {xpath}"
                f.write(f"{action}\n")
            f.write("driver.quit()\n")
        # Print the generated script and then exit
        with open(filename, "r") as f:
            print(f.read())
        sys.exit(0)

    def inject_tracking_script(self, driver):
        # First, inject the XPath helper function
        xpath_helper = """
        if (!window.getXPathForElement) {
            window.getXPathForElement = function(element) {
                if (element.id !== '')
                    return 'id("' + element.id + '")';
                if (element === document.body)
                    return element.tagName;

                var ix = 0;
                var siblings = element.parentNode.childNodes;

                for (var i = 0; i < siblings.length; i++) {
                    var sibling = siblings[i];
                    if (sibling === element)
                        return window.getXPathForElement(element.parentNode) + '/' + element.tagName + '[' + (ix + 1) + ']';
                    if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                        ix++;
                }
            };
        }
        """
        driver.execute_script(xpath_helper)

        # Then inject the tracking script
        script = """
        if (!window.actionTrackerInitialized) {
            window.actionTrackerInitialized = true;
            let pendingActions = [];
            
            function submitAction(action) {
                return fetch('http://localhost:5000/track', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify(action)
                })
                .then(response => response.json())
                .catch(error => {
                    console.error('Error submitting action:', error);
                    pendingActions.push(action);
                });
            }

            document.addEventListener('click', async function(event) {
                let element = event.target;
                let xpath = window.getXPathForElement(element);
                console.log('XPath generated:', xpath);
                
                let action = {
                    type: 'click',
                    tag: element.tagName,
                    id: element.id,
                    classes: element.className,
                    xpath: xpath,
                    timestamp: Date.now(),
                    href: element.href || ''
                };
                
                console.log('Action detected:', action);
                await submitAction(action);
            }, true);

            window.getTrackedActions = function() {
                return pendingActions;
            };
        }
        """
        driver.execute_script(script)

    def track_actions(self, driver):
        from flask import Flask, request, jsonify
        import threading

        app = Flask(__name__)
        CORS(app)

        # Add shutdown flag
        self.server_running = True

        @app.route("/track", methods=["POST", "OPTIONS"])
        def track():
            if request.method == "OPTIONS":
                return app.make_default_options_response()

            try:
                action = request.json
                print(f"Received action: {action}")

                if action.get("type") == "click":
                    xpath = action.get("xpath")
                    if xpath:
                        xpath = xpath.replace('"', "'")
                        action_str = f'driver.find_element(By.XPATH, "{xpath}").click()'
                        self.record_action(action_str)
                        self.save_actions("actions.json")
                        print(
                            f"Action recorded and saved. Total actions: {len(self.actions)}"
                        )

                return jsonify({"status": "success", "count": len(self.actions)})
            except Exception as e:
                print(f"Error processing action: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route("/shutdown", methods=["POST"])
        def shutdown():
            self.server_running = False
            # Use os._exit instead of werkzeug shutdown
            os._exit(0)
            return "Server shutting down..."

        def run_server():
            app.run(port=5000, threaded=True)

        # Start server
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(1)  # Give server time to start

        self.inject_tracking_script(driver)
        print("Tracking started. Perform actions in the browser.")

        try:
            while self.server_running:
                time.sleep(0.5)
                try:
                    # Store current URL to detect navigation
                    current_url = driver.current_url

                    # Check browser status
                    current_handles = driver.window_handles
                    if not current_handles:
                        print("Browser window closed")
                        break

                    # Re-inject tracking script after navigation
                    try:
                        self.inject_tracking_script(driver)
                    except Exception as e:
                        print(f"Script injection error: {e}")

                    # Process any pending actions
                    try:
                        pending_actions = driver.execute_script(
                            "return window.getTrackedActions ? window.getTrackedActions() : [];"
                        )
                        if pending_actions:
                            print(f"Processing {len(pending_actions)} pending actions")
                            for action in pending_actions:
                                if action.get("xpath"):
                                    xpath = action["xpath"].replace('"', "'")
                                    self.record_action(
                                        f'driver.find_element(By.XPATH, "{xpath}").click()'
                                    )
                                    # Add wait after navigation if href was present
                                    if action.get("href"):
                                        time.sleep(1)  # Wait for navigation
                                        self.inject_tracking_script(driver)

                    except Exception as e:
                        print(f"Error processing actions: {e}")

                except Exception as e:
                    if "no such window" in str(e) or "invalid session" in str(e):
                        print("Browser session ended")
                        break
                    else:
                        print(f"Error during tracking: {e}")
                        time.sleep(1)  # Wait before retrying

        except KeyboardInterrupt:
            print("\nTracking stopped by user")
        finally:
            print("Cleaning up...")
            self.save_actions("actions.json")
            self.server_running = False
            try:
                requests.post("http://localhost:5000/shutdown", timeout=1)
            except:
                # Force exit if shutdown request fails
                os._exit(0)
            print(f"Final recorded actions: {self.actions}")
            server_thread.join(timeout=1)


def get_driver(browser_type):
    try:
        if browser_type == "chrome":
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            ChromeDriverManager().install()
            return webdriver.Chrome(options=options)
        elif browser_type == "firefox":
            GeckoDriverManager().install()
            return webdriver.Firefox()
        elif browser_type == "edge":
            EdgeChromiumDriverManager().install()
            return webdriver.Edge()
        else:
            raise ValueError(f"Unsupported browser type: {browser_type}")
    except PermissionError as e:
        print(f"Permission error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


def main(browser_type="chrome"):
    driver = get_driver(browser_type)
    recorder = ActionRecorder()

    driver.get("https://joseph-c-mcguire.github.io/")
    recorder.record_action('driver.get("https://joseph-c-mcguire.github.io/")')

    recorder.track_actions(driver)
    driver.quit()


if __name__ == "__main__":
    import sys

    browser_type = sys.argv[1] if len(sys.argv) > 1 else "edge"
    main(browser_type)
