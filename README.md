# 🏭 xMixing Control System (x31-xMixingControl)
> **Digital Plant Innovation & Industrial Process Automation Platform**  
> *Mitr Phol SP Syrup & Ingredient Mixing Process Control Platform*

[![Nuxt 3](https://img.shields.io/badge/Frontend-Nuxt%203%20%7C%20Vue%203-00DC82?style=flat-square&logo=nuxt.js)](https://nuxt.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Siemens S7-1500](https://img.shields.io/badge/PLC-Siemens%20S7--1500%20%2F%20S7--1200-00646E?style=flat-square&logo=siemens)](https://www.siemens.com/)
[![MariaDB](https://img.shields.io/badge/Database-MariaDB%20Cluster-003545?style=flat-square&logo=mariadb)](https://mariadb.org/)
[![MQTT](https://img.shields.io/badge/Protocol-MQTT%20%7C%20Node--RED-660066?style=flat-square&logo=mqtt)](https://mqtt.org/)

---

## 🌐 Language Navigation (สารบัญเลือกภาษา)
- [🇹🇭 ภาษาไทย (Thai Documentation)](#-ภาษาไทย-thai-version)
  - [1. ภาพรวมและสถาปัตยกรรมระดับโรงงาน (System & Network Architecture)](#1-ภาพรวมและสถาปัตยกรรมระดับโรงงาน-system--network-architecture)
  - [2. โครงสร้างสถาปัตยกรรม 2 หน้าจอ (Dual-Screen Operation Architecture)](#2-โครงสร้างสถาปัตยกรรม-2-หน้าจอ-dual-screen-operation-architecture)
  - [3. โครงสร้างหน่วยความจำ PLC Data Blocks (PLC Memory Layout)](#3-โครงสร้างหน่วยความจำ-plc-data-blocks-plc-memory-layout)
  - [4. โครงสร้างฐานข้อมูลเชิงสัมพันธ์ (Database Relational Schema)](#4-โครงสร้างฐานข้อมูลเชิงสัมพันธ์-database-relational-schema)
  - [5. โครงสร้างโฟลเดอร์และคอมโพเนนต์ซอฟต์แวร์ (Software Stack & Tree)](#5-โครงสร้างโฟลเดอร์และคอมโพเนนต์ซอฟต์แวร์-software-stack--tree)
  - [6. กระบวนการผลิตและการล็อกสเต็ป (Manufacturing Process & Interlock)](#6-กระบวนการผลิตและการล็อกสเต็ป-manufacturing-process--interlock)
  - [7. การติดตั้งและคำสั่งควบคุมระบบ (Setup, Deploy & Maintenance)](#7-การติดตั้งและคำสั่งควบคุมระบบ-setup-deploy--maintenance)
- [🇬🇧 English Documentation](#-english-version)
  - [1. Executive Summary & Factory-Wide Architecture](#1-executive-summary--factory-wide-architecture)
  - [2. Dual-Interface Decoupled Topology](#2-dual-interface-decoupled-topology)
  - [3. Siemens PLC Memory Layout & Datablock Specs](#3-siemens-plc-memory-layout--datablock-specs)
  - [4. Relational Database Schema & Entities](#4-relational-database-schema--entities)
  - [5. Software Component Architecture & Event Loops](#5-software-component-architecture--event-loops)
  - [6. Production Phase Sequences & Interlock Logic](#6-production-phase-sequences--interlock-logic)
  - [7. Operational Commands & API Reference](#7-operational-commands--api-reference)

---

# 🇹🇭 ภาษาไทย (Thai Version)

## 1. ภาพรวมและสถาปัตยกรรมระดับโรงงาน (System & Network Architecture)

ระบบ **xMixing Control System** ถูกออกแบบตามมาตรฐาน ISA-95 สำหรับโรงงานอุตสาหกรรมอาหารและเครื่องดื่ม เชื่อมต่อระหว่างอุปกรณ์หน้างาน (Level 1/2) เข้ากับระบบควบคุมการผลิต (Level 3 MES) แบบ Real-time ครอบคลุมทั้ง 3 สายการผลิต (Plant 1, Plant 2, Plant 3)

```
============================================================================
                        🏭 PLANT NETWORK TOPOLOGY
============================================================================

             [ Level 3: Central Database & Management Center ]
                   Host: 192.168.121.11 (MariaDB Cluster)
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ Mixing Node .21 │         │ Mixing Node .22 │         │ 🏭 Mixing Node.23│
│ (xmitphol-01)   │         │ (xmitphol-02)   │         │ (xmitphol-03)   │
│ • Nuxt 3  :3000 │         │ • Nuxt 3  :3000 │         │ • Nuxt 3  :3031 │
│ • Grafana :3100 │         │ • Grafana :3100 │         │ • FastAPI :8031 │
│ • MQTT    :1883 │         │ • MQTT    :1883 │         │ • MQTT    :1883 │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
        ┌────────────────────────────┴────────────────────────────┐
        ▼ (Plant LAN: 192.168.121.x)                              ▼ (OT LAN: 192.168.21.x)
┌───────────────────────┐                               ┌───────────────────────┐
│   Process Wi-Fi AP    │                               │   Industrial Switch   │
└───────────┬───────────┘                               └───────────┬───────────┘
            │                                                       │
    ┌───────┴───────┐                                       ┌───────┼───────┐
    ▼               ▼                                       ▼       ▼       ▼
┌───────┐       ┌───────┐                               ┌───────┐┌───────┐┌───────┐
│Master │       │Pour   │                               │Plant 1││Plant 2││Plant 3│
│HMI    │       │HUD    │                               │Siemens││Siemens││Siemens│
│Console│       │Tablets│                               │S7-1500││S7-1500││S7-1500│
└───────┘       └───────┘                               └───────┘└───────┘└───────┘
============================================================================
```

### 📋 ตารางระบุโฮสต์ การเข้าถึง และพอร์ตของระบบโรงงาน (Plant Host Registry)
| Host IP | Hostname | SSH Login (`user:pass`) | Web Application Ports | หน้าที่และบทบาทการทำงาน |
| :--- | :--- | :--- | :--- | :--- |
| **`192.168.121.11`** | `xmitphol-db` | `x-root:xDev100!` (:22) | `3306` (MariaDB), `8000` | **Level 3 MES / Database Center** (ศูนย์กลางฐานข้อมูล MariaDB Cluster) |
| **`192.168.121.21`** | `xmitrphol-ubuntu2404` | `x-root:xDev100!` (:22) | `3000` (Nuxt), `3100` (Grafana) | **Mixing Station Node 1** (สายการผลิตที่ 1 / Local App & Scale) |
| **`192.168.121.22`** | `xmitphol-02` | `x-root:xDev100!` (:22) | `3000` (Nuxt), `3100` (Grafana) | **Mixing Station Node 2** (สายการผลิตที่ 2 / Local App & Scale) |
| **`192.168.121.23`** | **`xmitphol-03`** | `x-root:xDev100!` (:22) | `3031` (Nuxt), `8031` (FastAPI) | **Central Mixing Host Node 3** (เซิร์ฟเวอร์ระบบผสมหลัก คุม Plant 1, 2, 3) |
| **`192.168.21.210`** | `PLC-S7-1500` | - | `102` (ISO-on-TCP) | **Main Mixing PLC** (ควบคุมถังผสม, วาล์ว, อุณหภูมิ, โหลดเซลล์) |
| **`192.168.21.51`** | `PLC-Process` | - | `102` (ISO-on-TCP) | **Process Drive PLC** (ควบคุมปั๊มและมอเตอร์หัวตัด High-Shear) |

---

## 2. โครงสร้างสถาปัตยกรรม 2 หน้าจอ (Dual-Screen Operation Architecture)

เพื่อแก้ไขปัญหาคอขวดและลดความผิดพลาดในการสื่อสารข้ามจุดระหว่าง **คนคุมเครื่อง (ห้องต้ม)** และ **คนเทวัตถุดิบ (ปากถังผสม)** ระบบจึงแยกหน้าที่ของหน้าจอออกเป็น 2 มุมมองหลักที่ซิงค์ข้อมูลผ่าน MQTT แบบ Real-time:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 DUAL-SCREEN OPERATION                                  │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ 🖥️ Master HMI Console (/x61-MixingControl)│ 📱 Pour Station HUD (/x61-PourHUD)         │
├───────────────────────────────────────────┼────────────────────────────────────────────┤
│ • ผู้ใช้งาน: User 2 (Cook / คนคุมเครื่อง) │ • ผู้ใช้งาน: User 1 (Pour / คนเทวัตถุดิบ)  │
│ • อุปกรณ์: PC Kiosk จอสัมผัสในห้องควบคุม  │ • อุปกรณ์: Tablet / มือถือ ประจำจุดเท      │
│ • หน้าที่:                                │ • หน้าที่:                                 │
│   - เลือกสูตรและเริ่มแบทช์การผลิต (Start) │   - แสดง Checklist สารเฉพาะ Phase ปัจจุบัน │
│   - ควบคุมคำสั่ง PLC (Run/Pause/Abort)    │   - แสดงน้ำหนักและจำนวนถุงเป้าหมาย         │
│   - มอนิเตอร์อุณหภูมิ, RPM, วาล์ว, ปั๊ม   │   - สแกนยิงบาร์โค้ดยืนยันตัวสารก่อนเท      │
│   - ยืนยันพารามิเตอร์คุณภาพ (Brix/pH/CTW) │   - มีเสียงพูด Sweet Voice แจ้งชื่อสารสด   │
│   - ปิดจบแบทช์และออกรายงาน PDF Report     │   - สแกนตัวไหนก่อน-หลังก็ได้ใน Phase       │
└───────────────────────────────────────────┴────────────────────────────────────────────┘
```

---

## 3. โครงสร้างหน่วยความจำ PLC Data Blocks (PLC Memory Layout)

การสื่อสารระหว่าง Backend (Python Snap7) กับ Siemens S7-1500/1200 ใช้โครงสร้าง Datablock ที่แน่นอน:

### 3.1 DB 1510 / DB 1780 — Recipe Target & Command (32 Processes × 8 Steps)
```
+---------------+---------------+------------------------------------------------------+
| Byte Offset   | Type          | Field Name / Description                             |
+---------------+---------------+------------------------------------------------------+
| 0.0           | String[20]    | Plan_ID (รหัสแผนการผลิต เช่น P260907-03-02)          |
| 22.0          | String[20]    | Batch_ID (รหัสแบทช์ เช่น P260907-03-02-001)          |
| 44.0          | String[20]    | Sku_ID (รหัสสินค้า เช่น S7HFRU4200)                  |
| 66.0          | String[40]    | Sku_Name (ชื่อสูตร เช่น Orange Syrup Freshy)         |
| 108.0         | Int           | Plant_ID (1 = Line 1, 2 = Line 2, 3 = Line 3)        |
| 110.0         | Real          | Batch_Size (ขนาดแบทช์ เช่น 1200.0 kg)                |
| 114.0         | Int           | Process_Count (จำนวน Phase ทั้งหมดในสูตร)            |
+---------------+---------------+------------------------------------------------------+
| ARRAY[1..32] OF UDT_Process:                                                         |
|   +0.0        | Int           | Process_No (เช่น 10, 15, 16, 20, 30, 40...)          |
|   +2.0        | Int           | Phase_ID (1=A1010, 2=A1020, 5=x1010, 7=x1030...)    |
|   +4.0        | Int           | Step_Count (จำนวน Step ใน Phase นี้ 1..8)            |
|   +6.0        | Bool          | Process_Active (สถานะการทำงานของ Phase)              |
|   ARRAY[1..8] OF UDT_ProcessStep:                                                    |
|     +0.0      | Int           | Step_No (เช่น 10, 20, 30)                            |
|     +2.0      | DInt          | Action_Code (เช่น 10010, 10020, 20030, 30010, 30500) |
|     +6.0      | String[16]    | Re_Code (รหัสวัตถุดิบ เช่น W100 CG 50 kg)            |
|     +24.0     | Real          | Require / Target_Weight (น้ำหนักเป้าหมาย kg)         |
|     +28.0     | Real          | Low_Tol / High_Tol (ค่าเผื่อพิกัดน้ำหนัก)            |
|     +36.0     | Real          | Temperature_SP (อุณหภูมิเป้าหมาย °C)                 |
|     +40.0     | Real          | Agitator_RPM (ความเร็วกวนผสม RPM)                    |
|     +44.0     | Real          | HighShear_RPM (ความเร็วไฮเชียร์ RPM)                 |
|     +48.0     | DInt          | Step_Time (เวลานับถอยหลัง วินาที)                    |
+---------------+---------------+------------------------------------------------------+
```

### 3.2 DB 1520 / DB 1517 — Real-Time Telemetry & Actual Sensors
```
+---------------+---------------+------------------------------------------------------+
| Field Name    | Type          | Description / Sensor Mapping                         |
+---------------+---------------+------------------------------------------------------+
| PLC_State     | Int           | 0=Standby, 1=Starting, 2=Running, 24=Ready Transfer  |
| Phase_ID      | String[8]     | รหัส Phase ปัจจุบัน (เช่น "p016", "p020")            |
| Step_ID       | Int           | สเต็ปย่อยปัจจุบัน (เช่น 10, 20)                      |
| Actual_Weight | Real          | น้ำหนักรวมถังผสมปัจจุบัน (Mixing Tank Weight kg)     |
| Actual_Temp   | Real          | อุณหภูมิถังผสมจริง (TEMP01 °C)                       |
| Actual_Agit   | Real          | ความเร็วมอเตอร์กวนจริง (MixingTank_Agitator_Speed)   |
| Actual_HShear | Real          | ความเร็วชุดตัดไฮเชียร์จริง (HighShare_Speed RPM)      |
+---------------+---------------+------------------------------------------------------+
```

---

## 4. โครงสร้างฐานข้อมูลเชิงสัมพันธ์ (Database Relational Schema)

```
┌─────────────────────────┐         ┌─────────────────────────┐
│    production_plans     │         │       sku_recipes       │
├─────────────────────────┤         ├─────────────────────────┤
│ PK plan_id              │◄──┐     │ PK sku_id               │◄──┐
│    sku_id               │   │     │    sku_name             │   │
│    plan_date            │   │     │    std_batch_size       │   │
│    total_batches        │   │     └───────────┬─────────────┘   │
└────────────┬────────────┘   │                 │ 1:N             │
             │ 1:N            │                 ▼                 │
             ▼                │     ┌─────────────────────────┐   │
┌─────────────────────────┐   │     │    sku_recipe_steps     │   │
│   production_batches    │   │     ├─────────────────────────┤   │
├─────────────────────────┤   │     │ PK id                   │   │
│ PK batch_id             │───┘     │ FK sku_id               │───┘
│ FK plan_id              │         │    phase_number         │
│    sku_id               │         │    phase_id (A1010...)  │
│    batch_size           │         │    step_number          │
│    plant (Line-1/2/3)   │         │    action_code          │
│    status (In-Progress) │         │    re_code / sap_code   │
│    created_at           │         │    target_value         │
└────────────┬────────────┘         │    temp_sp / agitator_sp│
             │ 1:N                  └─────────────────────────┘
             ├───────────────────────────────────┐
             ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│ batch_requirements(reqs)│         │   production_step_logs  │
├─────────────────────────┤         ├─────────────────────────┤
│ PK id                   │         │ PK id                   │
│ FK batch_id             │         │ FK batch_id             │
│    re_code              │         │    phase_id ("p016")    │
│    ingredient_name      │         │    sub_step (10)        │
│    required_volume      │         │    re_code              │
│    total_packaged       │         │    target_value (120.0) │
│    wh (SPP / MIX)       │         │    actual_value (123.6) │
│    status (0/1)         │         │    actual_temp (62.8)   │
└─────────────────────────┘         │    completed_at         │
                                    │    operator (User 1)    │
                                    │    operator2 (User 2)   │
                                    └─────────────────────────┘
```

---

## 5. โครงสร้างโฟลเดอร์และคอมโพเนนต์ซอฟต์แวร์ (Software Stack & Directory Tree)

โครงสร้างระบบทั้งหมดถูกจัดหมวดหมู่แยกตามประเภทของงานอย่างเป็นระเบียบ:

```
x2512001-mitrPhol-x31-xMixingControl/
├── 🌐 x3101-app/                      # แอปพลิเคชันหลักของระบบ Mixing Control
│   ├── x3101-0110-frontEnd/          # 🖥️ Nuxt 3 / Vue 3 + TypeScript Frontend (Port 3031)
│   │   ├── app/
│   │   │   ├── pages/
│   │   │   │   ├── x61-MixingControl.vue   # หน้าจอควบคุมการผสมหลัก (Master HMI)
│   │   │   │   ├── x61-PourHUD.vue         # หน้าจอจุดเทสำหรับแท็บเล็ต (Pour Station HUD)
│   │   │   │   ├── x71-MixingReport.vue    # รายงานผลการผสมรายแบทช์ (Mixing Report)
│   │   │   │   ├── x78-ShiftLogbook.vue    # บันทึกกะการผลิต (Shift Logbook)
│   │   │   │   └── x80-UserLogin.vue       # ระบบล็อกอินแบบสแกนป้ายบาร์โค้ด
│   │   │   ├── composables/                # State & MQTT / Auth composables
│   │   │   ├── appConfig/                  # Dynamic Base URL Config (:8031)
│   │   │   └── sounds/                     # ไฟล์เสียงแจ้งเตือน Sweet Voice MP3
│   │   ├── tests/
│   │   │   ├── scripts/                    # Test scripts สำหรับ Frontend / MQTT
│   │   │   └── simulators/                 # PLC & Scan simulators
│   │   └── nuxt.config.ts
│   │
│   ├── x3101-0210-backEnd/           # ⚙️ FastAPI + Python 3.12 Backend (Port 8031)
│   │   └── x0201-fastAPI/
│   │       ├── main.py                     # FastAPI Entry Point
│   │       ├── database.py                 # SQLAlchemy Database Session
│   │       ├── models.py                   # ORM Database Models
│   │       ├── schemas.py                  # Pydantic Schemas
│   │       ├── plc_service.py              # Snap7 PLC S7-1500 Communication
│   │       ├── plc_datablock.py            # DB1510/DB1780 Recipe Serializer
│   │       ├── recipe_sequencer.py         # Interlock & Step Sequencer Logic
│   │       ├── worker_handshake.py         # PLC Step Watcher & Handshake
│   │       ├── routers/                    # REST API Endpoints
│   │       ├── crud/                       # Database CRUD Operations
│   │       ├── scripts/
│   │       │   ├── migrations/             # สคริปต์ Database Schema Migrations
│   │       │   ├── seeds/                  # สคริปต์สร้าง Master Data & Simulation Plans
│   │       │   ├── sync/                   # สคริปต์ Sync ข้อมูลระหว่าง Cloud / Local
│   │       │   └── diagnostics/            # สคริปต์วินิจฉัยและตรวจสอบระบบ Backend
│   │       └── tests/
│   │           └── scripts/                # Unit Tests & Integration Tests
│   │
│   └── simulation/                   # 🧪 สภาพแวดล้อมจำลองการทำงาน (Docker Sim & Flows)
│
├── 🚀 deployments/                   # โครงสร้างการติดตั้งและ Service Daemons
│   ├── docker/                       # Docker Compose configs (server, edge, client)
│   ├── services/                     # Systemd service files (fastapi, nuxt, xmixing)
│   ├── desktop/                      # Desktop Launcher shortcuts (.desktop)
│   └── scripts/                      # Watchdog & auto-start scripts
│
├── 📚 docs/                          # เอกสารคู่มือและการออกแบบระบบ
│   ├── manuals/                      # คู่มือการใช้งาน SOP, WI, Master Manuals (PDF & MD)
│   ├── recipes/                      # ข้อมูลสเปกสูตรการผลิต (PLC Recipe Mapping)
│   ├── architecture/                 # เอกสารสถาปัตยกรรมระบบ และ Flowchart การทำงาน
│   └── reports/                      # รายงานผลการทดสอบ (Test Reports)
│
├── 🔌 integrations/                  # ส่วนเชื่อมต่อระบบภายนอก
│   └── nodered/                      # Node-RED Recipe Flows & S7 Bridge Tools
│
├── ⚡ plc_code/                       # ซอร์สโค้ด PLC Siemens S7-1500 / S7-1200
│   ├── TIA_Full/                     # SCL Datablocks, UDTs, FBs, FCs สำหรับ TIA Portal
│   └── *.scl                         # Sequencer, Bridge, และ Checksum SCL Files
│
├── 🛠️ tools/                         # เครื่องมือพัฒนาและตรวจสอบระบบ
│   ├── diagnostics/                  # สคริปต์ทดสอบ MQTT, Snap7, Telemetry, Database
│   └── qr_generator/                 # เครื่องมือสร้างและถอดรหัส QR Code บาร์โค้ด
│
├── 📊 x3109-x3195 Services/          # Microservices สนับสนุน
│   ├── x3109-locMqtt/                # RabbitMQ MQTT Broker
│   ├── x3112-nodeRed/                # Node-RED Simulation Engine
│   ├── x3190-history/                # Telegraf Time-series Collector
│   ├── x3191-gafana/                 # Grafana Dashboards
│   ├── x3192-SystemDashBoard/        # Prometheus Monitoring
│   ├── x3193-CloudMonitor/           # Cloud Monitoring Agent
│   ├── x3194-ThingsBoard/            # ThingsBoard IoT Platform
│   └── x3195-DashboardDesign/        # Web Dashboard Design Mockups
│
├── 💡 x9000-Concept/                  # เอกสารแนวคิดการออกแบบระบบตั้งต้น
└── 📖 README.md                       # เอกสารคู่มือระบบหลักฉบับสมบูรณ์ (Master Blueprint)
```

---

## 6. กระบวนการผลิตและการล็อกสเต็ป (Manufacturing Process & Interlock)

### 6.1 Action Codes มาตรฐานในระบบ
| Action Code | ชื่อกระบวนการ | รายละเอียดการทำงาน | เงื่อนไขการปลดล็อก (Interlock) |
| :--- | :--- | :--- | :--- |
| **`10010`** | RO Water Batching | เติมน้ำ RO เข้าถังผสมตามปริมาตร | เซ็นเซอร์ Flow meter ครบปริมาตร |
| **`10020`** | MIS Batching | ปั๊มน้ำเชื่อม MIS เข้าถังผสม | โหลดเซลล์ชั่งน้ำหนักได้ตาม Target |
| **`30500`** | Heats Up | ต้มเพิ่มอุณหภูมิพร้อมกวนผสม | อุณหภูมิถึง Temp SP ± พิกัด |
| **`30010`** | Manual Add Ingredient | คนเทเทสารผง/สารเคมีเข้าถัง | สแกนบาร์โค้ดครบถุง + ชั่งน้ำหนักในพิกัด |
| **`20030`** | Pre-mix High Shear | ปั่นกวนผสมด้วยหัวตัดความเร็วสูง | นับเวลาถอยหลัง Step Time ครบ |

### 6.2 กลไก Phase-Based Free Scanning
```
[ เริ่มต้น Phase (เช่น p016 / p020) ]
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ ผู้ปฏิบัติงานนำบาร์โค้ด IND ตัวใดก็ได้ใน Phase มายิง  │
└────────────────┬────────────────────────────────┘
                 │
                 ├──► [ ยิงถูกตัว ] ──► บันทึก Log เขียว + เสียง Beep ติ๊ด + พูดชื่อสาร
                 └──► [ ยิงผิดตัว ] ──► แจ้งเตือน Error แดง + เสียง Alarm หวอ
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│     ตรวจสอบเงื่อนไข: สแกน IND ครบทุกตัวใน Phase?   │
└────────────────┬────────────────────────────────┘
                 ├──► [ ยังไม่ครบ ] ──► รอสแกนตัวที่เหลือ (PLC ล็อกไม่อนุญาตให้เริ่มต้ม)
                 └──► [ ครบ 100% ]  ──► ปลดล็อก Interlock ──► PLC อนุญาตให้เริ่ม Heat/Next
```

---

## 7. การติดตั้งและคำสั่งควบคุมระบบ (Setup, Deploy & Maintenance)

### 7.1 ตรวจสอบสถานะการทำงาน
```bash
# ตรวจสอบพอร์ต Backend (8031) และ Frontend (3031)
netstat -tulnp | grep -E '8031|3031'

# ตรวจสอบ Watchdog Log
tail -f /home/x-root/xApp/watchdog.log

# ตรวจสอบ Batch Watcher Service
tail -f /home/x-root/xApp/batch_watcher.log
```

### 7.2 คำสั่งคอมไพล์และรีสตาร์ท Frontend (Nuxt 3)
```bash
cd /home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0110-frontEnd
npm run build
pkill -f 'index.mjs'
PORT=3031 NITRO_PORT=3031 HOST=0.0.0.0 nohup node .output/server/index.mjs > /tmp/nuxt.log 2>&1 &
```

---

<br><br>

---

# 🇬🇧 English Version

## 1. Executive Summary & Factory-Wide Architecture
The **xMixing Control System** is an enterprise-grade Manufacturing Execution System (MES) and supervisory gateway designed specifically for sugar syrup and ingredient formulation facilities. It bridges factory floor industrial sensors, digital scale interfaces, handheld barcode terminals, and Siemens S7-1500 PLCs into a unified, redundant control architecture.

### 🌐 Physical Network Topology & Host Nodes:
* **Central MES & Database Center (192.168.121.11):** MariaDB Cluster hosting plant-wide ERP orders, historical batch archives, and synchronized master recipes.
* **General Factory Dashboards (192.168.121.21 & .22):** Client display nodes for other production lines and plant monitoring overview.
* **Dedicated Mixing Edge Host (192.168.121.23 / xmitphol-03):** Central industrial edge workstation running FastAPI (:8031) and Nuxt 3 (:3031) that orchestrates **all three mixing lines (Plant 1, Plant 2, Plant 3)** concurrently. Dual-homed with an isolated OT Industrial subnet (192.168.21.198) communicating directly to Siemens S7-1500 PLCs (192.168.21.210 & 192.168.21.51).

---

## 2. Dual-Interface Decoupled Topology
* **Master HMI (`/x61-MixingControl`):** High-density SCADA/MES console located in the boiling control room for Cook Operators (User 2) to monitor temperatures, agitator RPMs, execute step confirmations, and manage overall recipe progressions.
* **Pour Station HUD (`/x61-PourHUD`):** Dedicated, high-contrast, large-card tablet HUD deployed at eye-level near the dosing hopper for Pour Operators (User 1) to view real-time ingredient checklists, perform burst barcode scanning, and receive instant audio verification.

---

## 3. Siemens PLC Memory Layout & Datablock Specs
* **DB1510 / DB1780 (Recipe Master):** Contains the 32-process × 8-step recipe array with Target Weights, Temperatures, Agitator Setpoints, and Action Codes.
* **DB1520 / DB1517 (Live Telemetry):** Real-time cyclic telemetry of actual mixing tank volume, live temperature probes, mixer RPMs, and current active phase/step indicators.

---

## 4. Relational Database Schema & Entities
* `production_plans` ➔ `production_batches` ➔ `batch_requirements (reqs)` ➔ `production_step_logs`
* `sku_recipes` ➔ `sku_recipe_steps` ➔ `ingredients`
* Multi-plant data isolation partitioned across Plant 1, Plant 2, and Plant 3 with real-time replication to DB Center `192.168.121.11`.

---

## 5. Software Component Architecture & Event Loops
* **Zero-Click Barcode Engine:** Native hardware keycode translation (`e.code` mapping) immune to client OS language switching.
* **Neural Sweet Voice Engine:** Multi-frequency Web Audio oscillator chimes coupled with pre-rendered Thai studio neural voice prompts (*Nong Premawadee*).
* **Smart Batch Watcher (`xmixing_batch_watcher.py`):** Deduplicated background watcher service preventing notification spam while generating clean shift summary reports.

---

## 6. Production Phase Sequences & Interlock Logic
* **`10010` RO Water Dosing:** Monitored via volumetric flow meters.
* **`10020` MIS Liquid Sugar Batching:** Verified via vessel load cells.
* **`30010` Manual Ingredient Addition:** Requires barcode verification within defined tolerance bands.
* **`30500` Recipe Heating Phase:** Hard PLC gatekeeper interlock preventing heat activation until all preceding ingredient additions are 100% verified.

---

## 7. Operational Commands & API Reference
| Method | Route | Purpose |
| :--- | :--- | :--- |
| `GET` | `/plc/plant/{id}/recipe-status` | Real-time PLC sequence state, target weights, and active steps |
| `GET` | `/production-batches/{id}/logs` | Complete timestamped audit trail of completed mixing steps |
| `POST`| `/auth/switch-operator/{username}`| Rapid zero-click operator badge reassignment |
| `GET` | `/production-plans/?status=all` | Plant-wide production scheduling queues |

---

### 👨‍💻 Engineering Team & Maintenance
* **Developer:** Piyapong Nuanjan
* **Facility:** Mitr Phol SP Syrup Production Plant
* **Repository:** `git@github.com:x92120/x2512001-mitrPhol-x31-xMixingControl-site.git`
