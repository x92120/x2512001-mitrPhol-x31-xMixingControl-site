"""
Ingredients Router
==================
Ingredient management and intake list endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import csv
import io
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Ingredients"])


# =============================================================================
# INGREDIENT ENDPOINTS
# =============================================================================

@router.get("/ingredients/", response_model=List[schemas.Ingredient])
def read_ingredients(
    skip: int = 0, 
    limit: int = 1000, 
    mat_sap_code: str = None,
    lookup: str = None,
    db: Session = Depends(get_db)
):
    """Get all ingredients with pagination, optionally filter by MAT.SAP Code or lookup."""
    if lookup:
        ingredient = crud.search_ingredient(db, query=lookup)
        return [ingredient] if ingredient else []

    if mat_sap_code:
        ingredient = crud.get_ingredient_by_mat_sap_code(db, mat_sap_code=mat_sap_code)
        return [ingredient] if ingredient else []

    skip = max(0, skip)
    limit = min(max(1, limit), 1000)
    return crud.get_ingredients(db, skip=skip, limit=limit)


@router.get("/ingredients/{ingredient_id}", response_model=schemas.Ingredient)
def read_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    """Get ingredient by ID."""
    db_ingredient = crud.get_ingredient_by_id(db, ingredient_db_id=ingredient_id)
    if db_ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return db_ingredient


@router.post("/ingredients/", response_model=schemas.Ingredient)
def create_ingredient(ingredient: schemas.IngredientCreate, db: Session = Depends(get_db)):
    """Create new ingredient."""
    try:
        if ingredient.mat_sap_code and crud.get_ingredient_by_mat_sap_code(db, mat_sap_code=ingredient.mat_sap_code):
            raise HTTPException(status_code=400, detail="MAT.SAP Code already exists")
        return crud.create_ingredient(db=db, ingredient=ingredient)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")


@router.put("/ingredients/{ingredient_db_id}", response_model=schemas.Ingredient)
def update_ingredient(ingredient_db_id: int, ingredient: schemas.IngredientCreate, db: Session = Depends(get_db)):
    """Update ingredient."""
    try:
        updated = crud.update_ingredient(db, ingredient_id=ingredient_db_id, ingredient=ingredient)
        if updated is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")


@router.delete("/ingredients/{ingredient_db_id}")
def delete_ingredient(ingredient_db_id: int, db: Session = Depends(get_db)):
    """Delete ingredient."""
    try:
        deleted = crud.delete_ingredient(db, ingredient_id=ingredient_db_id)
        if deleted is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return {"status": "success"}
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")




# =============================================================================
# INTAKE FROM ENDPOINTS
# =============================================================================

@router.get("/intake-from/", response_model=List[schemas.IngredientIntakeFrom])
def read_intake_from_all(db: Session = Depends(get_db)):
    """Get all intake from locations."""
    return crud.get_intake_from_all(db)

@router.post("/intake-from/", response_model=schemas.IngredientIntakeFrom)
def create_intake_from(data: schemas.IngredientIntakeFromCreate, db: Session = Depends(get_db)):
    """Create new intake from location."""
    return crud.create_intake_from(db, data)

@router.put("/intake-from/{intake_from_id}", response_model=schemas.IngredientIntakeFrom)
def update_intake_from(intake_from_id: int, data: schemas.IngredientIntakeFromCreate, db: Session = Depends(get_db)):
    """Update intake from location."""
    updated = crud.update_intake_from(db, intake_from_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Intake from location not found")
    return updated

@router.delete("/intake-from/{intake_from_id}")
def delete_intake_from(intake_from_id: int, db: Session = Depends(get_db)):
    """Delete intake from location."""
    success = crud.delete_intake_from(db, intake_from_id)
    if not success:
        raise HTTPException(status_code=404, detail="Intake from location not found")
    return {"status": "success"}
 
# =============================================================================
# PACKAGE CONTAINER TYPE ENDPOINTS
# =============================================================================

@router.get("/package-container-types/", response_model=List[schemas.PackageContainerType])
def read_container_types(db: Session = Depends(get_db)):
    """Get all package container types."""
    return crud.get_container_types(db)

@router.post("/package-container-types/", response_model=schemas.PackageContainerType)
def create_container_type(data: schemas.PackageContainerTypeCreate, db: Session = Depends(get_db)):
    """Create new package container type."""
    return crud.create_container_type(db, data)

@router.put("/package-container-types/{type_id}", response_model=schemas.PackageContainerType)
def update_container_type(type_id: int, data: schemas.PackageContainerTypeCreate, db: Session = Depends(get_db)):
    """Update package container type."""
    updated = crud.update_container_type(db, type_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Container type not found")
    return updated

@router.delete("/package-container-types/{type_id}")
def delete_container_type(type_id: int, db: Session = Depends(get_db)):
    """Delete package container type."""
    success = crud.delete_container_type(db, type_id)
    if not success:
        raise HTTPException(status_code=404, detail="Container type not found")
    return {"status": "success"}
 
# =============================================================================
# PACKAGE CONTAINER SIZE ENDPOINTS
# =============================================================================

@router.get("/package-container-sizes/", response_model=List[schemas.PackageContainerSize])
def read_container_sizes(container_type: Optional[str] = None, db: Session = Depends(get_db)):
    """Get all package container sizes."""
    return crud.get_container_sizes(db, container_type=container_type)

@router.post("/package-container-sizes/", response_model=schemas.PackageContainerSize)
def create_container_size(data: schemas.PackageContainerSizeCreate, db: Session = Depends(get_db)):
    """Create new package container size."""
    return crud.create_container_size(db, data)

@router.put("/package-container-sizes/{size_id}", response_model=schemas.PackageContainerSize)
def update_container_size(size_id: int, data: schemas.PackageContainerSizeCreate, db: Session = Depends(get_db)):
    """Update package container size."""
    updated = crud.update_container_size(db, size_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Container size not found")
    return updated

@router.delete("/package-container-sizes/{size_id}")
def delete_container_size(size_id: int, db: Session = Depends(get_db)):
    """Delete package container size."""
    success = crud.delete_container_size(db, size_id)
    if not success:
        raise HTTPException(status_code=404, detail="Container size not found")
    return {"status": "success"}

# =============================================================================
# INGREDIENT INTAKE LIST ENDPOINTS
# =============================================================================

@router.get("/ingredient-intake-lists/", response_model=List[schemas.IngredientIntakeList])
def get_ingredient_intake_lists(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    """Get all ingredient intake list records with pagination."""
    limit = min(max(1, limit), 1000)
    return crud.get_ingredient_intake_lists(db, skip=skip, limit=limit)


@router.get("/ingredient-intake-next-id")
def get_next_intake_id(db: Session = Depends(get_db)):
    """Get next auto-generated intake ID."""
    return {"next_id": crud.get_next_intake_id(db)}


@router.post("/migrate-add-intake-to")
def migrate_add_intake_to(db: Session = Depends(get_db)):
    """One-time migration: add intake_to column."""
    from sqlalchemy import text
    try:
        db.execute(text("ALTER TABLE ingredient_intake_lists ADD COLUMN intake_to VARCHAR(50)"))
        db.commit()
        return {"status": "ok", "message": "intake_to column added"}
    except Exception as e:
        return {"status": "exists", "message": str(e)}


@router.get("/ingredient-intake-lists/{list_id}", response_model=schemas.IngredientIntakeList)
def get_ingredient_intake_list(list_id: str, db: Session = Depends(get_db)):
    """Get ingredient intake list by ID."""
    db_list = crud.get_ingredient_intake_list(db, list_id=list_id)
    if db_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    return db_list


@router.post("/ingredient-intake-lists/", response_model=schemas.IngredientIntakeList)
def create_ingredient_intake_list(list_data: schemas.IngredientIntakeListCreate, db: Session = Depends(get_db)):
    """Create new ingredient intake list."""
    try:
        return crud.create_ingredient_intake_list(db=db, list_data=list_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")


@router.put("/ingredient-intake-lists/{list_id}", response_model=schemas.IngredientIntakeList)
def update_ingredient_intake_list(list_id: str, list_data: schemas.IngredientIntakeListCreate, db: Session = Depends(get_db)):
    """Update ingredient intake list."""
    try:
        db_list = crud.update_ingredient_intake_list(db, list_id=list_id, list_update=list_data)
        if db_list is None:
            raise HTTPException(status_code=404, detail="List not found")
        return db_list
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")


@router.delete("/ingredient-intake-lists/{list_id}")
def delete_ingredient_intake_list(list_id: str, db: Session = Depends(get_db)):
    """Delete ingredient intake list."""
    try:
        db_list = crud.delete_ingredient_intake_list(db, list_id=list_id)
        if db_list is None:
            raise HTTPException(status_code=404, detail="List not found")
        return {"status": "success"}
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")


def parse_date_flexible(date_str: str):
    """Parse date string with support for multiple formats including Buddhist Era."""
    if not date_str:
        return None
    try:
        date_str = date_str.split(' ')[0]
        parts = date_str.replace('-', '/').split('/')
        if len(parts) == 3:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y > 2400:  # Buddhist Era
                y -= 543
            return datetime(y, m, d)
    except (ValueError, IndexError):
        pass
    return None


@router.post("/ingredient-intake-lists/bulk-import")
async def bulk_import_ingredient_intake(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Bulk import ingredient intakes from CSV."""
    try:
        content = await file.read()
        try:
            decoded = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded = content.decode('cp874', errors='ignore')

        reader = csv.DictReader(io.StringIO(decoded))
        imported_count = 0
        errors = []

        for i, row in enumerate(reader):
            try:
                row_clean = {k.strip(): v.strip() for k, v in row.items() if k}
                
                mat_code = row_clean.get('Material') or row_clean.get('mat_sap_code')
                if not mat_code:
                    errors.append(f"Row {i+1}: Missing Material code")
                    continue

                try:
                    intake_vol = float(row_clean.get('Intake Vol (kg)', 0) or 0)
                    remain_vol = float(row_clean.get('Remain Vol (kg)', 0) or intake_vol)
                    pkg_vol = float(row_clean.get('Pkg Vol', 0) or 0)
                except ValueError:
                    errors.append(f"Row {i+1}: Invalid volume numbers")
                    continue

                # Look up ingredient master to fill in missing re_code or description
                ing_master = crud.get_ingredient_by_mat_sap_code(db, mat_sap_code=mat_code)
                re_code_val = row_clean.get('Re-Code') or (ing_master.re_code if ing_master else None)
                mat_desc_val = row_clean.get('Material Description') or (ing_master.name if ing_master else None)
                mat_uom_val = row_clean.get('Base Unit of Measure') or row_clean.get('UoM') or (ing_master.unit if ing_master else None)

                item = schemas.IngredientIntakeListCreate(
                    intake_lot_id=crud.get_next_intake_id(db),
                    intake_from=row_clean.get('Storage Location') or row_clean.get('Storage Loca'),
                    mat_sap_code=mat_code,
                    re_code=re_code_val,
                    material_description=mat_desc_val,
                    uom=mat_uom_val,
                    intake_vol=intake_vol,
                    remain_vol=remain_vol,
                    intake_package_vol=pkg_vol,
                    package_intake=int(intake_vol/pkg_vol) if pkg_vol > 0 else 0,
                    expire_date=parse_date_flexible(row_clean.get('Expire Date')),
                    status='Active',
                    intake_by='import',
                    manufacturing_date=parse_date_flexible(row_clean.get('Date of Manufacture'))
                )
                
                crud.create_ingredient_intake_list(db, item)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)}")

        return {"status": "success", "imported_count": imported_count, "errors": errors or None}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process file: {str(e)}")
