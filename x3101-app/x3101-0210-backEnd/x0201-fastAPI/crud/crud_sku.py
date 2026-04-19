from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional, List
import models
import schemas

# Sku CRUD
def get_sku_by_sku_id(db: Session, sku_id: str) -> Optional[models.Sku]:
    return db.query(models.Sku).options(joinedload(models.Sku.steps)).filter(models.Sku.sku_id == sku_id).first()

def get_skus(db: Session, skip: int = 0, limit: int = 100) -> List[models.Sku]:
    return db.query(models.Sku).options(joinedload(models.Sku.steps)).order_by(models.Sku.created_at.desc()).offset(skip).limit(limit).all()

def create_sku(db: Session, sku: schemas.SkuCreate) -> models.Sku:
    try:
        # Create sku
        db_sku = models.Sku(
            sku_id=sku.sku_id,
            sku_name=sku.sku_name,
            std_batch_size=sku.std_batch_size,
            uom=sku.uom,
            sku_group=getattr(sku, 'sku_group', None),
            status=sku.status,
            creat_by=getattr(sku, 'creat_by', 'system'),
            update_by=getattr(sku, 'update_by', 'system')
        )
        db.add(db_sku)
        db.commit()
        db.refresh(db_sku)

        # Create steps if any
        if sku.steps:
            for step in sku.steps:
                step_data = step.dict()
                step_data['sku_id'] = db_sku.sku_id # Ensure FK is set
                db_step = models.SkuStep(**step_data)
                db.add(db_step)
            db.commit()
            db.refresh(db_sku)
            
        return db_sku
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def update_sku(db: Session, sku_db_id: int, sku_update: schemas.SkuCreate) -> Optional[models.Sku]:
    try:
        db_sku = db.query(models.Sku).filter(models.Sku.id == sku_db_id).first()
        if not db_sku:
            return None

        # Update sku fields
        db_sku.sku_id = sku_update.sku_id
        db_sku.sku_name = sku_update.sku_name
        db_sku.std_batch_size = sku_update.std_batch_size
        db_sku.uom = sku_update.uom
        db_sku.sku_group = getattr(sku_update, 'sku_group', db_sku.sku_group)
        db_sku.status = sku_update.status
        
        # Update steps: Delete existing and add new ONLY if steps are provided in update
        # This prevents wiping steps when just updating header (which sends steps=None or missing)
        if 'steps' in sku_update.dict(exclude_unset=True):
            # Delete existing steps using sku_id (string)
            db.query(models.SkuStep).filter(models.SkuStep.sku_id == db_sku.sku_id).delete()
            
            if sku_update.steps:
                for step in sku_update.steps:
                    step_data = step.dict()
                    step_data['sku_id'] = db_sku.sku_id
                    db_step = models.SkuStep(**step_data)
                    db.add(db_step)
        
        db.commit()
        db.refresh(db_sku)
        return db_sku

    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def delete_sku(db: Session, sku_db_id: int) -> Optional[models.Sku]:
    try:
        db_sku = db.query(models.Sku).filter(models.Sku.id == sku_db_id).first()
        if db_sku:
            db.delete(db_sku)
            db.commit()
        return db_sku
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def duplicate_sku(db: Session, dup_data: schemas.SkuDuplicate) -> models.Sku:
    try:
        # 1. Fetch source SKU
        source_sku = db.query(models.Sku).filter(models.Sku.sku_id == dup_data.source_sku_id).first()
        if not source_sku:
            raise ValueError(f"Source SKU {dup_data.source_sku_id} not found")

        # 2. Check if new SKU ID exists
        if db.query(models.Sku).filter(models.Sku.sku_id == dup_data.new_sku_id).first():
            raise ValueError(f"Target SKU ID {dup_data.new_sku_id} already exists")

        # 3. Create new SKU Header
        new_sku = models.Sku(
            sku_id=dup_data.new_sku_id,
            sku_name=dup_data.new_sku_name,
            std_batch_size=source_sku.std_batch_size,
            uom=source_sku.uom,
            sku_group=source_sku.sku_group,
            status="Active",
            creat_by=dup_data.creat_by,
            update_by=dup_data.creat_by
        )
        db.add(new_sku)
        db.flush() # Flush to get it ready for relationship or ensure identity

        # 4. Copy Steps
        source_steps = db.query(models.SkuStep).filter(models.SkuStep.sku_id == dup_data.source_sku_id).all()
        for step in source_steps:
            # Create a new step instance by copying values
            # We exclude 'id', 'created_at', 'updated_at' and 'sku_id'
            step_dict = {column.name: getattr(step, column.name) for column in step.__table__.columns if column.name not in ["id", "created_at", "updated_at", "sku_id"]}
            step_dict["sku_id"] = new_sku.sku_id
            
            new_step = models.SkuStep(**step_dict)
            db.add(new_step)

        db.commit()
        db.refresh(new_sku)
        return new_sku

    except Exception as e:
        db.rollback()
        raise e

# SkuAction CRUD
def get_sku_actions(db: Session, skip: int = 0, limit: int = 100) -> List[models.SkuAction]:
    return db.query(models.SkuAction).offset(skip).limit(limit).all()

def create_sku_action(db: Session, action: schemas.SkuActionCreate) -> models.SkuAction:
    db_action = models.SkuAction(
        action_code=action.action_code,
        action_description=action.action_description,
        component_filter=action.component_filter
    )
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action

def update_sku_action(db: Session, action_code: str, action_update: schemas.SkuActionCreate) -> Optional[models.SkuAction]:
    db_action = db.query(models.SkuAction).filter(models.SkuAction.action_code == action_code).first()
    if db_action:
        # We generally don't update the Primary Key (action_code)
        db_action.action_description = action_update.action_description
        db_action.component_filter = action_update.component_filter # Update the filter
        db.commit()
        db.refresh(db_action)
    return db_action

def delete_sku_action(db: Session, action_code: str) -> Optional[models.SkuAction]:
    db_action = db.query(models.SkuAction).filter(models.SkuAction.action_code == action_code).first()
    if db_action:
        db.delete(db_action)
        db.commit()
    return db_action

# SkuDestination CRUD
def get_sku_destinations(db: Session, skip: int = 0, limit: int = 100) -> List[models.SkuDestination]:
    return db.query(models.SkuDestination).offset(skip).limit(limit).all()

def create_sku_destination(db: Session, dest: schemas.SkuDestinationCreate) -> models.SkuDestination:
    db_dest = models.SkuDestination(
        destination_code=dest.destination_code,
        description=dest.description
    )
    db.add(db_dest)
    db.commit()
    db.refresh(db_dest)
    return db_dest

def update_sku_destination(db: Session, dest_id: int, dest_update: schemas.SkuDestinationCreate) -> Optional[models.SkuDestination]:
    db_dest = db.query(models.SkuDestination).filter(models.SkuDestination.id == dest_id).first()
    if db_dest:
        db_dest.destination_code = dest_update.destination_code
        db_dest.description = dest_update.description
        db.commit()
        db.refresh(db_dest)
    return db_dest

def delete_sku_destination(db: Session, dest_id: int) -> Optional[models.SkuDestination]:
    db_dest = db.query(models.SkuDestination).filter(models.SkuDestination.id == dest_id).first()
    if db_dest:
        db.delete(db_dest)
        db.commit()
    return db_dest

# SkuPhase CRUD
def get_sku_phases(db: Session, skip: int = 0, limit: int = 100) -> List[models.SkuPhase]:
    return db.query(models.SkuPhase).offset(skip).limit(limit).all()

def create_sku_phase(db: Session, phase: schemas.SkuPhaseCreate) -> models.SkuPhase:
    db_phase = models.SkuPhase(
        phase_id=phase.phase_id,
        phase_description=phase.phase_description
    )
    db.add(db_phase)
    db.commit()
    db.refresh(db_phase)
    return db_phase

def update_sku_phase(db: Session, phase_id: str, phase_update: schemas.SkuPhaseCreate) -> Optional[models.SkuPhase]:
    db_phase = db.query(models.SkuPhase).filter(models.SkuPhase.phase_id == phase_id).first()
    if db_phase:
        db_phase.phase_description = phase_update.phase_description
        db.commit()
        db.refresh(db_phase)
    return db_phase

def delete_sku_phase(db: Session, phase_id: str) -> Optional[models.SkuPhase]:
    db_phase = db.query(models.SkuPhase).filter(models.SkuPhase.phase_id == phase_id).first()
    if db_phase:
        db.delete(db_phase)
        db.commit()
    return db_phase

# SkuGroup CRUD
def get_sku_groups(db: Session, skip: int = 0, limit: int = 100) -> List[models.SkuGroup]:
    return db.query(models.SkuGroup).offset(skip).limit(limit).all()

def create_sku_group(db: Session, group: schemas.SkuGroupCreate) -> models.SkuGroup:
    db_group = models.SkuGroup(
        group_code=group.group_code,
        group_name=group.group_name,
        description=group.description,
        status=group.status
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def update_sku_group(db: Session, group_code: str, group_update: schemas.SkuGroupCreate) -> Optional[models.SkuGroup]:
    db_group = db.query(models.SkuGroup).filter(models.SkuGroup.group_code == group_code).first()
    if db_group:
        db_group.group_name = group_update.group_name
        db_group.description = group_update.description
        db_group.status = group_update.status
        db.commit()
        db.refresh(db_group)
    return db_group

def delete_sku_group(db: Session, group_code: str) -> Optional[models.SkuGroup]:
    db_group = db.query(models.SkuGroup).filter(models.SkuGroup.group_code == group_code).first()
    if db_group:
        db.delete(db_group)
        db.commit()
    return db_group
