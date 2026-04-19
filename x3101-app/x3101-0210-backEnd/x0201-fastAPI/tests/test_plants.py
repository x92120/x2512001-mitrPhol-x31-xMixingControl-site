import pytest

def test_create_plant(client):
    response = client.post(
        "/plants/",
        json={
            "plant_id": "PLANT-TEST-001",
            "plant_name": "Test Mixing Plant",
            "plant_capacity": 5000.0,
            "plant_description": "Test plant for unit testing",
            "status": "Active"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["plant_id"] == "PLANT-TEST-001"

def test_get_plants(client):
    response = client.get("/plants/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

def test_get_plant_by_id(client):
    response = client.get("/plants/PLANT-TEST-001")
    assert response.status_code == 200
    data = response.json()
    assert data["plant_id"] == "PLANT-TEST-001"

def test_update_plant(client):
    response = client.put(
        "/plants/PLANT-TEST-001",
        json={
            "plant_name": "Updated Test Plant",
            "plant_capacity": 6000.0
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["plant_name"] == "Updated Test Plant"
    assert data["plant_capacity"] == 6000.0
