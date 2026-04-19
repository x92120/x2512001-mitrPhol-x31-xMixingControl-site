from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional, List
from datetime import date
import models
import schemas

# Ingredient CRUD
def get_ingredient_by_id(db: Session, ingredient_db_id: int) -> Optional[models.Ingredient]:
    """Get ingredient by DB ID"""
    return db.query(models.Ingredient).filter(models.Ingredient.id == ingredient_db_id).first()

def get_ingredient_by_mat_sap_code(db: Session, mat_sap_code: str) -> Optional[models.Ingredient]:
    """Get ingredient by mat_sap_code"""
    return db.query(models.Ingredient).filter(models.Ingredient.mat_sap_code == mat_sap_code).first()

def search_ingredient(db: Session, query: str) -> Optional[models.Ingredient]:
    """Search ingredient by ID or blind code"""
    # Try by mat_sap_code
    ingredient = db.query(models.Ingredient).filter(models.Ingredient.mat_sap_code == query).first()
    if ingredient:
        return ingredient
    # Try by re_code
    ingredient = db.query(models.Ingredient).filter(models.Ingredient.re_code == query).first()
    if ingredient:
        return ingredient
    # Try by name (case-insensitive substring)
    ingredient = db.query(models.Ingredient).filter(models.Ingredient.name.ilike(f"%{query}%")).first()
    if ingredient:
        return ingredient
    # Try by blind_code
    return db.query(models.Ingredient).filter(models.Ingredient.blind_code == query).first()

def get_ingredients(db: Session, skip: int = 0, limit: int = 100) -> List[models.Ingredient]:
    """Get list of ingredients with pagination"""
    return db.query(models.Ingredient).offset(skip).limit(limit).all()

def create_ingredient(db: Session, ingredient: schemas.IngredientCreate) -> models.Ingredient:
    """Create new ingredient with error handling"""
    try:
        db_ingredient = models.Ingredient(**ingredient.dict())
        db.add(db_ingredient)
        db.commit()
        db.refresh(db_ingredient)
        return db_ingredient
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def update_ingredient(db: Session, ingredient_id: int, ingredient: schemas.IngredientCreate) -> Optional[models.Ingredient]:
    """Update ingredient by ID"""
    try:
        db_ingredient = db.query(models.Ingredient).filter(models.Ingredient.id == ingredient_id).first()
        if not db_ingredient:
            return None
        
        update_data = ingredient.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_ingredient, key, value)
            
        db.commit()
        db.refresh(db_ingredient)
        return db_ingredient
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def delete_ingredient(db: Session, ingredient_id: int) -> Optional[models.Ingredient]:
    """Delete ingredient by ID"""
    try:
        db_ingredient = db.query(models.Ingredient).filter(models.Ingredient.id == ingredient_id).first()
        if db_ingredient:
            db.delete(db_ingredient)
            db.commit()
        return db_ingredient
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

# Ingredient Intake From CRUD
def get_intake_from_all(db: Session) -> List[models.IngredientIntakeFrom]:
    """Get all intake from locations"""
    return db.query(models.IngredientIntakeFrom).order_by(models.IngredientIntakeFrom.name).all()

def create_intake_from(db: Session, data: schemas.IngredientIntakeFromCreate) -> models.IngredientIntakeFrom:
    """Create new intake from location"""
    db_obj = models.IngredientIntakeFrom(**data.dict())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update_intake_from(db: Session, intake_from_id: int, data: schemas.IngredientIntakeFromCreate) -> Optional[models.IngredientIntakeFrom]:
    """Update intake from location"""
    db_obj = db.query(models.IngredientIntakeFrom).filter(models.IngredientIntakeFrom.id == intake_from_id).first()
    if db_obj:
        db_obj.name = data.name
        db.commit()
        db.refresh(db_obj)
    return db_obj

def delete_intake_from(db: Session, intake_from_id: int) -> bool:
    """Delete intake from location"""
    db_obj = db.query(models.IngredientIntakeFrom).filter(models.IngredientIntakeFrom.id == intake_from_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
        return True
    return False

# Package Container Type CRUD
def get_container_types(db: Session) -> List[models.PackageContainerType]:
    """Get all package container types"""
    return db.query(models.PackageContainerType).order_by(models.PackageContainerType.name).all()

def create_container_type(db: Session, data: schemas.PackageContainerTypeCreate) -> models.PackageContainerType:
    """Create new package container type"""
    db_obj = models.PackageContainerType(**data.dict())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update_container_type(db: Session, type_id: int, data: schemas.PackageContainerTypeCreate) -> Optional[models.PackageContainerType]:
    """Update package container type"""
    db_obj = db.query(models.PackageContainerType).filter(models.PackageContainerType.id == type_id).first()
    if db_obj:
        db_obj.name = data.name
        db.commit()
        db.refresh(db_obj)
    return db_obj

def delete_container_type(db: Session, type_id: int) -> bool:
    """Delete package container type"""
    db_obj = db.query(models.PackageContainerType).filter(models.PackageContainerType.id == type_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
        return True
    return False

# Package Container Size CRUD
def get_container_sizes(db: Session, container_type: Optional[str] = None) -> List[models.PackageContainerSize]:
    """Get all package container sizes"""
    query = db.query(models.PackageContainerSize)
    if container_type:
        query = query.filter(models.PackageContainerSize.container_type == container_type)
    return query.order_by(models.PackageContainerSize.size).all()

def create_container_size(db: Session, data: schemas.PackageContainerSizeCreate) -> models.PackageContainerSize:
    """Create new package container size"""
    db_obj = models.PackageContainerSize(**data.dict())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update_container_size(db: Session, size_id: int, data: schemas.PackageContainerSizeCreate) -> Optional[models.PackageContainerSize]:
    """Update package container size"""
    db_obj = db.query(models.PackageContainerSize).filter(models.PackageContainerSize.id == size_id).first()
    if db_obj:
        db_obj.size = data.size
        db_obj.container_type = data.container_type
        db.commit()
        db.refresh(db_obj)
    return db_obj

def delete_container_size(db: Session, size_id: int) -> bool:
    """Delete package container size"""
    db_obj = db.query(models.PackageContainerSize).filter(models.PackageContainerSize.id == size_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
        return True
    return False

# Ingredient Intake List CRUD
def get_ingredient_intake_lists(db: Session, skip: int = 0, limit: int = 100) -> List[models.IngredientIntakeList]:
    """Get list of ingredient intake list with pagination"""
    return db.query(models.IngredientIntakeList)\
        .options(joinedload(models.IngredientIntakeList.history), joinedload(models.IngredientIntakeList.packages))\
        .order_by(models.IngredientIntakeList.intake_at.desc())\
        .offset(skip).limit(limit).all()

def get_ingredient_intake_list(db: Session, list_id: str) -> Optional[models.IngredientIntakeList]:
    """Get ingredient intake list by ID"""
    return db.query(models.IngredientIntakeList)\
        .options(joinedload(models.IngredientIntakeList.history), joinedload(models.IngredientIntakeList.packages))\
        .filter(models.IngredientIntakeList.intake_lot_id == list_id).first()

def create_ingredient_intake_list(db: Session, list_data: schemas.IngredientIntakeListCreate) -> models.IngredientIntakeList:
    """Create new ingredient intake list with error handling and individual package generation"""
    try:
        # Convert schema to dict
        data = list_data.dict()
        
        # Look up ingredient master to fill in missing fields
        ing_master = get_ingredient_by_mat_sap_code(db, mat_sap_code=data.get('mat_sap_code'))
        if ing_master:
            if not data.get('re_code'):
                data['re_code'] = ing_master.re_code
            if not data.get('material_description'):
                data['material_description'] = ing_master.name
            if not data.get('uom'):
                data['uom'] = ing_master.unit

        db_list = models.IngredientIntakeList(**data)
        db.add(db_list)
        db.commit()
        db.refresh(db_list)

        # Log initial creation history
        db_history = models.IngredientIntakeHistory(
            intake_list_id=db_list.intake_lot_id,
            action="Created",
            new_status=db_list.status,
            changed_by=db_list.intake_by,
            remarks="Initial record creation"
        )
        db.add(db_history)
        
        # Create individual package records if package info is provided
        if db_list.intake_package_vol and db_list.package_intake and db_list.package_intake > 0:
            total_vol = db_list.intake_vol
            std_pkg_vol = db_list.intake_package_vol
            num_pkgs = db_list.package_intake
            
            for i in range(1, num_pkgs + 1):
                if i == num_pkgs:
                    # Last package gets the residual weight
                    pkg_weight = round(total_vol - (std_pkg_vol * (num_pkgs - 1)), 4)
                else:
                    pkg_weight = std_pkg_vol
                
                db_package = models.IntakePackageReceive(
                    intake_list_id=db_list.intake_lot_id,
                    package_no=i,
                    weight=pkg_weight,
                    created_by=db_list.intake_by
                )
                db.add(db_package)
        
        db.commit()
        db.refresh(db_list)
        return db_list
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def update_ingredient_intake_list(db: Session, list_id: str, list_update: schemas.IngredientIntakeListCreate) -> Optional[models.IngredientIntakeList]:
    """Update ingredient intake list"""
    try:
        db_list = db.query(models.IngredientIntakeList).filter(models.IngredientIntakeList.intake_lot_id == list_id).first()
        if db_list:
            old_status = db_list.status
            update_data = list_update.dict(exclude_unset=True)
            
            # Check for significant changes to log
            new_status = update_data.get('status')
            
            for key, value in update_data.items():
                setattr(db_list, key, value)
            
            db.commit()
            db.refresh(db_list)

            # Log history if status changed or just a general update
            action = "Status Change" if new_status and new_status != old_status else "Modified"
            db_history = models.IngredientIntakeHistory(
                intake_list_id=db_list.intake_lot_id,
                action=action,
                old_status=old_status,
                new_status=db_list.status,
                changed_by=db_list.edit_by or "system",
                remarks=f"Record updated via API"
            )
            db.add(db_history)
            db.commit()

        return db_list
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def delete_ingredient_intake_list(db: Session, list_id: str) -> Optional[models.IngredientIntakeList]:
    """Delete ingredient intake list with error handling"""
    try:
        db_list = db.query(models.IngredientIntakeList).filter(models.IngredientIntakeList.intake_lot_id == list_id).first()
        if db_list:
            db.delete(db_list)
            db.commit()
        return db_list
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Database error: {str(e)}")

def get_next_intake_id(db: Session) -> str:
    """Generate next intake ID: intake-yyyy-mm-dd-nnn"""
    today_str = date.today().strftime("%Y-%m-%d")
    pattern = f"intake-{today_str}-%"
    
    # Count existing for today or find max
    # We use len() of query to simple count since we renamed table
    # Optimally we would parse the max number, but count+1 is usually fine if no deletes
    # To be robust against deletes, let's try to find max
    
    # This query might be slow if huge data, but fine for now.
    last_record = db.query(models.IngredientIntakeList)\
        .filter(models.IngredientIntakeList.intake_lot_id.like(pattern))\
        .order_by(models.IngredientIntakeList.intake_lot_id.desc())\
        .first()
        
    if last_record:
        try:
            # Extract last 3 digits
            last_num = int(last_record.intake_lot_id.split('-')[-1])
            new_num = last_num + 1
        except:
            new_num = 1
    else:
        new_num = 1
        
    return f"intake-{today_str}-{new_num:03d}"
