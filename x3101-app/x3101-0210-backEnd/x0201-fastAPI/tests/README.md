# xMixing Backend - Unit Test Suite

## Test Coverage Summary

This test suite provides comprehensive coverage for all major backend functionality in the xMixing batch control system.

## Test Files

### 1. `test_all_functions.py` - Main Test Suite
Comprehensive tests covering:
- ✅ Ingredient CRUD operations
- ✅ Ingredient Intake List management
- ✅ Intake Summary Reports (with database joins)
- ✅ SKU and SKU Step management
- ✅ Production Plan creation (with auto-generated IDs)
- ✅ Production Batch management
- ✅ Prebatch Record tracking
- ✅ Plant CRUD operations
- ✅ Health check and monitoring endpoints

### 2. `test_ingredients.py`
Focused tests for ingredient and intake functionality:
- Ingredient creation and retrieval
- Intake list CRUD
- Report generation with proper joins

### 3. `test_skus.py`
SKU management tests:
- SKU creation and retrieval
- SKU step management

### 4. `test_production.py`
Production workflow tests:
- Production plan creation with auto-ID generation
- Batch auto-creation
- Prebatch record tracking

### 5. `test_plants.py`
Plant management tests:
- Plant CRUD operations
- Plant updates

### 6. `test_auth.py`
Authentication and user management:
- User registration
- Login functionality
- Token generation

### 7. `test_monitoring.py`
System monitoring and views:
- Server status checks
- Database view access
- History tracking

## Running Tests

### Run all tests:
```bash
cd x02-BackEnd/x0201-fastAPI
../.venv/bin/python -m pytest tests/
```

### Run specific test file:
```bash
../.venv/bin/python -m pytest tests/test_all_functions.py -v
```

### Run with coverage:
```bash
../.venv/bin/python -m pytest tests/ --cov=. --cov-report=html
```

### Run specific test:
```bash
../.venv/bin/python -m pytest tests/test_all_functions.py::test_create_ingredient -v
```

## Test Results

**Main Test Suite (test_all_functions.py):**
- ✅ 16 tests passed
- 📊 Coverage includes all major CRUD operations
- 🔄 Tests database joins and relationships
- ⚙️ Validates auto-generation logic (IDs, batches)

**Key Features Tested:**
1. **Data Consolidation**: Unified ingredient_intake_lists table
2. **Auto-Generation**: Production plan IDs, batch creation
3. **Database Joins**: Ingredient name resolution in reports
4. **History Tracking**: Status change tracking
5. **CRUD Operations**: All major entities
6. **API Endpoints**: All routers validated

## Database Compatibility

Tests use SQLite in-memory database for isolation. The models have been updated to be compatible with both MySQL (production) and SQLite (testing):
- Replaced MySQL-specific `ON UPDATE CURRENT_TIMESTAMP` with SQLAlchemy's `onupdate=func.now()`
- All timestamp fields work correctly in both databases

## Notes

- Tests are isolated using session-scoped fixtures
- Each test uses the same database session to allow testing relationships
- Unique IDs are used to prevent conflicts
- Auto-generated fields (like plan_id) are validated for correct format
