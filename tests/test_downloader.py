import pytest
import respx
import httpx
import os
import shutil
import asyncio
from unittest.mock import patch, mock_open
from website_necromancer import WebsiteNecromancer

@pytest.fixture
def necromancer():
    return WebsiteNecromancer(base_url="http://example.com", directory="websites/test_example/")

@pytest.mark.asyncio
@respx.mock
async def test_get_raw_list_from_api_success(necromancer):
    mock_url = "https://web.archive.org/cdx/search/xd"
    respx.get(mock_url).mock(return_value=httpx.Response(200, json=[
        ["timestamp", "original"],
        ["20101231235959", "http://example.com/"]
    ]))
    
    async with httpx.AsyncClient() as client:
        data = await necromancer.get_raw_list_from_api(client, "http://example.com")
        
    assert len(data) == 1
    assert data[0] == ["20101231235959", "http://example.com/"]

@pytest.mark.asyncio
@respx.mock
async def test_get_raw_list_from_api_retry_503(necromancer):
    mock_url = "https://web.archive.org/cdx/search/xd"
    
    # Mock to fail twice with 503, then succeed
    route = respx.get(mock_url)
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(503),
        httpx.Response(200, json=[
            ["timestamp", "original"],
            ["20101231235959", "http://example.com/"]
        ])
    ]
    
    # We use a patch on asyncio.sleep to not actually wait 3 seconds during the test
    with patch('asyncio.sleep', return_value=None):
        async with httpx.AsyncClient() as client:
            data = await necromancer.get_raw_list_from_api(client, "http://example.com")
            
    assert len(data) == 1
    assert route.call_count == 3

@pytest.mark.asyncio
@respx.mock
async def test_get_raw_list_from_api_timeout(necromancer):
    mock_url = "https://web.archive.org/cdx/search/xd"
    
    route = respx.get(mock_url)
    route.side_effect = httpx.ReadTimeout("Timeout")
    
    with patch('asyncio.sleep', return_value=None):
        async with httpx.AsyncClient() as client:
            data = await necromancer.get_raw_list_from_api(client, "http://example.com")
            
    # Should fail and return empty list after retries
    assert data == []
    assert route.call_count == 3
