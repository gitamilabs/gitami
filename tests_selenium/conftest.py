import os
import time
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

BASE_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="function")
def driver():
    """Initializes a headless Chrome or Edge WebDriver instance."""
    driver_instance = None

    # Try Google Chrome first
    try:
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # Explicit binary location if found
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for cp in chrome_paths:
            if os.path.exists(cp):
                chrome_options.binary_location = cp
                break

        driver_instance = webdriver.Chrome(options=chrome_options)
    except Exception as chrome_err:
        print(f"Chrome initialization failed ({chrome_err}), falling back to Edge...")
        try:
            edge_options = EdgeOptions()
            edge_options.add_argument("--headless=new")
            edge_options.add_argument("--disable-gpu")
            edge_options.add_argument("--no-sandbox")
            edge_options.add_argument("--window-size=1920,1080")
            driver_instance = webdriver.Edge(options=edge_options)
        except Exception as edge_err:
            raise RuntimeError(f"Could not initialize Chrome or Edge WebDriver: {edge_err}")

    driver_instance.implicitly_wait(4)
    yield driver_instance
    driver_instance.quit()


@pytest.fixture(scope="function")
def mock_auth(driver, base_url):
    """Navigates to the app and injects a mock session token into localStorage."""
    driver.get(base_url)
    driver.execute_script("""
        localStorage.setItem('sentinel_token', 'mock_jwt_session_token_xyz987');
    """)
    driver.refresh()
    time.sleep(0.5)
    return driver
