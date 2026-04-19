from sqlalchemy.orm import Session
from typing import List, Optional

import models
import schemas

def get_warehouse(db: Session, warehouse_id: str):
    return db.query(models.Warehouse).filter(models.Warehouse.warehouse_id == warehouse_id).first()

def get_warehouse_by_id(db: Session, id: int):
    return db.query(models.Warehouse).filter(models.Warehouse.id == id).first()

def get_warehouses(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Warehouse).offset(skip).limit(limit).all()

def create_warehouse(db: Session, warehouse: schemas.WarehouseCreate):
    db_warehouse = models.Warehouse(
        warehouse_id=warehouse.warehouse_id,
        name=warehouse.name,
        description=warehouse.description,
        status=warehouse.status
    )
    db.add(db_warehouse)
    db.commit()
    db.refresh(db_warehouse)
    return db_warehouse

def update_warehouse(db: Session, warehouse_id: str, warehouse_update: schemas.WarehouseUpdate):
    db_warehouse = get_warehouse(db, warehouse_id)
    if not db_warehouse:
        return None
    
    update_data = warehouse_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_warehouse, key, value)
    
    db.commit()
    db.refresh(db_warehouse)
    return db_warehouse

def delete_warehouse(db: Session, warehouse_id: str):
    db_warehouse = get_warehouse(db, warehouse_id)
    if not db_warehouse:
        return None
    db.delete(db_warehouse)
    db.commit()
    return db_warehouse

def clear_and_seed_warehouses(db: Session):
    # Clear all
    db.query(models.Warehouse).delete()
    
    # Seed new
    seed_data = [
        {"warehouse_id": "FH", "name": "Flavour House", "description": "Flavour House Storage"},
        {"warehouse_id": "SPP", "name": "SPP", "description": "SPP Storage"}
    ]
    
    for item in seed_data:
        db_warehouse = models.Warehouse(**item)
        db.add(db_warehouse)
    
    db.commit()
    return True
