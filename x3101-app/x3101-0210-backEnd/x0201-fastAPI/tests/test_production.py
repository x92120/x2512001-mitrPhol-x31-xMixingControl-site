import pytest
from datetime import date

def test_create_production_plan(client):
    response = client.post(
        "/production-plans/",
        json={
            "plan_id": "WILL-BE-IGNORED",
            "sku_id": "SKU-TEST-001",
            "sku_name": "Test SKU",
            "plant": "Mixing 1",
            "total_volume": 2000.0,
            "batch_size": 1000.0,
            "num_batches": 2,
            "start_date": str(date.today()),
            "status": "Planned",
            "created_by": "testuser"
        }
    )
    assert response.status_code == 200
    data = response.json()
    # verify it starts with 'plan-' instead of equaling the dummy input
    assert data["plan_id"].startswith("plan-Mixing1")
    assert data["num_batches"] == 2

def test_get_production_batches(client):
    response = client.get("/production-batches/")
    assert response.status_code == 200
    data = response.json()
    # Batches should have been auto-created
    assert len(data) >= 2

def test_create_prebatch_record(client):
    # Get a plan_id first
    response = client.get("/production-plans/")
    data = response.json()
    plans = data.get("plans", data) if isinstance(data, dict) else data
    if len(plans) > 0:
        plan_id = plans[0]["plan_id"]
        
        response = client.post(
            "/prebatch-recs/",
            json={
                "batch_record_id": f"{plan_id}-B1-RE-TEST-001-1",
                "plan_id": plan_id,
                "re_code": "RE-TEST-001",
                "package_no": 1,
                "total_packages": 2,
                "net_volume": 25.0,
                "total_volume": 50.0,
                "total_request_volume": 25.0
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["batch_record_id"] == f"{plan_id}-B1-RE-TEST-001-1"
