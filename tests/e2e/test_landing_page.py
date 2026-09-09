import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_landing_page_title_and_branding(driver, base_url):
    """Verify landing page loads, title matches Sentinel AI, and header branding renders."""
    driver.get(base_url)

    # Verify Page Title
    WebDriverWait(driver, 10).until(lambda d: "Sentinel" in d.title)
    assert "Sentinel" in driver.title

    # Verify Brand Logo
    brand_logo = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Sentinel')]"))
    )
    assert brand_logo.is_displayed()

    # Verify Version Badge (AI v2.0)
    version_badge = driver.find_element(By.XPATH, "//*[contains(text(), 'AI v2.0')]")
    assert version_badge.is_displayed()


def test_landing_page_hero_section(driver, base_url):
    """Verify Hero headline, subtext, and primary call-to-action buttons."""
    driver.get(base_url)

    # Verify Hero Headline
    headline = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Architectural Code Graph')]"))
    )
    assert headline.is_displayed()

    # Verify Agentic RAG text highlight
    rag_highlight = driver.find_element(By.XPATH, "//span[contains(text(), 'Agentic RAG')]")
    assert rag_highlight.is_displayed()

    # Verify Sign in with GitHub button (when unauthenticated)
    github_cta = driver.find_element(By.XPATH, "//button[contains(., 'Get Started with GitHub')]")
    assert github_cta.is_displayed()

    # Verify Live Demo button
    demo_cta = driver.find_element(By.XPATH, "//a[contains(., 'Try Live Demo Chat')]")
    assert demo_cta.is_displayed()


def test_landing_page_architecture_preview(driver, base_url):
    """Verify the 3-tier architecture visualization card renders."""
    driver.get(base_url)

    # 1. Neo4j AST Graph Card
    neo4j_card = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '1. AST Graph (Neo4j)')]"))
    )
    assert neo4j_card.is_displayed()

    # 2. ChromaDB Vector Card
    chroma_card = driver.find_element(By.XPATH, "//*[contains(text(), '2. Vector KB (ChromaDB)')]")
    assert chroma_card.is_displayed()

    # 3. Dual-LLM ReAct Loop Card
    dual_llm_card = driver.find_element(By.XPATH, "//*[contains(text(), '3. Dual-LLM ReAct Loop')]")
    assert dual_llm_card.is_displayed()


def test_landing_page_feature_grid_and_footer(driver, base_url):
    """Verify feature grid cards and footer details."""
    driver.get(base_url)

    # Verify Feature Grid title
    grid_title = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Complete Microservice Feature Suite')]"))
    )
    assert grid_title.is_displayed()

    # Verify features like Transitive Ripple Blast Radius
    blast_radius_feature = driver.find_element(By.XPATH, "//*[contains(text(), 'Transitive Ripple Blast Radius')]")
    assert blast_radius_feature.is_displayed()

    # Verify FastMCP tool feature
    mcp_feature = driver.find_element(By.XPATH, "//*[contains(text(), 'Model Context Protocol (MCP)')]")
    assert mcp_feature.is_displayed()

    # Verify Footer
    footer = driver.find_element(By.TAG_NAME, "footer")
    assert "Sentinel AI Platform" in footer.text
    assert "Tree-sitter" in footer.text
