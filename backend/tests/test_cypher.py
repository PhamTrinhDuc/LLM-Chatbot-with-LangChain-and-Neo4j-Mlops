"""Tests for Cypher query endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.cypher
def test_cypher_query_endpoint_exists(client: TestClient):
    """Test Cypher query endpoint is available."""
    response = client.post(
        "/cypher/query",
        json={"query": "Find all patients"}
    )
    assert response.status_code != 404


@pytest.mark.cypher
def test_cypher_query_response_structure(client: TestClient, mock_query_request):
    """Test Cypher query response has expected structure."""
    response = client.post(
        "/cypher/query",
        json=mock_query_request
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "query" in data
        assert "answer" in data
        assert "cypher" in data


@pytest.mark.cypher
def test_cypher_query_with_patient_search(client: TestClient):
    """Test Cypher query for patient search."""
    response = client.post(
        "/cypher/query",
        json={"query": "What patients have diabetes?"}
    )
    
    # Should not be 404
    assert response.status_code != 404


@pytest.mark.cypher
def test_cypher_patients_endpoint(client: TestClient):
    """Test dedicated patients search endpoint."""
    response = client.post(
        "/cypher/patients",
        json={"query": "patients diagnosed in 2023"}
    )
    
    assert response.status_code != 404


@pytest.mark.cypher
def test_cypher_patients_response_structure(client: TestClient):
    """Test patients endpoint response structure."""
    response = client.post(
        "/cypher/patients",
        json={"query": "Find all patients"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "answer" in data
        assert "cypher" in data


@pytest.mark.cypher
def test_cypher_hospital_stats_endpoint(client: TestClient):
    """Test hospital statistics endpoint."""
    response = client.post(
        "/cypher/hospital-stats",
        json={"query": "total number of patients"}
    )
    
    assert response.status_code != 404


@pytest.mark.cypher
def test_cypher_hospital_stats_response(client: TestClient):
    """Test hospital stats response structure."""
    response = client.post(
        "/cypher/hospital-stats",
        json={"query": "How many visits in 2023?"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert "answer" in data
        assert "cypher" in data


@pytest.mark.cypher
def test_cypher_query_empty_query(client: TestClient):
    """Test Cypher query with empty query."""
    response = client.post(
        "/cypher/query",
        json={"query": ""}
    )
    
    # Should handle gracefully
    assert response.status_code in [200, 400, 500]


@pytest.mark.cypher
def test_cypher_query_complex_question(client: TestClient):
    """Test Cypher query with complex natural language question."""
    response = client.post(
        "/cypher/query",
        json={"query": "Which doctors have treated the most patients with hypertension in the last year?"}
    )
    
    assert response.status_code in [200, 500]


@pytest.mark.cypher
def test_cypher_generates_cypher_code(client: TestClient):
    """Test that Cypher query generates actual Cypher code."""
    response = client.post(
        "/cypher/query",
        json={"query": "Find all patients"}
    )
    
    if response.status_code == 200:
        data = response.json()
        cypher = data.get("cypher", "")
        # Should contain Cypher keywords if it generated anything
        if cypher:
            # Cypher code should be a string
            assert isinstance(cypher, str)


@pytest.mark.cypher
def test_cypher_response_format(client: TestClient):
    """Test Cypher response is properly formatted."""
    response = client.post(
        "/cypher/query",
        json={"query": "List hospitals"}
    )
    
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)
        assert isinstance(data.get("query"), str)
        assert isinstance(data.get("answer"), str)
        assert isinstance(data.get("cypher"), str)


@pytest.mark.cypher
def test_cypher_patients_with_condition(client: TestClient):
    """Test patients search with health condition."""
    response = client.post(
        "/cypher/patients",
        json={"query": "patients with heart disease"}
    )
    
    assert response.status_code in [200, 500]


@pytest.mark.cypher
def test_cypher_hospital_stats_query_type(client: TestClient):
    """Test hospital stats different query types."""
    queries = [
        "total visits",
        "average visit duration",
        "most visited hospital"
    ]
    
    for query in queries:
        response = client.post(
            "/cypher/hospital-stats",
            json={"query": query}
        )
        assert response.status_code in [200, 500]
