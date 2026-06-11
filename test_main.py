import pytest
from unittest.mock import AsyncMock
from main import verify_job_posting, check_blacklist_and_qa, is_strictly_israel
import re

# ==========================================
# Test Suite for Job Verification Engine
# ==========================================

@pytest.mark.asyncio
async def test_verify_job_posting_detects_ghost_job():
    """Test that the scraper correctly rejects 'closed' or 'filled' jobs."""
    mock_page = AsyncMock()
    mock_page.goto.return_value = None
    mock_page.title.return_value = "Job Posting"
    mock_page.content.return_value = "<html><body>This position is no longer accepting applications.</body></html>"
    
    title, company, tech, content = await verify_job_posting(mock_page, "http://dummy-url.com/closed-job")
    
    assert content is None, "Failed: Scraper did not discard a closed job posting."

@pytest.mark.asyncio
async def test_verify_job_posting_detects_apply_button():
    """Test that the scraper correctly identifies a valid job page with an Apply button."""
    mock_page = AsyncMock()
    mock_content = "<html><body>We are looking for a backend developer. <button>Apply Now</button></body></html>"
    mock_page.content.return_value = mock_content
    mock_page.title.return_value = "Backend Dev - Example"
    mock_page.url = "https://jobs.example.com/backend"
    
    from unittest.mock import MagicMock
    mock_locator = AsyncMock()
    mock_locator.count.return_value = 1
    mock_locator.all_inner_texts.return_value = ["Backend Dev"]
    mock_page.locator = MagicMock(return_value=mock_locator)
    
    title, company, tech, content = await verify_job_posting(mock_page, "http://dummy-url.com/valid-job")
    
    assert content == mock_content, "Failed: Scraper did not accept a valid job posting with an Apply button."

def test_location_filter():
    """Test that jobs outside Israel are rejected, and jobs in Israel are accepted."""
    valid_job_desc = "We are hiring in Tel Aviv, Israel."
    invalid_job_desc = "We are hiring in New York, USA. Remote only in EST."
    
    # Test valid location
    is_valid_location = is_strictly_israel(valid_job_desc)
    assert is_valid_location is True, "Failed: Scraper rejected an Israeli location."
    
    # Test invalid location
    is_invalid_location = is_strictly_israel(invalid_job_desc)
    assert is_invalid_location is False, "Failed: Scraper accepted a non-Israeli location."

def test_whitelist_blacklist_logic():
    """Test that QA is blocked, Senior is blocked, but Junior Backend passes."""
    
    job_1 = "Looking for a Junior Backend Developer." # Should PASS
    job_2 = "Looking for an experienced QA Automation Engineer." # Should PASS (QA with Automation)
    job_3 = "Looking for a manual QA tester." # Should FAIL (Pure QA)
    job_4 = "Senior Cloud Architect needed. 5+ years experience." # Should FAIL (Blacklist: Senior/Architect)
    
    assert check_blacklist_and_qa(job_1) is True, "Failed: Scraper rejected a valid Junior Backend role."
    assert check_blacklist_and_qa(job_2) is True, "Failed: QA Automation should be allowed."
    assert check_blacklist_and_qa(job_3) is False, "Failed: Manual QA should be rejected."
    assert check_blacklist_and_qa(job_4) is False, "Failed: Scraper accepted a Senior role (Blacklist failure)."
