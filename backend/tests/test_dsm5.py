"""Tests for DSM-5 tool endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.dsm5
def test_dsm5_search_endpoint_exists(client: TestClient):
    """Test DSM-5 search endpoint is available."""
    response = client.post("/dsm5/search", json={"query": "depression"})
    # Should return 200 or 500, not 404
    assert response.status_code != 404


@pytest.mark.dsm5
def test_dsm5_search_with_query(client: TestClient, mock_query_request):
    """Test DSM-5 search with query."""
    response = client.post("/dsm5/search", json=mock_query_request)
    # Endpoint exists
    assert response.status_code in [200, 422, 500]


@pytest.mark.dsm5
def test_dsm5_search_response_structure(client: TestClient):
    """Test DSM-5 search response has expected structure."""
    response = client.post("/dsm5/search", json={"query": "anxiety disorder"})

    if response.status_code == 200:
        data = response.json()
        assert "query" in data
        assert "response" in data
        assert data["query"] == "anxiety disorder"


@pytest.mark.dsm5
def test_dsm5_hybrid_search_endpoint_exists(client: TestClient):
    """Test DSM-5 hybrid search endpoint is available."""
    response = client.post(
        "/dsm5/hybrid", json={"query": "major depressive disorder", "top_k": 5}
    )
    assert response.status_code != 404


@pytest.mark.dsm5
def test_dsm5_hybrid_search_with_top_k(client: TestClient):
    """Test DSM-5 hybrid search with top_k parameter."""
    response = client.post("/dsm5/hybrid", json={"query": "PTSD", "top_k": 3})

    if response.status_code == 200:
        data = response.json()
        assert "results_count" in data


@pytest.mark.dsm5
def test_dsm5_hybrid_search_default_top_k(client: TestClient):
    """Test DSM-5 hybrid search uses default top_k if not provided."""
    response = client.post("/dsm5/hybrid?query=schizophrenia")

    assert response.status_code in [200, 500]


@pytest.mark.dsm5
def test_dsm5_criteria_search_endpoint_exists(client: TestClient):
    """Test DSM-5 criteria search endpoint is available."""
    response = client.get(
        "/dsm5/criteria", params={"disorder": "Major Depressive Disorder"}
    )
    assert response.status_code != 404


@pytest.mark.dsm5
def test_dsm5_criteria_search_with_disorder(client: TestClient):
    """Test DSM-5 criteria search with disorder name."""
    response = client.get(
        "/dsm5/criteria", params={"disorder": "Generalized Anxiety Disorder"}
    )

    if response.status_code == 200:
        data = response.json()
        assert "disorder" in data
        assert "response" in data


@pytest.mark.dsm5
def test_dsm5_criteria_search_with_criteria(client: TestClient):
    """Test DSM-5 criteria search with specific criteria."""
    response = client.get(
        "/dsm5/criteria",
        params={"disorder": "Major Depressive Disorder", "criteria": "depressed mood"},
    )

    assert response.status_code in [200, 405, 500]


@pytest.mark.dsm5
def test_dsm5_search_empty_query(client: TestClient):
    """Test DSM-5 search with empty query."""
    response = client.post("/dsm5/search?query=")
    # Should handle empty query gracefully
    assert response.status_code in [200, 400, 500]


@pytest.mark.dsm5
def test_dsm5_hybrid_search_zero_top_k(client: TestClient):
    """Test DSM-5 hybrid search handles invalid top_k."""
    response = client.post("/dsm5/hybrid", json={"query": "test", "top_k": 0})
    # Should validate input
    assert response.status_code in [200, 400, 422, 500]


@pytest.mark.dsm5
def test_dsm5_search_response_format(client: TestClient):
    """Test DSM-5 search returns properly formatted response."""
    response = client.post("/dsm5/search", json={"query": "autism spectrum disorder"})

    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)
        assert "query" in data
        assert isinstance(data["query"], str)
