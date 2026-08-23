import time
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


def test_chat_page_layout_and_elements(driver, base_url):
    """Verify chat window renders with target repo selector, branch input, and textarea."""
    driver.get(f"{base_url}/chat")

    # Verify Sidebar link
    sidebar = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Agentic RAG Chat')]"))
    )
    assert sidebar.is_displayed()

    # Verify Target Repo Selector Dropdown
    repo_select = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//select"))
    )
    assert repo_select.is_displayed()

    # Verify default selected repo or options
    select_obj = Select(repo_select)
    option_texts = [opt.text for opt in select_obj.options]
    assert len(option_texts) > 0
    assert any("final-year-project" in opt for opt in option_texts)

    # Verify Branch input
    branch_input = driver.find_element(By.XPATH, "//input[@placeholder='main']")
    assert branch_input.is_displayed()

    # Verify Message Textarea
    textarea = driver.find_element(By.XPATH, "//textarea")
    assert textarea.is_displayed()

    # Verify Initial Ask button is disabled when empty
    ask_button = driver.find_element(By.XPATH, "//button[contains(., 'Ask Agent')]")
    assert not ask_button.is_enabled()


def test_chat_starter_prompts_click(driver, base_url):
    """Verify clicking a suggested prompt populates the message textarea and enables submit."""
    driver.get(f"{base_url}/chat")

    # Locate a suggested query button
    prompt_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//button[contains(text(), 'What is the ripple blast radius')]")
        )
    )
    assert prompt_button.is_displayed()
    prompt_text = prompt_button.text

    # Click suggested prompt
    prompt_button.click()
    time.sleep(0.3)

    # Verify textarea value is populated
    textarea = driver.find_element(By.XPATH, "//textarea")
    assert textarea.get_attribute("value") == prompt_text

    # Verify Ask Agent button is now enabled
    ask_button = driver.find_element(By.XPATH, "//button[contains(., 'Ask Agent')]")
    assert ask_button.is_enabled()


def test_chat_textarea_input_and_clear_history(driver, base_url):
    """Verify manual typing into textarea and clear history button action."""
    driver.get(f"{base_url}/chat")

    textarea = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//textarea"))
    )

    # Type custom question
    test_query = "Find all callers of handleCallback across the repository"
    textarea.clear()
    textarea.send_keys(test_query)

    assert textarea.get_attribute("value") == test_query

    ask_button = driver.find_element(By.XPATH, "//button[contains(., 'Ask Agent')]")
    assert ask_button.is_enabled()

    # Verify Clear History button
    clear_button = driver.find_element(By.XPATH, "//button[contains(., 'Clear History')]")
    assert clear_button.is_displayed()
    clear_button.click()
    time.sleep(0.2)


def test_chat_url_parameters(driver, base_url):
    """Verify navigating with ?repo=demo-mern&branch=develop updates the selectors."""
    driver.get(f"{base_url}/chat?repo=demo-mern&branch=develop")

    # Verify branch input took value from URL
    branch_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//input[@value='develop']"))
    )
    assert branch_input.is_displayed()
