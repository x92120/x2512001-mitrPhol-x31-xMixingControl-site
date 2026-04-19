from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, date

class LoginRequest(BaseModel):
    """Login request with validation"""
    username_or_email: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)

class UserBase(BaseModel):
    """Base user model"""
    username: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    role: str = Field("Operator", max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    status: str = Field("Active", max_length=20)
    permissions: List[str] = []

class UserCreate(UserBase):
    """User creation with password validation"""
    password: str = Field(..., min_length=6, max_length=255)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Ensure password has minimum complexity (optional for now)"""
        # Relaxed validation - just ensure minimum length
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class UserUpdate(BaseModel):
    """User update model"""
    full_name: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, max_length=50)
    password: Optional[str] = Field(None, min_length=6, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=20)
    permissions: Optional[List[str]] = None
    username: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None

class User(UserBase):
    """User response model"""
    id: int
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class IngredientIntakeFromBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class IngredientIntakeFromCreate(IngredientIntakeFromBase):
    pass

class IngredientIntakeFrom(IngredientIntakeFromBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Package Container Type Schemas
class PackageContainerTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

class PackageContainerTypeCreate(PackageContainerTypeBase):
    pass

class PackageContainerType(PackageContainerTypeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Package Container Size Schemas
class PackageContainerSizeBase(BaseModel):
    size: float = Field(..., gt=0)
    container_type: Optional[str] = Field("Bag", max_length=50)

class PackageContainerSizeCreate(PackageContainerSizeBase):
    pass

class PackageContainerSize(PackageContainerSizeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Ingredient Schemas
class IngredientBase(BaseModel):
    """Base ingredient model"""
    blind_code: Optional[str] = Field(None, max_length=50)
    mat_sap_code: str = Field(..., min_length=1, max_length=50)
    re_code: Optional[str] = Field(None, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    std_package_size: Optional[float] = Field(25.0, ge=0)
    unit: str = Field("kg", max_length=20)
    Group: Optional[str] = Field(None, max_length=50)
    warehouse: Optional[str] = Field(None, max_length=50)
    package_container_type: Optional[str] = Field("Bag", max_length=50)
    status: str = Field("Active", max_length=20)
    creat_by: str = Field(..., min_length=1, max_length=50)
    update_by: Optional[str] = Field(None, max_length=50)

class IngredientCreate(IngredientBase):
    """Ingredient creation model"""
    pass

class Ingredient(IngredientBase):
    """Ingredient response model"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Ingredient Intake List Schemas
class IngredientIntakeListBase(BaseModel):
    """Base ingredient intake list model (merged with Receipt)"""
    intake_lot_id: str = Field(..., min_length=1, max_length=50)
    intake_from: Optional[str] = Field(None, max_length=50) # Renamed from warehouse_location
    intake_to: Optional[str] = Field(None, max_length=50) # Destination warehouse
    blind_code: Optional[str] = Field(None, max_length=50)
    mat_sap_code: str = Field(..., min_length=1, max_length=50)
    re_code: Optional[str] = Field(None, max_length=50)
    material_description: Optional[str] = Field(None, max_length=200) # Merged
    uom: Optional[str] = Field(None, max_length=20) # Merged
    intake_vol: float = Field(...)
    remain_vol: float = Field(...)
    intake_package_vol: Optional[float] = Field(None)
    package_intake: Optional[int] = Field(None)
    expire_date: Optional[datetime] = None
    status: str = Field("Active", max_length=20)
    intake_by: str = Field(..., min_length=1, max_length=50)
    edit_by: Optional[str] = Field(None, max_length=50)
    po_number: Optional[str] = Field(None, max_length=50)
    manufacturing_date: Optional[datetime] = None
    batch_prepare_vol: Optional[float] = None # Merged
    std_package_size: Optional[float] = Field(25.0, ge=0) # Merged
    ext_date: Optional[datetime] = None
    reserv_no: Optional[str] = Field(None, max_length=50)
    stock_zone: Optional[str] = Field(None, max_length=50)
    material_type: Optional[str] = Field(None, max_length=50)

class IngredientIntakeListCreate(IngredientIntakeListBase):
    """Ingredient intake list creation model"""
    pass

# Ingredient Intake History Schemas
class IngredientIntakeHistoryBase(BaseModel):
    action: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    remarks: Optional[str] = None
    changed_by: str

class IngredientIntakeHistoryCreate(IngredientIntakeHistoryBase):
    intake_list_id: str

class IngredientIntakeHistory(IngredientIntakeHistoryBase):
    id: int
    intake_list_id: str
    changed_at: datetime

    class Config:
        from_attributes = True

# Intake Package Receive Schemas
class IntakePackageReceiveBase(BaseModel):
    package_no: int
    weight: float
    created_by: Optional[str] = None

class IntakePackageReceiveCreate(IntakePackageReceiveBase):
    intake_list_id: str

class IntakePackageReceive(IntakePackageReceiveBase):
    id: int
    intake_list_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class IngredientIntakeList(IngredientIntakeListBase):
    """Ingredient intake list response model"""
    intake_at: datetime
    edit_at: Optional[datetime] = None
    history: List[IngredientIntakeHistory] = []
    packages: List[IntakePackageReceive] = []

    class Config:
        from_attributes = True


# SkuStep Schemas
class SkuStepBase(BaseModel):
    sku_id: Optional[str] = None
    phase_number: str # Now required
    phase_id: Optional[str] = None
    master_step: Optional[bool] = False
    sub_step: int
    action: Optional[str] = None
    re_code: Optional[str] = None
    action_code: Optional[str] = None
    setup_step: Optional[str] = None
    destination: Optional[str] = None
    require: Optional[float] = 0.0
    uom: Optional[str] = None
    low_tol: Optional[float] = 0.0
    high_tol: Optional[float] = 0.0
    step_condition: Optional[str] = None
    
    agitator_rpm: Optional[float] = 0.0
    high_shear_rpm: Optional[float] = 0.0
    temperature: Optional[float] = 0.0
    temp_low: Optional[float] = 0.0
    temp_high: Optional[float] = 0.0
    
    step_time: Optional[int] = 0
    step_timer_control: Optional[int] = 0
    
    qc_temp: Optional[bool] = False
    record_steam_pressure: Optional[bool] = False
    record_ctw: Optional[bool] = False
    operation_brix_record: Optional[bool] = False
    operation_ph_record: Optional[bool] = False
    
    brix_sp: Optional[str] = None
    ph_sp: Optional[str] = None
    
    action_description: Optional[str] = None

class SkuStepCreate(SkuStepBase):
    pass

class SkuStep(SkuStepBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Sku Schemas
class SkuBase(BaseModel):
    sku_id: str = Field(..., max_length=50)
    sku_name: str = Field(..., max_length=200)
    std_batch_size: Optional[float] = None
    uom: Optional[str] = Field(None, max_length=20)
    sku_group: Optional[int] = None
    status: str = Field("Active", max_length=20)
    creat_by: str = Field("system", max_length=50)
    update_by: Optional[str] = Field(None, max_length=50)

class SkuCreate(SkuBase):
    # Optional steps during creation, or can be added later
    steps: List[SkuStepCreate] = []

class Sku(SkuBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    steps: List[SkuStep] = []

    class Config:
        from_attributes = True

class SkuDuplicate(BaseModel):
    source_sku_id: str
    new_sku_id: str
    new_sku_name: str
    creat_by: str = "system"

# PreBatch Req Schemas
class PreBatchReqBase(BaseModel):
    batch_db_id: int
    plan_id: str
    batch_id: str
    re_code: str
    ingredient_name: Optional[str] = None
    required_volume: float
    wh: Optional[str] = None
    status: int = 0

class PreBatchReqCreate(PreBatchReqBase):
    pass

class PreBatchRecSummary(BaseModel):
    """Lightweight rec for nesting inside PreBatchReq"""
    id: int
    batch_record_id: str
    package_no: Optional[int] = None
    total_packages: Optional[int] = None
    net_volume: Optional[float] = None
    packing_status: Optional[int] = 0

    class Config:
        from_attributes = True

class PreBatchReq(PreBatchReqBase):
    id: int
    total_packaged: Optional[float] = 0.0
    created_at: datetime
    updated_at: Optional[datetime] = None
    recs: List[PreBatchRecSummary] = []

    class Config:
        from_attributes = True

# PreBatch Record Schemas
class PreBatchRecBase(BaseModel):
    req_id: Optional[int] = None
    batch_record_id: str = Field(..., max_length=100)
    plan_id: Optional[str] = Field(None, max_length=50)
    re_code: Optional[str] = Field(None, max_length=50)
    package_no: Optional[int] = None
    total_packages: Optional[int] = None
    net_volume: Optional[float] = None
    total_volume: Optional[float] = None
    total_request_volume: Optional[float] = None
    intake_lot_id: Optional[str] = Field(None, max_length=50)
    mat_sap_code: Optional[str] = Field(None, max_length=50)
    prebatch_id: Optional[str] = Field(None, max_length=100)
    recode_batch_id: Optional[str] = Field(None, max_length=50)
    
    # Re-check fields
    recheck_status: Optional[int] = 0
    recheck_at: Optional[datetime] = None
    recheck_by: Optional[str] = None

class PreBatchRecFromBase(BaseModel):
    intake_lot_id: str = Field(..., max_length=50)
    mat_sap_code: Optional[str] = Field(None, max_length=50)
    take_volume: float

class PreBatchRecFromCreate(PreBatchRecFromBase):
    pass

class PreBatchRecFrom(PreBatchRecFromBase):
    id: int
    prebatch_rec_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class PreBatchRecCreate(PreBatchRecBase):
    origins: Optional[List[PreBatchRecFromCreate]] = None

class PreBatchRec(PreBatchRecBase):
    id: int
    created_at: datetime
    wh: Optional[str] = None
    batch_id: Optional[str] = None
    packing_status: Optional[int] = 0
    packed_at: Optional[datetime] = None
    packed_by: Optional[str] = None
    origins: List[PreBatchRecFrom] = []
    
    class Config:
        from_attributes = True

# ── PreBatchItem Schemas (NEW unified table) ──────────────────────────────────

class PreBatchItemFromBase(BaseModel):
    intake_lot_id: str = Field(..., max_length=50)
    mat_sap_code: Optional[str] = Field(None, max_length=50)
    take_volume: float

class PreBatchItemFromCreate(PreBatchItemFromBase):
    pass

class PreBatchItemFrom(PreBatchItemFromBase):
    id: int
    prebatch_item_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class PreBatchItemBase(BaseModel):
    batch_db_id: int
    plan_id: Optional[str] = None
    batch_id: Optional[str] = None
    re_code: Optional[str] = None
    ingredient_name: Optional[str] = None
    required_volume: Optional[float] = None
    wh: Optional[str] = "Mix"
    status: int = 0

class PreBatchItemCreate(PreBatchItemBase):
    pass

class PreBatchItemPack(BaseModel):
    """Fields sent when operator packs (weighs) an item."""
    batch_record_id: str
    net_volume: float
    package_no: int = 1
    total_packages: int = 1
    new_required_volume: Optional[float] = None
    intake_lot_id: Optional[str] = None
    mat_sap_code: Optional[str] = None
    recode_batch_id: Optional[str] = None
    origins: Optional[List[PreBatchItemFromCreate]] = None

class PreBatchItem(PreBatchItemBase):
    id: int
    batch_record_id: Optional[str] = None
    net_volume: Optional[float] = None
    package_no: Optional[int] = 1
    total_packages: Optional[int] = 1
    intake_lot_id: Optional[str] = None
    mat_sap_code: Optional[str] = None
    prebatch_id: Optional[str] = None
    recode_batch_id: Optional[str] = None
    total_volume: Optional[float] = None
    total_request_volume: Optional[float] = None
    recheck_status: Optional[int] = 0
    recheck_at: Optional[datetime] = None
    recheck_by: Optional[str] = None
    packing_status: Optional[int] = 0
    packed_at: Optional[datetime] = None
    packed_by: Optional[str] = None
    weighed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    origins: List[PreBatchItemFrom] = []
    
    class Config:
        from_attributes = True

# Production Batch Schema
class ProductionBatchBase(BaseModel):
    batch_id: str
    sku_id: str
    plant: Optional[str] = None
    batch_size: Optional[float] = None
    status: str = "Created"
    # Status flags
    flavour_house: bool = False
    spp: bool = False
    batch_prepare: bool = False
    ready_to_product: bool = False
    production: bool = False
    done: bool = False
    # Packing & Delivery
    fh_boxed_at: Optional[datetime] = None
    spp_boxed_at: Optional[datetime] = None
    fh_delivered_at: Optional[datetime] = None
    fh_delivered_by: Optional[str] = None
    spp_delivered_at: Optional[datetime] = None
    spp_delivered_by: Optional[str] = None

class ProductionBatchCreate(ProductionBatchBase):
    plan_id: int

class ProductionBatchUpdate(BaseModel):
    batch_id: Optional[str] = None
    sku_id: Optional[str] = None
    plant: Optional[str] = None
    batch_size: Optional[float] = None
    status: Optional[str] = None
    flavour_house: Optional[bool] = None
    spp: Optional[bool] = None
    batch_prepare: Optional[bool] = None
    ready_to_product: Optional[bool] = None
    production: Optional[bool] = None
    done: Optional[bool] = None
    plan_id: Optional[int] = None
    fh_boxed_at: Optional[datetime] = None
    spp_boxed_at: Optional[datetime] = None
    fh_delivered_at: Optional[datetime] = None
    fh_delivered_by: Optional[str] = None
    spp_delivered_at: Optional[datetime] = None
    spp_delivered_by: Optional[str] = None

class ProductionBatch(ProductionBatchBase):
    id: int
    plan_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    reqs: List[PreBatchReq] = []

    class Config:
        from_attributes = True

class ProductionBatchSummary(ProductionBatchBase):
    """Lightweight batch for plans list — no reqs loaded."""
    id: int
    plan_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Production Plan Schema
class ProductionPlanBase(BaseModel):
    plan_id: Optional[str] = None
    sku_id: str
    sku_name: Optional[str] = None
    plant: Optional[str] = None
    total_volume: Optional[float] = None
    total_plan_volume: Optional[float] = None
    batch_size: Optional[float] = None
    num_batches: Optional[int] = None
    start_date: Optional[date] = None
    finish_date: Optional[date] = None
    status: str = "Planned"
    flavour_house: bool = False
    spp: bool = False
    batch_prepare: bool = False
    ready_to_product: bool = False
    production: bool = False
    done: bool = False

class ProductionPlanCreate(ProductionPlanBase):
    created_by: Optional[str] = None

class ProductionPlan(ProductionPlanBase):
    id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    batches: List[ProductionBatch] = []

    class Config:
        from_attributes = True

class ProductionPlanSummary(ProductionPlanBase):
    """Lightweight plan for list — batches without reqs."""
    id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    batches: List[ProductionBatchSummary] = []

    class Config:
        from_attributes = True

class ProductionPlanCancel(BaseModel):
    comment: Optional[str] = None
    changed_by: Optional[str] = None

# Packing & Delivery request models
class BoxCloseRequest(BaseModel):
    """Request to mark a warehouse box as closed/boxed."""
    wh: str  # 'FH' or 'SPP'
    operator: Optional[str] = None

class DeliveryRequest(BaseModel):
    """Request to mark a batch warehouse as delivered."""
    wh: str  # 'FH' (FH→SPP) or 'SPP' (SPP→Production Hall)
    delivered_by: Optional[str] = None

class BoxCancelRequest(BaseModel):
    """Request to cancel (revert) a closed packing box."""
    wh: str  # 'FH' or 'SPP'
    reason: str  # Reason for cancellation
    cancelled_by: Optional[str] = None

# Stock Adjustment Schemas
class StockAdjustmentCreate(BaseModel):
    intake_lot_id: str = Field(..., min_length=1, max_length=50)
    adjust_type: str = Field(..., pattern=r'^(increase|decrease)$')
    adjust_qty: float = Field(..., gt=0)
    adjust_reason: str = Field(..., min_length=1, max_length=50)
    remark: Optional[str] = Field(None, max_length=255)
    adjusted_by: str = Field(..., min_length=1, max_length=50)

class StockAdjustment(BaseModel):
    id: int
    intake_lot_id: str
    mat_sap_code: Optional[str] = None
    re_code: Optional[str] = None
    material_description: Optional[str] = None
    adjust_type: str
    adjust_reason: str
    adjust_qty: float
    prev_remain_vol: float
    new_remain_vol: float
    remark: Optional[str] = None
    adjusted_by: str
    adjusted_at: datetime

    class Config:
        from_attributes = True

class LotLookup(BaseModel):
    id: int
    intake_lot_id: str
    mat_sap_code: str
    re_code: Optional[str] = None
    material_description: Optional[str] = None
    remain_vol: float
    intake_vol: float
    status: str

    class Config:
        from_attributes = True

# SkuAction Schemas
class SkuActionBase(BaseModel):
    action_code: str = Field(..., max_length=50)
    action_description: str = Field(..., max_length=200)
    component_filter: Optional[str] = Field(None, max_length=255)

class SkuActionCreate(SkuActionBase):
    pass

class SkuAction(SkuActionBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# SkuDestination Schemas
class SkuDestinationBase(BaseModel):
    destination_code: str = Field(..., max_length=50)
    description: Optional[str] = None

class SkuDestinationCreate(SkuDestinationBase):
    pass

class SkuDestination(SkuDestinationBase):
    id: int

    class Config:
        from_attributes = True


# SkuPhase Schemas
class SkuPhaseBase(BaseModel):
    phase_id: int
    phase_code: Optional[str] = Field(None, max_length=50)
    phase_description: str = Field(..., max_length=200)

class SkuPhaseCreate(SkuPhaseBase):
    pass

class SkuPhase(SkuPhaseBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# SkuGroup Schemas
class SkuGroupBase(BaseModel):
    group_code: str = Field(..., max_length=50)
    group_name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field("Active", max_length=20)

class SkuGroupCreate(SkuGroupBase):
    pass

class SkuGroup(SkuGroupBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Plant Schemas
class PlantBase(BaseModel):
    plant_id: str = Field(..., max_length=50)
    plant_name: str = Field(..., max_length=100)
    plant_capacity: Optional[float] = Field(0, ge=0)
    plant_description: Optional[str] = Field(None, max_length=255)
    status: str = Field("Active", max_length=20)

class PlantCreate(PlantBase):
    pass

class PlantUpdate(BaseModel):
    plant_name: Optional[str] = Field(None, max_length=100)
    plant_capacity: Optional[float] = Field(None, ge=0)
    plant_description: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=20)

class Plant(PlantBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Warehouse Schemas
class WarehouseBase(BaseModel):
    warehouse_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    status: str = Field("Active", max_length=20)

class WarehouseCreate(WarehouseBase):
    pass

class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=20)

class Warehouse(WarehouseBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Server Status Schemas
class MemoryStatus(BaseModel):
    total: int
    available: int
    percent: float
    used: int

class DiskStatus(BaseModel):
    total: int
    used: int
    free: int
    percent: float

class NetworkStatus(BaseModel):
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int

class ServerStatus(BaseModel):
    cpu_percent: List[float]
    cpu_average: float
    cpu_count: int
    memory: MemoryStatus
    disk: DiskStatus
    network: NetworkStatus
    boot_time: float
    os: str
    python_version: str
    hostname: str
    local_ip: str
    cpu_model: str
    architecture: str

class HostInfo(BaseModel):
    hostname: str
    ip_addresses: List[str]
    os_name: str
    os_version: str
    kernel: str
    architecture: str
    cpu_model: str
    total_ram: str
    username: str
    uptime: str
    boot_time_iso: str

class ConnectedDevice(BaseModel):
    name: str
    type: str  # 'usb', 'network', 'serial'
    status: str  # 'connected', 'active'
    details: str
    icon: str  # icon name for frontend

class ConnectedDevices(BaseModel):
    usb_devices: List[ConnectedDevice]
    network_devices: List[ConnectedDevice]
    serial_devices: List[ConnectedDevice]

class MetricPoint(BaseModel):
    timestamp: datetime
    value: float

class ServerHistory(BaseModel):
    cpu: List[MetricPoint]
    memory: List[MetricPoint]
    disk: List[MetricPoint]
    net_sent: List[MetricPoint]
    net_recv: List[MetricPoint]


# ============================================================================
# DATABASE VIEW SCHEMAS (Read-Only)
# ============================================================================

class VSkuMasterDetail(BaseModel):
    """Schema for v_sku_master_detail view"""
    id: int
    sku_id: str
    sku_name: str
    std_batch_size: Optional[float] = None
    uom: Optional[str] = None
    status: Optional[str] = None
    creat_by: Optional[str] = None
    created_at: Optional[datetime] = None
    update_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    total_phases: Optional[int] = 0
    total_sub_steps: Optional[int] = 0
    last_step_update: Optional[datetime] = None
    sku_group: Optional[int] = None
    sku_group_code: Optional[str] = None
    sku_group_name: Optional[str] = None

    class Config:
        from_attributes = True


class VSkuStepDetail(BaseModel):
    """Schema for v_sku_step_detail view"""
    step_id: int
    sku_id: str
    phase_number: str
    phase_id: Optional[str] = None
    sub_step: int
    action: Optional[str] = None
    re_code: Optional[str] = None
    action_code: Optional[str] = None
    setup_step: Optional[str] = None
    destination: Optional[str] = None
    require: Optional[float] = None
    uom: Optional[str] = None
    low_tol: Optional[float] = None
    high_tol: Optional[float] = None
    step_condition: Optional[str] = None
    
    agitator_rpm: Optional[float] = None
    high_shear_rpm: Optional[float] = None
    temperature: Optional[float] = None
    temp_low: Optional[float] = None
    temp_high: Optional[float] = None
    
    ph: Optional[float] = None # Keeping for backward compat if needed, or remove? Replaced by ph_sp string?
    brix: Optional[float] = None # Replaced by brix_sp?
    
    step_time: Optional[int] = None
    step_timer_control: Optional[int] = None
    
    qc_temp: Optional[bool] = None
    record_steam_pressure: Optional[bool] = None
    record_ctw: Optional[bool] = None
    operation_brix_record: Optional[bool] = None
    operation_ph_record: Optional[bool] = None
    
    brix_sp: Optional[str] = None
    ph_sp: Optional[str] = None

    step_created_at: Optional[datetime] = None
    step_updated_at: Optional[datetime] = None
    
    # SKU Master info
    sku_name: Optional[str] = None
    std_batch_size: Optional[float] = None
    uom_master: Optional[str] = None
    sku_status: Optional[str] = None
    
    # Lookups
    action_description: Optional[str] = None
    destination_description: Optional[str] = None
    ingredient_name: Optional[str] = None
    mat_sap_code: Optional[str] = None
    blind_code: Optional[str] = None
    ingredient_category: Optional[str] = None
    ingredient_unit: Optional[str] = None
    std_package_size: Optional[float] = None
    
    # Computed fields
    step_label: Optional[str] = None
    full_action_description: Optional[str] = None
    full_destination_description: Optional[str] = None

    class Config:
        from_attributes = True


class VSkuComplete(BaseModel):
    """Schema for v_sku_complete view"""
    sku_id: str
    step_number: Optional[str] = None
    sku_name: str
    std_batch_size: Optional[float] = None
    uom: Optional[str] = None
    status: Optional[str] = None
    
    phase_number: Optional[str] = None
    phase_id: Optional[str] = None
    sub_step: Optional[int] = None
    
    action: Optional[str] = None
    action_code: Optional[str] = None
    action_description: Optional[str] = None
    
    re_code: Optional[str] = None
    ingredient_name: Optional[str] = None
    mat_sap_code: Optional[str] = None
    blind_code: Optional[str] = None
    
    destination: Optional[str] = None
    destination_description: Optional[str] = None
    
    required_amount: Optional[float] = None
    low_tol: Optional[float] = None
    high_tol: Optional[float] = None
    
    qc_temp: Optional[bool] = None
    record_steam_pressure: Optional[bool] = None
    record_ctw: Optional[bool] = None
    operation_brix_record: Optional[bool] = None
    operation_ph_record: Optional[bool] = None
    brix_sp: Optional[str] = None
    ph_sp: Optional[str] = None
    agitator_rpm: Optional[float] = None
    high_shear_rpm: Optional[float] = None
    temperature: Optional[float] = None
    step_time: Optional[int] = None
    
    setup_step: Optional[str] = None
    
    creat_by: Optional[str] = None
    created_at: Optional[datetime] = None
    update_by: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


