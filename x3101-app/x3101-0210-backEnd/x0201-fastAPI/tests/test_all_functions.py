"""
Comprehensive Unit Tests for xMixing FastAPI Backend
=====================================================
Test coverage for all major functionality including:
- Ingredients and Intake Lists
- SKUs and SKU Steps  
- Production Plans and Batches
- Prebatch Records
- Plants
- Users and Authentication
- Monitoring and Views
"""

import pytest
from datetime import datetime

# ============================================================================
# INGREDIENT TESTS
# ============================================================================

def test_create_ingredient(client):
    """Test creating a new ingredient"""
    response = client.post(
        "/ingredients/",
        json={
            "ingredient_id": "TEST-ING-002",
            "name": "Test Ingredient 2",
            "mat_sap_code": "MAT-TEST-002",
            "re_code": "RE-TEST-002",
            "unit": "kg",
            "creat_by": "testuser"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ingredient_id"] == "TEST-ING-002"
    assert data["name"] == "Test Ingredient 2"

def test_get_ingredients(client):
    """Test retrieving all ingredients"""
    response = client.get("/ingredients/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_search_ingredient(client):
    """Test searching for an ingredient"""
    response = client.get("/ingredients/?lookup=TEST-ING-002")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["ingredient_id"] == "TEST-ING-002"

# ============================================================================
# INTAKE LIST TESTS
# ============================================================================

def test_create_intake_list(client):
    """Test creating an ingredient intake record"""
    response = client.post(
        "/ingredient-intake-lists/",
        json={
            "intake_lot_id": "INTAKE-TEST-002",
            "mat_sap_code": "MAT-TEST-002",
            "re_code": "RE-TEST-002",
            "material_description": "Test Ingredient 2 Description",
            "uom": "kg",
            "intake_vol": 100.0,
            "remain_vol": 100.0,
            "intake_by": "testuser",
            "status": "Active"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intake_lot_id"] == "INTAKE-TEST-002"
    assert data["remain_vol"] == 100.0

def test_get_intake_lists(client):
    """Test retrieving all intake lists"""
    response = client.get("/ingredient-intake-lists/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

# ============================================================================
# SKU TESTS
# ============================================================================

def test_create_sku(client):
    """Test creating a new SKU"""
    response = client.post(
        "/skus/",
        json={
            "sku_id": "SKU-TEST-003",
            "sku_name": "Test SKU 3",
            "std_batch_size": 1000.0,
            "uom": "kg",
            "status": "Active",
            "creat_by": "testuser"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "SKU-TEST-003"

def test_get_skus(client):
    """Test retrieving all SKUs"""
    response = client.get("/skus/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_create_sku_step(client):
    """Test creating a SKU step"""
    response = client.post(
        "/sku-steps/",
        json={
            "sku_id": "SKU-TEST-003",
            "phase_number": "10",
            "sub_step": 1,
            "action": "Mixing",
            "re_code": "RE-TEST-002",
            "require": 50.0,
            "uom": "kg"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "Mixing"

# ============================================================================
# PRODUCTION TESTS
# ============================================================================

def test_create_production_plan(client):
    """Test creating a production plan with auto-generated ID"""
    from datetime import date
    response = client.post(
        "/production-plans/",
        json={
            "sku_id": "SKU-TEST-003",
            "sku_name": "Test SKU 3",
            "plant": "Mixing 2",
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
    assert data["plan_id"].startswith("plan-Mixing2")
    assert data["num_batches"] == 2

def test_get_production_batches(client):
    """Test retrieving production batches"""
    response = client.get("/production-batches/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_create_prebatch_record(client):
    """Test creating a prebatch record"""
    # Get a plan_id first
    response = client.get("/production-plans/")
    data = response.json()
    plans = data.get("plans", data) if isinstance(data, dict) else data
    if len(plans) > 0:
        plan_id = plans[0]["plan_id"]
        
        response = client.post(
            "/prebatch-recs/",
            json={
                "batch_record_id": f"{plan_id}-TEST-REC-1",
                "plan_id": plan_id,
                "re_code": "RE-TEST-002",
                "package_no": 1,
                "total_packages": 2,
                "net_volume": 25.0,
                "total_volume": 50.0,
                "total_request_volume": 25.0
            }
        )
        assert response.status_code == 200

# ============================================================================
# PLANT TESTS
# ============================================================================

def test_create_plant(client):
    """Test creating a plant"""
    response = client.post(
        "/plants/",
        json={
            "plant_id": "PLANT-TEST-002",
            "plant_name": "Test Mixing Plant 2",
            "plant_capacity": 5000.0,
            "plant_description": "Test plant",
            "status": "Active"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["plant_id"] == "PLANT-TEST-002"

def test_get_plants(client):
    """Test retrieving all plants"""
    response = client.get("/plants/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

# ============================================================================
# MONITORING TESTS
# ============================================================================

def test_root_endpoint(client):
    """Test the root health check endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "xMixing API"
    assert data["status"] == "connected"

def test_server_status(client):
    """Test the server status monitoring endpoint"""
    response = client.get("/server-status")
    assert response.status_code == 200
    data = response.json()
    # The actual response contains system metrics
    assert isinstance(data, dict)
    assert "cpu_percent" in data
    assert "memory" in data
