import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_ingest_page_form_and_controls(mock_auth, base_url):
    """Verify ingestion form inputs, pipeline stage cards, and submit button."""
    driver = mock_auth
    driver.get(f"{base_url}/ingest")

    # Verify Page Title
    header = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Ingest Codebase into Neo4j & ChromaDB')]"))
    )
    assert header.is_displayed()

    # Verify repo_id input
    repo_id_input = driver.find_element(By.XPATH, "//input[@placeholder='e.g. final-year-project']")
    assert repo_id_input.is_displayed()
    assert repo_id_input.get_attribute("value") != ""

    # Verify repo_dir input
    repo_dir_input = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'Users')]")
    assert repo_dir_input.is_displayed()

    # Verify branch input
    branch_input = driver.find_element(By.XPATH, "//input[@placeholder='main']")
    assert branch_input.is_displayed()

    # Verify Submit Button
    submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
    assert submit_btn.is_displayed()
    assert "Start Knowledge Base Ingestion" in submit_btn.text

    # Verify Pipeline Stages info box
    pipeline_box = driver.find_element(By.XPATH, "//*[contains(text(), 'Ingestion Pipeline Stages')]")
    assert pipeline_box.is_displayed()


def test_ingest_page_input_modification(mock_auth, base_url):
    """Verify editing repo_id and branch inputs."""
    driver = mock_auth
    driver.get(f"{base_url}/ingest")

    repo_id_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='e.g. final-year-project']")
        )
    )
    repo_id_input.clear()
    repo_id_input.send_keys("custom-demo-repo")
    assert repo_id_input.get_attribute("value") == "custom-demo-repo"

    branch_input = driver.find_element(By.XPATH, "//input[@placeholder='main']")
    branch_input.clear()
    branch_input.send_keys("feature/agent-v2")
    assert branch_input.get_attribute("value") == "feature/agent-v2"
