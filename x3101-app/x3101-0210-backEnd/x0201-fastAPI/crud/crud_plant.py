from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional, List
import models
import schemas

# Plant CRUD
def get_plants(db: Session, skip: int = 0, limit: int = 100) -> List[models.Plant]:
    """Get list of plants with pagination"""
    return db.query(models.Plant).filter(models.Plant.status == "Active").order_by(models.Plant.plant_id).offset(skip).limit(limit).all()

def get_plant_by_id(db: Session, plant_id: str) -> Optional[models.Plant]:
    """Get plant by plant_id"""
    return db.query(models.Plant).filter(models.Plant.plant_id == plant_id).first()

def create_plant(db: Session, plant: schemas.PlantCreate) -> models.Plant:
    """Create new plant with error handling"""
    try:
        db_plant = models.Plant(**plant.dict())
        db.add(db_plant)
        db.commit()
        db.refresh(db_plant)
        return db_plant
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def update_plant(db: Session, plant_id: str, plant_update: schemas.PlantUpdate) -> Optional[models.Plant]:
    """Update plant with error handling"""
    try:
        db_plant = db.query(models.Plant).filter(models.Plant.plant_id == plant_id).first()
        if not db_plant:
            return None
        
        update_data = plant_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_plant, key, value)
            
        db.commit()
        db.refresh(db_plant)
        return db_plant
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def delete_plant(db: Session, plant_id: str) -> Optional[models.Plant]:
    """Delete plant with error handling"""
    try:
        db_plant = db.query(models.Plant).filter(models.Plant.plant_id == plant_id).first()
        if db_plant:
            db.delete(db_plant)
            db.commit()
        return db_plant
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")
