from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import crud
import schemas
from database import get_db

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])

@router.get("/", response_model=List[schemas.Warehouse])
def get_warehouses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all warehouses."""
    return crud.get_warehouses(db, skip=skip, limit=limit)

@router.post("/seed", status_code=status.HTTP_200_OK)
def seed_warehouses(db: Session = Depends(get_db)):
    """Clear and seed initial warehouse data (FH, SPP)."""
    try:
        crud.clear_and_seed_warehouses(db)
        return {"status": "success", "message": "Warehouses seeded with FH and SPP"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{warehouse_id}", response_model=schemas.Warehouse)
def get_warehouse(warehouse_id: str, db: Session = Depends(get_db)):
    """Get warehouse by warehouse_id."""
    db_warehouse = crud.get_warehouse(db, warehouse_id=warehouse_id)
    if not db_warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return db_warehouse

@router.post("/", response_model=schemas.Warehouse, status_code=status.HTTP_201_CREATED)
def create_warehouse(warehouse: schemas.WarehouseCreate, db: Session = Depends(get_db)):
    """Create a new warehouse."""
    if crud.get_warehouse(db, warehouse_id=warehouse.warehouse_id):
        raise HTTPException(status_code=400, detail="Warehouse ID already exists")
    return crud.create_warehouse(db=db, warehouse=warehouse)

@router.put("/{warehouse_id}", response_model=schemas.Warehouse)
def update_warehouse(warehouse_id: str, warehouse: schemas.WarehouseUpdate, db: Session = Depends(get_db)):
    """Update a warehouse."""
    db_warehouse = crud.update_warehouse(db, warehouse_id=warehouse_id, warehouse_update=warehouse)
    if not db_warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return db_warehouse

@router.delete("/{warehouse_id}")
def delete_warehouse(warehouse_id: str, db: Session = Depends(get_db)):
    """Delete a warehouse."""
    db_warehouse = crud.delete_warehouse(db, warehouse_id=warehouse_id)
    if not db_warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return {"status": "success"}
