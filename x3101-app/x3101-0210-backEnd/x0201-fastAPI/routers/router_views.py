"""
Views Router
============
Database view endpoints (read-only).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db

router = APIRouter(prefix="/api", tags=["Views"])


@router.get("/v_sku_master_detail", response_model=List[schemas.VSkuMasterDetail])
def get_sku_master_detail_view(
    skip: int = 0, 
    limit: int = 100, 
    search: str = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get SKU master list with step counts and metadata."""
    query = db.query(models.VSkuMasterDetail)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (models.VSkuMasterDetail.sku_id.like(search_filter)) |
            (models.VSkuMasterDetail.sku_name.like(search_filter))
        )
    
    if status:
        query = query.filter(models.VSkuMasterDetail.status == status)
    
    query = query.order_by(models.VSkuMasterDetail.updated_at.desc())
    return query.offset(skip).limit(limit).all()


@router.get("/v_sku_step_detail", response_model=List[schemas.VSkuStepDetail])
def get_sku_step_detail_view(
    sku_id: str = None,
    skip: int = 0, 
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """Get SKU steps with all lookups and computed fields."""
    query = db.query(models.VSkuStepDetail)
    
    if sku_id:
        query = query.filter(models.VSkuStepDetail.sku_id == sku_id)
    
    query = query.order_by(
        models.VSkuStepDetail.sku_id,
        models.VSkuStepDetail.phase_number,
        models.VSkuStepDetail.sub_step
    )
    return query.offset(skip).limit(limit).all()


@router.get("/v_sku_complete", response_model=List[schemas.VSkuComplete])
def get_sku_complete_view(
    sku_id: str = None,
    skip: int = 0, 
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """Get complete denormalized SKU data (for export/reporting)."""
    query = db.query(models.VSkuComplete)
    
    if sku_id:
        query = query.filter(models.VSkuComplete.sku_id == sku_id)
    
    query = query.order_by(
        models.VSkuComplete.sku_id,
        models.VSkuComplete.phase_number,
        models.VSkuComplete.sub_step
    )
    return query.offset(skip).limit(limit).all()


@router.get("/v_sku_master_detail/{sku_id}", response_model=schemas.VSkuMasterDetail)
def get_single_sku_master_detail(sku_id: str, db: Session = Depends(get_db)):
    """Get single SKU master detail by SKU ID."""
    sku = db.query(models.VSkuMasterDetail).filter(
        models.VSkuMasterDetail.sku_id == sku_id
    ).first()
    
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    return sku
