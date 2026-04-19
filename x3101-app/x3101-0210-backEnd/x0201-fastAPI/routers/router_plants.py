"""
Plants Router
=============
Plant configuration endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import crud
import schemas
from database import get_db

router = APIRouter(prefix="/plants", tags=["Plants"])


@router.get("/", response_model=List[schemas.Plant])
def get_plants(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    """Get all plants with pagination."""
    skip = max(0, skip)
    limit = min(max(1, limit), 1000)
    return crud.get_plants(db, skip=skip, limit=limit)


@router.get("/{plant_id}", response_model=schemas.Plant)
def get_plant(plant_id: str, db: Session = Depends(get_db)):
    """Get plant by plant_id."""
    db_plant = crud.get_plant_by_id(db, plant_id=plant_id)
    if not db_plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    return db_plant


@router.post("/", response_model=schemas.Plant, status_code=status.HTTP_201_CREATED)
def create_plant(plant: schemas.PlantCreate, db: Session = Depends(get_db)):
    """Create new plant."""
    try:
        if crud.get_plant_by_id(db, plant_id=plant.plant_id):
            raise HTTPException(status_code=400, detail="Plant ID already exists")
        return crud.create_plant(db=db, plant=plant)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")


@router.put("/{plant_id}", response_model=schemas.Plant)
def update_plant(plant_id: str, plant: schemas.PlantUpdate, db: Session = Depends(get_db)):
    """Update plant."""
    try:
        db_plant = crud.update_plant(db, plant_id=plant_id, plant_update=plant)
        if db_plant is None:
            raise HTTPException(status_code=404, detail="Plant not found")
        return db_plant
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")


@router.delete("/{plant_id}")
def delete_plant(plant_id: str, db: Session = Depends(get_db)):
    """Delete plant."""
    try:
        db_plant = crud.delete_plant(db, plant_id=plant_id)
        if db_plant is None:
            raise HTTPException(status_code=404, detail="Plant not found")
        return {"status": "success"}
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Database error")
