# 🏭 xMixing Control System (x31-xMixingControl)
> **Digital Plant Innovation & Industrial Process Automation**  
> *Mitr Phol SP Syrup & Ingredient Mixing Process Control Platform*

---

## 🌐 Language Navigation (เลือกภาษา)
- [🇹🇭 ภาษาไทย (Thai Documentation)](#-ภาษาไทย-thai-version)
- [🇬🇧 English (English Documentation)](#-english-version)

---

# 🇹🇭 ภาษาไทย (Thai Version)

## 1. บทนำและภาพรวมระบบ (System Overview)
**xMixing Control System** เป็นระบบควบคุมและติดตามกระบวนการผสมน้ำเชื่อมและวัตถุดิบอัตโนมัติระดับอุตสาหกรรม (Industrial MES & SCADA Gateway) พัฒนาขึ้นเพื่อควบคุมคุณภาพและความแม่นยำในการผลิตของโรงงาน Mitr Phol SP รองรับการทำงานแบบขนาน 3 สายการผลิต (Plant 1, Plant 2, Plant 3) โดยเชื่อมต่อระหว่างระบบซอฟต์แวร์ควบคุมหน้างาน (HMI), เครื่องชั่ง (Scales), บาร์โค้ดสแกนเนอร์ (Barcode/QR Scanners), ฐานข้อมูลกลาง (DB Center) และ PLC อุตสาหกรรม (Siemens S7-1500) แบบ Real-time

```
                          ┌────────────────────────┐
                          │   DB Center (.11)      │
                          │   (MariaDB Master)     │
                          └───────────┬────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
  ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
  │  Mixing Node .21  │     │  Mixing Node .22  │     │  Mixing Node .23  │
  │     (Plant 1)     │     │     (Plant 2)     │     │     (Plant 3)     │
  └─────────┬─────────┘     └─────────┬─────────┘     └─────────┬─────────┘
            │                         │                         │
  ┌─────────┴─────────┐     ┌─────────┴─────────┐     ┌─────────┴─────────┐
  │  FastAPI (8031)   │     │  FastAPI (8031)   │     │  FastAPI (8031)   │
  │  Nuxt 3  (3031)   │     │  Nuxt 3  (3031)   │     │  Nuxt 3  (3031)   │
  │  Siemens PLC S7   │     │  Siemens PLC S7   │     │  Siemens PLC S7   │
  └───────────────────┘     └───────────────────┘     └───────────────────┘
```

---

## 2. โครงสร้างสถาปัตยกรรม 2 หน้าจอ (Dual-Screen Operation Architecture)
ระบบได้รับการออกแบบเพื่อแก้ปัญหาการสื่อสารข้ามจุดระหว่าง **"คนคุมเครื่อง (Cook Operator)"** ในห้องควบคุม และ **"คนเทวัตถุดิบ (Pour Operator)"** หน้าถังผสม:

```
                  ┌─────────────────────────────────────────────────┐
                  │              สถานีผสม (Mixing Station)          │
                  └────────────────────────┬────────────────────────┘
                                           │
          ┌────────────────────────────────┴────────────────────────────────┐
          ▼                                                                 ▼
┌───────────────────────────────────────┐         ┌───────────────────────────────────────┐
│     🖥️ Master Control (ห้องต้ม)        │         │      📱 Pour Station HUD (จุดเท)       │
│     URL: /x61-MixingControl           │         │      URL: /x61-PourHUD                │
├───────────────────────────────────────┤         ├───────────────────────────────────────┤
│ • ควบคุมสเต็ป PLC, Start/Pause/Abort  │         │ • จอแท็บเล็ต/มือถือประจำจุดเท (Eye-Level)│
│ • แสดงพารามิเตอร์รวม Temp, Agitator    │         │ • การ์ด Checklist รายการสารตัวใหญ่ยักษ์ │
│ • ยืนยันพารามิเตอร์ & ออกรายงาน Batch │         │ • สแกนยิงบาร์โค้ดยืนยันตัวสารหน้างาน  │
│ • สำหรับ User 2 (Cook Operator)       │         │ • เสียงแจ้งเตือน Sweet Voice + Beep   │
└───────────────────────────────────────┘         └───────────────────────────────────────┘
```

---

## 3. ฟังก์ชันและนวัตกรรมสำคัญ (Key Highlights & Innovations)

### 3.1 ระบบสแกนบาร์โค้ด Zero-Click Hardware Scanner Engine
* **Physical Key-to-ASCII Mapper:** แปลงสัญญาณ Key Event ที่ระดับ Hardware Code (`e.code`) โดยตรง ทำให้สามารถอ่านบาร์โค้ด/QR Code ได้ถูกต้องแม่นยำ **100% แม้ระบบปฏิบัติการของเครื่องจะสลับเป็นแป้นพิมพ์ภาษาไทยอยู่ก็ตาม**
* **Instant Fast Queue:** ประมวลผลการยิงรัว 2-3 บาร์โค้ดต่อเนื่องได้โดยไม่หลุดเฟรม ตัดสถานะการ์ดบนจอเป็นสีเขียวทันทีและบันทึก API เบื้องหลัง

### 3.2 การควบคุมตามเฟสและการล็อก PLC (Phase-based & PLC Interlock)
* **Free-order Scanning within Phase:** ภายใน Phase เดียวกัน ผู้ปฏิบัติงานสามารถหยิบวัตถุดิบ (IND) ตัวไหนมาสแกนและเทก่อน-หลังก็ได้ เพื่อความคล่องตัวหน้างานสูงสุด
* **PLC Boiling Interlock:** PLC จะล็อกไม่ยอมให้เริ่มกระบวนการต้ม/เพิ่มความร้อน (เช่น Heat 90°C) จนกว่าสัญญาณยืนยันการสแกนสารใน Phase นั้นจะครบ 100% ป้องกันข้อผิดพลาดของมนุษย์ (Zero Human Error)

### 3.3 ระบบเสียงอัจฉริยะ (Sweet Voice & Web Audio Buzzer)
* **Neural Sweet Voice (น้องเปรมวดี):** เสียงภาษาไทยสังเคราะห์คุณภาพสตูดิโอ พูดชื่อวัตถุดิบและสถานะ เช่น *"สแกนสำเร็จ: กรดมะนาว"* หรือ *"วัตถุดิบไม่ตรงสูตร"*
* **Multi-frequency Oscillator:** เสียงสัญญาณ Beep สั้นยืนยันความถูกต้อง และเสียง Sawtooth Alarm เตือนเมื่อเกิดข้อผิดพลาด

### 3.4 ระบบรายงานอัจฉริยะ (Smart Batch Watcher)
* **Spam-free Monitoring:** บันทึกประวัติการจบแบทช์โดยอัตโนมัติ และตัดปัญหาการส่งอีเมลถี่เกินไป โดยรวบรวมส่งเป็น **รายงานสรุปรายกะ (Shift Summary Report)** หรือแจ้งเตือนเฉพาะเมื่อมี Supervisor Bypass

---

## 4. โครงสร้างโฟลเดอร์โปรเจกต์ (Project Directory Structure)
```
x2512001-mitrPhol-x31-xMixingControl/
├── x3101-app/
│   ├── x3101-0110-frontEnd/          # 🌐 Nuxt 3 / Vue 3 + TypeScript Frontend (Port 3031)
│   │   ├── app/
│   │   │   ├── pages/
│   │   │   │   ├── x61-MixingControl.vue   # หน้าจอควบคุมการผสมหลัก (Master HMI)
│   │   │   │   ├── x61-PourHUD.vue         # หน้าจอจุดเทสำหรับแท็บเล็ต (Pour Station HUD)
│   │   │   │   ├── x71-MixingReport.vue    # รายงานผลการผสมรายแบทช์ (Mixing Report)
│   │   │   │   ├── x78-ShiftLogbook.vue    # บันทึกกะการผลิต (Shift Logbook)
│   │   │   │   └── x80-UserLogin.vue       # ระบบล็อกอินแบบสแกนป้ายบาร์โค้ด
│   │   │   ├── composables/
│   │   │   │   ├── useMQTT.ts              # เชื่อมต่อ MQTT Telemetry & Real-time State
│   │   │   │   └── useAuth.ts              # จัดการ Token & User Roles
│   │   │   └── appConfig/config.ts         # Dynamic API Base URL Config
│   │   └── package.json
│   │
│   └── x3101-0210-backEnd/           # ⚙️ FastAPI + Python Backend (Port 8031)
│       └── x0201-fastAPI/
│           ├── main.py                     # FastAPI Application Entry
│           ├── plc_service.py              # Snap7 PLC S7-1500 Communication
│           ├── recipe_sequencer.py         # การจัดลำดับสูตรการผลิต & Interlock
│           ├── routers/                    # REST API Endpoints
│           └── models.py                   # SQLAlchemy ORM Models
│
├── deployments/                      # 🚀 สคริปต์ควบคุมและ Watchdog
│   └── watchdog_stability.sh         # Auto-recovery daemon & memory guard
│
├── auto_report_generator.py          # 📄 เครื่องมือสร้างรายงาน PDF และส่งอีเมล
├── xmixing_batch_watcher.py          # 🤖 Smart Batch Done Watcher Service
└── README.md                         # 📖 คู่มือการใช้งานระบบ (เอกสารนี้)
```

---

## 5. การติดตั้งและการรันระบบ (Setup & Commands)

### 5.1 การรัน Backend (FastAPI - Port 8031)
```bash
cd x3101-app/x3101-0210-backEnd/x0201-fastAPI
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8031 --reload
```

### 5.2 การสร้างและรัน Frontend (Nuxt 3 - Port 3031)
```bash
cd x3101-app/x3101-0110-frontEnd
npm install
npm run build
PORT=3031 HOST=0.0.0.0 node .output/server/index.mjs
```

### 5.3 การรัน Batch Watcher Daemon
```bash
python3 xmixing_batch_watcher.py
```

---

<br><br>

---

# 🇬🇧 English Version

## 1. Executive Summary & Overview
The **xMixing Control System** is an enterprise-grade industrial manufacturing execution (MES) and process control platform engineered for Mitr Phol SP. The system delivers 100% batch traceability, precision ingredient dosing verification, and automated boiling sequence orchestration across 3 parallel production lines (Plant 1, Plant 2, Plant 3).

It interfaces real-time sensor telemetry between Industrial Scales, High-speed Barcode Imagers, Central MariaDB Clusters, and Siemens S7-1500 PLCs.

---

## 2. Dual-Screen Operating Architecture
To eliminate miscommunication and cycle time bottlenecks between the **Cook Operator** (control room) and the **Pour Operator** (dosing vessel), the system deploys a decoupled dual-interface model:

1. **Master Control Console (`/x61-MixingControl`):**
   * High-density HMI for overall batch progress, PLC sequence triggering, parameter validation, and exception management.
2. **Pour Station HUD (`/x61-PourHUD`):**
   * High-contrast, responsive tablet interface positioned at eye-level at the pouring station.
   * Real-time phase ingredient checklist, large status cards, multi-bag scan counters, and local audio prompts.

---

## 3. Key Technological Innovations

### 3.1 Universal Zero-Click Barcode Engine
* **Hardware-Layer ASCII Mapping:** Resolves raw keycodes (`e.code`) directly from USB/Bluetooth HID scanners, guaranteeing 100% accurate barcode captures even when the host operating system is set to Thai or non-Latin keyboard layouts.
* **Non-blocking Fast Scan Queue:** Handles burst scanning (2-3 scans/second) with optimistic UI updates and asynchronous backend synchronization.

### 3.2 Phase-based Validation & Hardware Interlocks
* **Free-order Scanning:** Operators can scan and pour ingredients in any order within the active phase.
* **PLC Sequence Interlock:** The PLC hardware restricts recipe progression (e.g., initiating 90°C heating) until all phase ingredients are 100% verified and acknowledged.

### 3.3 Neural Sweet Voice & Audio Cues
* **Bilingual Neural TTS:** Voice prompts (Emma EN / Premawadee TH) provide instant auditory confirmation of scanned materials and weight ranges.
* **Web Audio Oscillators:** Distinct high-frequency confirmation chimes and low-frequency alert buzzers.

### 3.4 Smart Batch Watcher & Shift Reporting
* Automated post-batch evaluation with deduplication buffers to prevent notification spam, compiling clean shift-based executive summaries.

---

## 4. Key API Endpoints Reference
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/plc/plant/{id}/recipe-status` | Live recipe telemetry, active phase, steps, and target weights |
| `GET` | `/production-batches/{id}/logs` | Audit trail of completed steps, timestamps, weights, and operators |
| `POST`| `/auth/switch-operator/{user}` | Instant badge scan operator assignment |
| `GET` | `/production-plans/?status=all` | Global multi-plant production plan schedules |

---

## 5. Deployment & Maintenance
* **Frontend Service:** Systemd unit `xmixing-frontend.service` running on `http://192.168.121.23:3031`
* **Backend Service:** Systemd unit `xmixing-backend.service` running on `http://192.168.121.23:8031`
* **Health Watchdog:** Cron execution of `watchdog_stability.sh` every 5 minutes for automatic memory recovery and process restarts.

---

### 👨‍💻 Maintainer & Engineering Team
* **Prepared & Maintained by:** Piyapong Nuanjan (*Digital Process & Automation Specialist*)
* **Plant Site:** Mitr Phol SP Production Facility
* **Repository:** `git@github.com:x92120/x2512001-mitrPhol-x31-xMixingControl-site.git`
