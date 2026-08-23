import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_repositories_page_layout(mock_auth, base_url):
    """Verify repositories page header, install banner, and search bar."""
    driver = mock_auth
    driver.get(f"{base_url}/repositories")

    # Verify Page Title
    header = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Connected Repositories')]"))
    )
    assert header.is_displayed()

    # Verify Refresh Button
    refresh_btn = driver.find_element(By.XPATH, "//button[contains(., 'Refresh')]")
    assert refresh_btn.is_displayed()

    # Verify Install Sentinel App banner
    install_banner = driver.find_element(By.XPATH, "//*[contains(text(), 'Connect Your GitHub Repositories')]")
    assert install_banner.is_displayed()

    install_btn = driver.find_element(By.XPATH, "//button[contains(., 'Install Sentinel App')]")
    assert install_btn.is_displayed()

    # Verify Search Input
    search_input = driver.find_element(By.XPATH, "//input[@placeholder='Search connected repositories...']")
    assert search_input.is_displayed()


def test_repositories_search_interaction(mock_auth, base_url):
    """Verify typing into the search filter updates the search state."""
    driver = mock_auth
    driver.get(f"{base_url}/repositories")

    search_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Search connected repositories...']")
        )
    )
    search_input.clear()
    search_input.send_keys("final-year-project")

    assert search_input.get_attribute("value") == "final-year-project"
