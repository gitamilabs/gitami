import time
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_graph_page_layout_and_inspector(mock_auth, base_url):
    """Verify code graph explorer layout, node list, and initial inspector details."""
    driver = mock_auth
    driver.get(f"{base_url}/graph")

    # Verify Page Title
    header = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Knowledge Base Code Graph & AST')]"))
    )
    assert header.is_displayed()

    # Verify Node Kinds Filter Buttons
    all_pill = driver.find_element(By.XPATH, "//button[contains(text(), 'All')]")
    assert all_pill.is_displayed()

    func_pill = driver.find_element(By.XPATH, "//button[contains(text(), 'Function')]")
    assert func_pill.is_displayed()

    class_pill = driver.find_element(By.XPATH, "//button[contains(text(), 'Class')]")
    assert class_pill.is_displayed()

    comp_pill = driver.find_element(By.XPATH, "//button[contains(text(), 'React Component')]")
    assert comp_pill.is_displayed()

    # Verify Right Inspector Panel Details
    inspector_docstring = driver.find_element(By.XPATH, "//*[contains(text(), 'Docstring / Description')]")
    assert inspector_docstring.is_displayed()

    incoming_callers = driver.find_element(By.XPATH, "//*[contains(text(), 'Incoming Callers')]")
    assert incoming_callers.is_displayed()

    outgoing_callees = driver.find_element(By.XPATH, "//*[contains(text(), 'Outgoing Callees')]")
    assert outgoing_callees.is_displayed()


def test_graph_node_selection_and_switch(mock_auth, base_url):
    """Verify clicking a different node updates the inspector panel."""
    driver = mock_auth
    driver.get(f"{base_url}/graph")

    # Locate and click AutonomousAgentLoop class node
    loop_node = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'AutonomousAgentLoop')]"))
    )
    assert loop_node.is_displayed()
    loop_node.click()
    time.sleep(0.3)

    # Verify Inspector title updated
    inspector_heading = driver.find_element(By.XPATH, "//h2[contains(text(), 'AutonomousAgentLoop')]")
    assert inspector_heading.is_displayed()

    # Verify Blast Risk score is shown
    risk_label = driver.find_element(By.XPATH, "//*[contains(text(), 'Blast Risk')]")
    assert risk_label.is_displayed()


def test_graph_search_filter(mock_auth, base_url):
    """Verify searching in graph explorer filters the list of nodes."""
    driver = mock_auth
    driver.get(f"{base_url}/graph")

    search_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search symbol or file path...']"))
    )
    search_input.clear()
    search_input.send_keys("DualLLMClient")
    time.sleep(0.3)

    # Verify DualLLMClient is in the filtered list
    match_node = driver.find_element(By.XPATH, "//*[contains(text(), 'DualLLMClient')]")
    assert match_node.is_displayed()
