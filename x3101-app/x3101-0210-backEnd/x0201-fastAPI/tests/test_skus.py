import pytest

def test_create_sku(client):
    response = client.post(
        "/skus/",
        json={
            "sku_id": "SKU-TEST-002",
            "sku_name": "Test SKU 2",
            "std_batch_size": 1000.0,
            "uom": "kg",
            "status": "Active",
            "creat_by": "testuser"
        }
    )
    if response.status_code != 200:
        print(f"Error creating SKU: {response.json()}")
    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "SKU-TEST-002"

def test_get_skus(client):
    response = client.get("/skus/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

def test_create_sku_step(client):
    response = client.post(
        "/sku-steps/",
        json={
            "sku_id": "SKU-TEST-002",
            "phase_number": "10",
            "sub_step": 1,
            "action": "Mixing",
            "re_code": "RE-TEST-001",
            "require": 50.0,
            "uom": "kg"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "Mixing"

def test_get_sku_steps(client):
    response = client.get("/sku-steps/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
