import time
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_unauthenticated_protected_route_guard(driver, base_url):
    """Verify that unauthenticated access to /dashboard displays the auth guard barrier."""
    # Clear localStorage
    driver.get(base_url)
    driver.execute_script("localStorage.clear();")

    # Navigate to /dashboard
    driver.get(f"{base_url}/dashboard")

    # Verify Authentication Required card
    auth_req_card = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Authentication Required')]"))
    )
    assert auth_req_card.is_displayed()

    # Verify Sign in with GitHub button in guard
    signin_button = driver.find_element(By.XPATH, "//button[contains(., 'Sign in with GitHub')]")
    assert signin_button.is_displayed()


def test_authenticated_dashboard_view(mock_auth, base_url):
    """Verify that having a session token reveals the authenticated dashboard layout and stats."""
    driver = mock_auth
    driver.get(f"{base_url}/dashboard")

    # Verify Welcome header
    welcome_header = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Welcome back')]"))
    )
    assert welcome_header.is_displayed()

    # Verify Metric Cards
    connected_repos_card = driver.find_element(By.XPATH, "//*[contains(text(), 'Connected Repos')]")
    assert connected_repos_card.is_displayed()

    vector_passages_card = driver.find_element(By.XPATH, "//*[contains(text(), 'Vector KB Passages')]")
    assert vector_passages_card.is_displayed()

    graph_repos_card = driver.find_element(By.XPATH, "//*[contains(text(), 'Graph Repositories')]")
    assert graph_repos_card.is_displayed()

    dual_llm_card = driver.find_element(By.XPATH, "//*[contains(text(), 'Dual-LLM Engine')]")
    assert dual_llm_card.is_displayed()


def test_auth_callback_error_handling(driver, base_url):
    """Verify that /auth/callback?error=access_denied gracefully shows the error screen."""
    driver.get(f"{base_url}/auth/callback?error=access_denied&error_description=User+cancelled+authorization")

    error_heading = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Authentication Failed')]"))
    )
    assert error_heading.is_displayed()

    error_msg = driver.find_element(By.XPATH, "//*[contains(text(), 'User cancelled authorization')]")
    assert error_msg.is_displayed()

    return_btn = driver.find_element(By.XPATH, "//button[contains(., 'Return to Home')]")
    assert return_btn.is_displayed()
