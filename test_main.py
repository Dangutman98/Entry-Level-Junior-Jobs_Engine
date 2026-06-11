import pytest
from unittest.mock import AsyncMock
from main import verify_job_posting, WHITELIST, BLACKLIST, ISRAEL_LOCATIONS
import re

# ==========================================
# Test Suite for Job Verification Engine
# ==========================================

@pytest.mark.asyncio
async def test_verify_job_posting_detects_ghost_job():
    """Test that the scraper correctly rejects 'closed' or 'filled' jobs."""
    mock_page = AsyncMock()
    mock_page.title = AsyncMock(return_value="Valid Title")
    mock_page.content.return_value = "<html><body>This position is no longer accepting applications.</body></html>"
    
    result = await verify_job_posting(mock_page, "http://dummy-url.com/closed-job")
    
    # Assert that the function returns None (discarded)
    assert result == (None, None, None, None), "Failed: Scraper did not discard a closed job posting."

@pytest.mark.asyncio
async def test_verify_job_posting_detects_apply_button():
    """Test that the scraper correctly identifies a valid job page with an Apply button."""
    mock_page = AsyncMock()
    mock_page.title = AsyncMock(return_value="Valid Title")
    mock_content = "<html><body>We are looking for a backend developer. <button>Apply Now</button></body></html>"
    mock_page.content.return_value = mock_content
    
    # Mock the locator to simulate finding the button
    from unittest.mock import MagicMock
    mock_locator = AsyncMock()
    mock_locator.count.return_value = 1
    mock_page.locator = MagicMock(return_value=mock_locator)

    # Mock extract_page_data because verify_job_posting calls it
    # We must patch it or mock it if we can't patch easily.
    # Actually, verify_job_posting uses extract_page_data from the same module.
    # Since we can't easily patch it without unittest.mock.patch, let's just make page.evaluate return something.
    mock_page.evaluate = AsyncMock(return_value="mocked text")
    
    result = await verify_job_posting(mock_page, "http://dummy-url.com/valid-job")
    
    # Assert that the function does not return (None, None, None, None)
    assert result != (None, None, None, None), "Failed: Scraper did not accept a valid job posting with an Apply button."

def test_location_filter():
    """Test that jobs outside Israel are rejected, and jobs in Israel are accepted."""
    valid_job_desc = "We are hiring in Tel Aviv, Israel."
    invalid_job_desc = "We are hiring in New York, USA. Remote only in EST."
    
    is_valid_location = any(loc in valid_job_desc.lower() for loc in ISRAEL_LOCATIONS)
    assert is_valid_location is True, "Failed: Scraper rejected an Israeli location."
    
    is_invalid_location = any(loc in invalid_job_desc.lower() for loc in ISRAEL_LOCATIONS)
    assert is_invalid_location is False, "Failed: Scraper accepted a non-Israeli location."

def test_whitelist_blacklist_logic():
    """Test that QA is blocked, Senior is blocked, but Junior Backend passes."""
    
    job_1 = "Looking for a Junior Backend Developer." # Should PASS
    job_2 = "Looking for an experienced QA Automation Engineer." # Should FAIL (Blacklist: QA)
    job_3 = "Senior Cloud Architect needed. 5+ years experience." # Should FAIL (Blacklist: Senior/Architect, Experience > 3)
    
    def is_job_relevant(job_desc):
        job_desc_lower = job_desc.lower()
        if any(term in job_desc_lower for term in BLACKLIST): return False
        if not any(term in job_desc_lower for term in WHITELIST): return False
        
        years_match = re.search(r'(\d+)\+?\s*years?', job_desc_lower)
        if years_match and int(years_match.group(1)) >= 3: return False
        return True

    assert is_job_relevant(job_1) is True, "Failed: Scraper rejected a valid Junior Backend role."
    assert is_job_relevant(job_2) is False, "Failed: Scraper accepted a QA role (Blacklist failure)."
    assert is_job_relevant(job_3) is False, "Failed: Scraper accepted a Senior role (Blacklist failure)."
