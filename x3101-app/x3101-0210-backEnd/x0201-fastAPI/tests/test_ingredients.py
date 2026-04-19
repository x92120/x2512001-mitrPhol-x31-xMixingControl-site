import pytest
from datetime import datetime

def test_create_ingredient(client):
    response = client.post(
        "/ingredients/",
        json={
            "ingredient_id": "TEST-ING-001",
            "name": "Test Ingredient",
            "mat_sap_code": "MAT-TEST-001",
            "re_code": "RE-TEST-001",
            "unit": "kg",
            "creat_by": "testuser"
        }
    )
    if response.status_code != 200:
        print(f"Error: {response.json()}")
    assert response.status_code == 200
    data = response.json()
    assert data["ingredient_id"] == "TEST-ING-001"

def test_get_ingredients(client):
    response = client.get("/ingredients/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

def test_create_intake_list(client):
    response = client.post(
        "/ingredient-intake-lists/",
        json={
            "intake_lot_id": "INTAKE-TEST-001",
            "mat_sap_code": "MAT-TEST-001",
            "re_code": "RE-TEST-001",
            "material_description": "Test Ingredient Description",
            "uom": "kg",
            "intake_vol": 100.0,
            "remain_vol": 100.0,
            "intake_by": "testuser",
            "status": "Active"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intake_lot_id"] == "INTAKE-TEST-001"

def test_get_intake_lists(client):
    """Test retrieving all intake lists"""
    response = client.get("/ingredient-intake-lists/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_get_intake_by_id(client):
    """Test retrieving a specific intake list by ID"""
    # First create one
    create_response = client.post(
        "/ingredient-intake-lists/",
        json={
            "intake_lot_id": "INTAKE-GET-TEST",
            "mat_sap_code": "MAT-TEST-001",
            "re_code": "RE-TEST-001",
            "material_description": "Get Test",
            "uom": "kg",
            "intake_vol": 50.0,
            "remain_vol": 50.0,
            "intake_by": "testuser",
            "status": "Active"
        }
    )
    assert create_response.status_code == 200
    intake_id = create_response.json()["id"]
    
    # Retrieve it
    response = client.get(f"/ingredient-intake-lists/{intake_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["intake_lot_id"] == "INTAKE-GET-TEST"
