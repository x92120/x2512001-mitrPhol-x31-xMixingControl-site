"""
SQLAlchemy ORM Models
=====================
All database tables and read-only views for the xMixing system.
"""
from sqlalchemy import (  # type: ignore[import-untyped]
    Column, Integer, String, Enum, TIMESTAMP, text, DateTime,
    JSON, Float, ForeignKey, Date, Boolean, func,
)
from sqlalchemy.orm import relationship  # type: ignore[import-untyped]
from database import Base  # type: ignore[import-untyped]
import enum


# ── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    Admin = "Admin"
    Manager = "Manager"
    Operator = "Operator"
    QC_Inspector = "QC Inspector"
    Viewer = "Viewer"

class UserStatus(str, enum.Enum):
    Active = "Active"
    Inactive = "Inactive"


# ── Core Tables ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(Enum(UserRole), default=UserRole.Operator)
    department = Column(String(100))
    status = Column(Enum(UserStatus), default=UserStatus.Active)
    permissions = Column(JSON)
    last_login = Column(DateTime)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True, index=True)
    blind_code = Column(String(50), index=True,unique=True,nullable=False)
    mat_sap_code = Column(String(50), index=True, nullable=False, unique=True)
    re_code = Column(String(50))
    name = Column(String(150), nullable=False)
    unit = Column(String(20), default="kg")
    Group = Column(String(50))
    std_package_size = Column(Float, default=1.0)
    warehouse = Column(String(50), default="")
    package_container_type = Column(String(50), default="Bag")
    status = Column(String(20), default="Active")
    creat_by = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    update_by = Column(String(50))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class IngredientIntakeFrom(Base):
    __tablename__ = "ingredient_intake_from"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class PackageContainerType(Base):
    __tablename__ = "package_container_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class PackageContainerSize(Base):
    __tablename__ = "package_container_sizes"
    id = Column(Integer, primary_key=True, index=True)
    size = Column(Float, nullable=False)
    container_type = Column(String(50), nullable=True, default="Bag")
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


# ── Ingredient Intake ────────────────────────────────────────────────────────

class IngredientIntakeList(Base):
    __tablename__ = "ingredient_intake_lists"
    intake_lot_id = Column(String(50), primary_key=True, index=True)
    lot_id = Column(String(50), nullable=False, default="")
    intake_from = Column(String(50))
    intake_to = Column(String(50))
    blind_code = Column(String(50), index=True)
    mat_sap_code = Column(String(50), nullable=False, index=True)
    re_code = Column(String(50))
    material_description = Column(String(200))
    uom = Column(String(20))
    intake_vol = Column(Float, nullable=False)
    remain_vol = Column(Float, nullable=False)
    intake_package_vol = Column(Float)
    package_intake = Column(Integer)
    expire_date = Column(DateTime)
    status = Column(String(20), default="Active")
    intake_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    intake_by = Column(String(50), nullable=False)
    edit_by = Column(String(50))
    edit_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
    po_number = Column(String(50))
    manufacturing_date = Column(DateTime)
    batch_prepare_vol = Column(Float)
    std_package_size = Column(Float, default=25.0)
    ext_date = Column(DateTime)
    reserv_no = Column(String(50))
    stock_zone = Column(String(50))
    material_type = Column(String(50))
    # Relationships
    history = relationship("IngredientIntakeHistory", back_populates="intake_record", cascade="all, delete-orphan")
    packages = relationship("IntakePackageReceive", back_populates="intake_record", cascade="all, delete-orphan")


class IngredientIntakeHistory(Base):
    __tablename__ = "ingredient_intake_history"
    id = Column(Integer, primary_key=True, index=True)
    intake_list_id = Column(String(50), ForeignKey("ingredient_intake_lists.intake_lot_id"), nullable=False)
    action = Column(String(50), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20))
    remarks = Column(String(255))
    changed_by = Column(String(50), nullable=False)
    changed_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    intake_record = relationship("IngredientIntakeList", back_populates="history")


class IntakePackageReceive(Base):
    __tablename__ = "intake_package_receive"
    id = Column(Integer, primary_key=True, index=True)
    intake_list_id = Column(String(50), ForeignKey("ingredient_intake_lists.intake_lot_id"), nullable=False)
    package_no = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    created_by = Column(String(50))
    intake_record = relationship("IngredientIntakeList", back_populates="packages")


# ── SKU / Recipe ─────────────────────────────────────────────────────────────

class SkuGroup(Base):
    __tablename__ = "sku_groups"
    id = Column(Integer, primary_key=True, index=True)
    group_code = Column(String(50), unique=True, nullable=False, index=True)
    group_name = Column(String(100), nullable=False)
    description = Column(String(255))
    status = Column(String(20), default="Active")
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class Sku(Base):
    __tablename__ = "sku_masters"
    id = Column(Integer, primary_key=True, index=True)
    sku_id = Column(String(50), unique=True, nullable=False, index=True)
    sku_name = Column(String(200), nullable=False)
    std_batch_size = Column(Float)
    uom = Column(String(20))
    status = Column(String(20), default="Active")
    sku_group = Column(Integer, ForeignKey("sku_groups.id"), nullable=True)
    creat_by = Column(String(50), nullable=False)
    update_by = Column(String(50))
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
    steps = relationship("SkuStep", back_populates="sku", foreign_keys="[SkuStep.sku_id]", primaryjoin="Sku.sku_id == SkuStep.sku_id")
    group = relationship("SkuGroup", foreign_keys=[sku_group])


class SkuStep(Base):
    __tablename__ = "sku_steps"
    id = Column(Integer, primary_key=True, index=True)
    sku_id = Column(String(50), ForeignKey("sku_masters.sku_id"), index=True, nullable=True)
    phase_number = Column(String(20), index=True, nullable=True)
    phase_id = Column(String(50), index=True, nullable=True)
    master_step = Column(Boolean, default=False)
    sub_step = Column(Integer, nullable=False)
    action = Column(String(100))
    re_code = Column(String(50))
    action_code = Column(String(50))
    setup_step = Column(String(100))
    destination = Column(String(100))
    require = Column(Float)
    uom = Column(String(20))
    low_tol = Column(Float)
    high_tol = Column(Float)
    step_condition = Column(String(100))
    agitator_rpm = Column(Float)
    high_shear_rpm = Column(Float)
    temperature = Column(Float)
    temp_low = Column(Float)
    temp_high = Column(Float)
    step_time = Column(Integer)
    step_timer_control = Column(Integer)
    qc_temp = Column(Boolean, default=False)
    record_steam_pressure = Column(Boolean, default=False)
    record_ctw = Column(Boolean, default=False)
    operation_brix_record = Column(Boolean, default=False)
    operation_ph_record = Column(Boolean, default=False)
    brix_sp = Column(String(50))
    ph_sp = Column(String(50))
    action_description = Column(String(200))
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
    sku = relationship("Sku", back_populates="steps", foreign_keys=[sku_id], primaryjoin="Sku.sku_id == SkuStep.sku_id")


class SkuAction(Base):
    __tablename__ = "sku_actions"
    action_code = Column(String(50), primary_key=True)
    action_description = Column(String(200), nullable=False)
    component_filter = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class SkuPhase(Base):
    __tablename__ = "sku_phases"
    phase_id = Column(Integer, primary_key=True)
    phase_code = Column(String(50), nullable=True)
    phase_description = Column(String(200), nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class SkuDestination(Base):
    __tablename__ = "sku_destinations"
    id = Column(Integer, primary_key=True, index=True)
    destination_code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(200))


# ── Production ───────────────────────────────────────────────────────────────

class ProductionPlanHistory(Base):
    __tablename__ = "production_plan_history"
    id = Column(Integer, primary_key=True, index=True)
    plan_db_id = Column(Integer, ForeignKey("production_plans.id"), nullable=False)
    action = Column(String(50), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20))
    remarks = Column(String(255))
    changed_by = Column(String(50), nullable=False)
    changed_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    plan = relationship("ProductionPlan", backref="history")


class ProductionPlan(Base):
    __tablename__ = "production_plans"
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(50), unique=True, nullable=False, index=True)
    sku_id = Column(String(50), nullable=False)
    sku_name = Column(String(200))
    plant = Column(String(50))
    total_volume = Column(Float)
    total_plan_volume = Column(Float)
    batch_size = Column(Float)
    num_batches = Column(Integer)
    start_date = Column(Date)
    finish_date = Column(Date)
    status = Column(String(20), default="Planned")
    # Status flags
    flavour_house = Column(Boolean, default=False)
    spp = Column(Boolean, default=False)
    batch_prepare = Column(Boolean, default=False)
    ready_to_product = Column(Boolean, default=False)
    production = Column(Boolean, default=False)
    done = Column(Boolean, default=False)
    created_by = Column(String(50))
    updated_by = Column(String(50))
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
    batches = relationship("ProductionBatch", back_populates="plan", cascade="all, delete-orphan")


class ProductionBatch(Base):
    __tablename__ = "production_batches"
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("production_plans.id"), nullable=False)
    batch_id = Column(String(100), unique=True, nullable=False, index=True)
    sku_id = Column(String(50), nullable=False)
    plant = Column(String(50))
    batch_size = Column(Float)
    status = Column(String(50), default="Created")
    flavour_house = Column(Boolean, default=False)
    spp = Column(Boolean, default=False)
    batch_prepare = Column(Boolean, default=False)
    ready_to_product = Column(Boolean, default=False)
    production = Column(Boolean, default=False)
    done = Column(Boolean, default=False)
    # Packing & Delivery tracking
    fh_boxed_at = Column(TIMESTAMP, nullable=True)       # When FH box was closed
    spp_boxed_at = Column(TIMESTAMP, nullable=True)      # When SPP box was closed
    fh_delivered_at = Column(TIMESTAMP, nullable=True)    # FH delivered to SPP
    fh_delivered_by = Column(String(50), nullable=True)
    spp_delivered_at = Column(TIMESTAMP, nullable=True)   # SPP delivered to Production Hall
    spp_delivered_by = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
    plan = relationship("ProductionPlan", back_populates="batches")


# ── PreBatch (Legacy — kept for backward compat) ─────────────────────────────

class PreBatchReq(Base):
    __tablename__ = "prebatch_reqs"
    id = Column(Integer, primary_key=True, index=True)
    batch_db_id = Column(Integer, ForeignKey("production_batches.id"), nullable=False)
    plan_id = Column(String(50), index=True)
    batch_id = Column(String(100), index=True)
    re_code = Column(String(50), index=True)
    ingredient_name = Column(String(200))
    required_volume = Column(Float)
    wh = Column(String(50))
    status = Column(Integer, default=0)  # 0=Pending, 1=In-Progress, 2=Completed
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
    batch = relationship("ProductionBatch", backref="reqs")


class PreBatchRec(Base):
    __tablename__ = "prebatch_recs"
    id = Column(Integer, primary_key=True, index=True)
    req_id = Column(Integer, ForeignKey("prebatch_reqs.id"), nullable=True)
    batch_record_id = Column(String(100), unique=True, nullable=False, index=True)
    plan_id = Column(String(50), index=True)
    re_code = Column(String(50), index=True)
    package_no = Column(Integer)
    total_packages = Column(Integer)
    net_volume = Column(Float)
    total_volume = Column(Float)
    total_request_volume = Column(Float)
    intake_lot_id = Column(String(50), index=True, nullable=True)
    mat_sap_code = Column(String(50), index=True)
    prebatch_id = Column(String(100), index=True)
    recode_batch_id = Column(String(50), index=True)
    recheck_status = Column(Integer, default=0)   # 0=Pending, 1=OK, 2=Error
    recheck_at = Column(TIMESTAMP, nullable=True)
    recheck_by = Column(String(50), nullable=True)
    packing_status = Column(Integer, default=0)    # 0=Unpacked, 1=Packed
    packed_at = Column(TIMESTAMP, nullable=True)
    packed_by = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    req = relationship("PreBatchReq", backref="recs")
    origins = relationship("PreBatchRecFrom", back_populates="prebatch_rec", cascade="all, delete-orphan")


# ── PreBatch Unified (NEW — replaces reqs + recs) ────────────────────────────

class PreBatchItem(Base):
    """Unified prebatch table: one row per batch×ingredient.
    Packing fields are NULL until the operator weighs on the scale."""
    __tablename__ = "prebatch_items"
    id = Column(Integer, primary_key=True, index=True)
    # Requirement fields (filled at plan creation)
    batch_db_id = Column(Integer, ForeignKey("production_batches.id"), nullable=False)
    plan_id = Column(String(50), index=True)
    batch_id = Column(String(100), index=True)
    re_code = Column(String(50), index=True)
    ingredient_name = Column(String(200))
    required_volume = Column(Float)
    wh = Column(String(50), default="Mix")
    status = Column(Integer, default=0)  # 0=Wait, 1=Prepare, 2=preBatch_ok
    # Packing fields (filled when operator weighs — NULL until then)
    batch_record_id = Column(String(100), index=True)
    net_volume = Column(Float)
    package_no = Column(Integer, default=1)
    total_packages = Column(Integer, default=1)
    intake_lot_id = Column(String(50), index=True)
    mat_sap_code = Column(String(50), index=True)
    prebatch_id = Column(String(100))
    recode_batch_id = Column(String(50))
    total_volume = Column(Float)
    total_request_volume = Column(Float)
    # QC Recheck
    recheck_status = Column(Integer, default=0)   # 0=Pending, 1=OK, 2=Error
    recheck_at = Column(TIMESTAMP, nullable=True)
    recheck_by = Column(String(100), nullable=True)
    # Box Packing
    packing_status = Column(Integer, default=0)    # 0=Open, 1=Packed
    packed_at = Column(TIMESTAMP, nullable=True)
    packed_by = Column(String(50), nullable=True)
    # Timestamps
    weighed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
    # Relationships
    batch = relationship("ProductionBatch", backref="items")
    origins = relationship("PreBatchItemFrom", back_populates="prebatch_item", cascade="all, delete-orphan")


class PreBatchItemFrom(Base):
    """Multi-lot origins for a prebatch item (which raw material lots were used)."""
    __tablename__ = "prebatch_item_from"
    id = Column(Integer, primary_key=True, index=True)
    prebatch_item_id = Column(Integer, ForeignKey("prebatch_items.id"), nullable=False, index=True)
    intake_lot_id = Column(String(50), nullable=False, index=True)
    mat_sap_code = Column(String(50), index=True)
    take_volume = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    prebatch_item = relationship("PreBatchItem", back_populates="origins")


# Legacy origin table (kept for backward compat)
class PreBatchRecFrom(Base):
    __tablename__ = "prebatch_rec_from"
    id = Column(Integer, primary_key=True, index=True)
    prebatch_rec_id = Column(Integer, ForeignKey("prebatch_recs.id"), nullable=False, index=True)
    intake_lot_id = Column(String(50), nullable=False, index=True)
    mat_sap_code = Column(String(50), index=True)
    take_volume = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    prebatch_rec = relationship("PreBatchRec", back_populates="origins")


# ── Reference Tables ─────────────────────────────────────────────────────────

class Plant(Base):
    __tablename__ = "plants"
    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(String(50), unique=True, nullable=False, index=True)
    plant_name = Column(String(100), nullable=False)
    plant_capacity = Column(Float, default=0)
    plant_description = Column(String(255))
    status = Column(String(20), default="Active")
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class Warehouse(Base):
    __tablename__ = "warehouses"
    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    status = Column(String(20), default="Active")
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())

# ── Stock Adjustment ─────────────────────────────────────────────────────────

class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"
    id = Column(Integer, primary_key=True, index=True)
    intake_lot_id = Column(String(50), nullable=False, index=True)
    mat_sap_code = Column(String(50), index=True)
    re_code = Column(String(50), index=True)
    material_description = Column(String(200))
    adjust_type = Column(String(20), nullable=False)   # 'increase' or 'decrease'
    adjust_reason = Column(String(50), nullable=False)
    adjust_qty = Column(Float, nullable=False)
    prev_remain_vol = Column(Float, nullable=False)
    new_remain_vol = Column(Float, nullable=False)
    remark = Column(String(255))
    adjusted_by = Column(String(50), nullable=False)
    adjusted_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


# ── Database Views (Read-Only) ───────────────────────────────────────────────

class VSkuMasterDetail(Base):
    """v_sku_master_detail — SKU master with step counts"""
    __tablename__ = "v_sku_master_detail"
    __table_args__ = {'info': {'is_view': True}}
    id = Column(Integer, primary_key=True)
    sku_id = Column(String(50))
    sku_name = Column(String(200))
    std_batch_size = Column(Float)
    uom = Column(String(20))
    status = Column(String(20))
    creat_by = Column(String(50))
    created_at = Column(TIMESTAMP)
    update_by = Column(String(50))
    updated_at = Column(TIMESTAMP)
    total_phases = Column(Integer)
    total_sub_steps = Column(Integer)
    last_step_update = Column(TIMESTAMP)
    sku_group = Column(Integer)
    sku_group_code = Column(String(50))
    sku_group_name = Column(String(100))


class VSkuStepDetail(Base):
    """v_sku_step_detail — SKU steps with lookups and computed fields"""
    __tablename__ = "v_sku_step_detail"
    __table_args__ = {'info': {'is_view': True}}
    step_id = Column("step_id", Integer, primary_key=True)
    sku_id = Column(String(50))
    phase_number = Column(String(20))
    phase_id = Column(String(50))
    sub_step = Column(Integer)
    action = Column(String(100))
    re_code = Column(String(50))
    action_code = Column(String(50))
    setup_step = Column(String(100))
    destination = Column(String(100))
    require = Column(Float)
    uom = Column(String(20))
    low_tol = Column(Float)
    high_tol = Column(Float)
    step_condition = Column(String(100))
    agitator_rpm = Column(Float)
    high_shear_rpm = Column(Float)
    temperature = Column(Float)
    temp_low = Column(Float)
    temp_high = Column(Float)
    step_time = Column(Integer)
    step_timer_control = Column(Integer)
    ph = Column(Float, nullable=True)
    brix = Column(Float, nullable=True)
    qc_temp = Column(Boolean)
    record_steam_pressure = Column(Boolean)
    record_ctw = Column(Boolean)
    operation_brix_record = Column(Boolean)
    operation_ph_record = Column(Boolean)
    brix_sp = Column(String(50))
    ph_sp = Column(String(50))
    step_created_at = Column(TIMESTAMP)
    step_updated_at = Column(TIMESTAMP)
    # SKU master info
    sku_name = Column(String(200))
    std_batch_size = Column(Float)
    uom_master = Column(String(20))
    sku_status = Column(String(20))
    # Lookups
    action_description = Column(String(200))
    destination_description = Column(String(200))
    ingredient_name = Column(String(200))
    mat_sap_code = Column(String(50))
    blind_code = Column(String(50))
    ingredient_category = Column(String(100))
    ingredient_unit = Column(String(20))
    std_package_size = Column(Float)
    # Computed
    step_label = Column(String(20))
    full_action_description = Column(String(300))
    full_destination_description = Column(String(300))


class VSkuComplete(Base):
    """v_sku_complete — Denormalized SKU data for export/reporting"""
    __tablename__ = "v_sku_complete"
    __table_args__ = {'info': {'is_view': True}}
    sku_id = Column(String(50), primary_key=True)
    step_number = Column(String(20), primary_key=True)
    sku_name = Column(String(200))
    std_batch_size = Column(Float)
    uom = Column(String(20))
    status = Column(String(20))
    phase_number = Column(String(20))
    phase_id = Column(String(50))
    sub_step = Column(Integer)
    action = Column(String(100))
    action_code = Column(String(50))
    action_description = Column(String(200))
    re_code = Column(String(50))
    ingredient_name = Column(String(200))
    mat_sap_code = Column(String(50))
    blind_code = Column(String(50))
    destination = Column(String(100))
    destination_description = Column(String(200))
    required_amount = Column(Float)
    low_tol = Column(Float)
    high_tol = Column(Float)
    agitator_rpm = Column(Float)
    high_shear_rpm = Column(Float)
    temperature = Column(Float)
    step_time = Column(Integer)
    setup_step = Column(String(100))
    creat_by = Column(String(50))
    created_at = Column(TIMESTAMP)
    update_by = Column(String(50))
    updated_at = Column(TIMESTAMP)
