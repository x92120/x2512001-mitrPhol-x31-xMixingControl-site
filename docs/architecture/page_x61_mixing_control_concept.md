# 🎛️ x61 - Mixing Control Page Concept (Plant 1)

หน้านี้คือ **หัวใจหลักของการดำเนินงาน (Operation Control)** เป็นหน้าจอที่ Operator ใช้คุมเครื่องจักรและตรวจสอบสถานะทุกอย่างระหว่างการผลิต โดยในเฟสนี้เราจะโฟกัสที่ **Plant 1 (Mixing Tank 1)** เป็นหลัก

---

## 1. 🎯 หัวใจหลักของหน้า x61 (Core Concepts)

1. **Safety & Clarity FIRST** : ต้องเห็นค่าสำคัญชัดเจน (อุณหภูมิ, น้ำหนัก) และมีปุ่มฉุกเฉิน (ABORT) ที่เรียกใช้งานได้ทันที
2. **Step-by-Step Handshake** : หน้าเว็บจะเป็นคนจ่ายงาน (Recipe) ทีละบรรทัดให้ PLC และรอจนกว่า PLC จะทำสเตปนั้นเสร็จ แล้วจึงไปต่อ
3. **Actual vs Setpoint Comparison** : โชว์เปรียบเทียบค่าที่ควรจะเป็น (SP) กับค่าที่วัดได้จริงจากเซนเซอร์ตลอดเวลา
4. **Mandatory QC Stop** : ถ้าเป็น Step ที่เกี่ยวกับการเย็นลง (Cooldown/Final) ระบบต้องหยุดให้ Operator กรอกค่า Brix / pH ไม่งั้นไม่ให้จบ Batch

---

## 2. 📐 โครงสร้างหน้าจอ (UI Layout Design)

หน้าจอออกแบบมาให้ Operator เข้าใจง่าย แบ่งเป็นโซนชัดเจน (3 โซนหลัก):

### 🟦 Zone A: Header & Status (ด้านบนสุด)
- วัตถุประสงค์: ข้อมูลแผนการผลิต
- ข้อมูลที่แสดง:
  - ชื่อ SKU และรหัสินค้า (เช่น S77S743200 - Cafe Amazon)
  - หมายเลข Batch และ Target Weight (เช่น 1200kg)
  - เชื่อมต่อ PLC สำเร็จหรือไม่ (แสดงป้าย 🟢 PLC CONNECTED)

### 🟩 Zone B: Live Telemetry Dashboard (ตรงกลางจอ)
- วัตถุประสงค์: แสดงสถานะเครื่องจักร Real-time ทุก 1 วินาที
- ข้อมูลที่แสดง (แบ่งเป็น 4 คอลัมน์):
  1. **🌾 Hopper Scale**: น้ำหนักของสารระเหย หรือสารปรุงแต่งที่รอโหลด
  2. **💧 Mixing Tank (ถังหลัก)**: อุณหภูมิน้ำ, น้ำหนักรวม, ความเร็วใบกวน Agitator
  3. **⚡ High Shear**: ความเร็วใบมีดบดละเอียด และอุณหภูมิมอเตอร์
  4. **🔄 Circulation**: ความเร็ว Flow Pump
- **จุดเด่น**: ในส่วนนี้จะมีป้ายตัวเลขเล็กๆ โชว์คำว่า `SP: 40°C` แปะไว้ข้างๆ `Actual: 42°C` ถ้าอยู่ในเกณฑ์ ±5°C จะเป็นสีเขียว ถ้าเลยเกณฑ์จะเป็นสีส้ม

### 🟨 Zone C: Operation & Command Center (ด้านล่าง)
- วัตถุประสงค์: การควบคุม และบอกพิกัดว่าถึงขั้นไหนแล้ว
- ข้อมูลที่แสดง:
  - **Command Buttons**: 
    - ▶️ `START`: จ่ายงาน Step ปัจจุบันให้ PLC รัน
    - ⏸ `PAUSE`: สั่งให้ PLC ระงับการขยับ ทุกอย่างหยุดหมุน
    - 🛑 `ABORT`: เบรกฉุกเฉิน เคลียร์ระบบ
    - ⏭️ `Force Next Step`: ข้ามสเตปแบบบังคับ (ใช้กรณีฉุกเฉิน/Manual Override)
  - **SKU Step List (Accordion)**: แกะกล่องทีละ Phase (เช่น Phase A1010) แล้วแสดงว่า PLC ตอนนี้บรรทัดไหนติดแถบสีสว่างๆ (Highlight) ให้รู้ว่า "กำลังกวนตัวนี้อยู่นะ"

---

## 3. ⚙️ ลำดับการควบคุมจากหน้า x61 (Operation Flow)

1. **Initiate (โหลดข้อมูล)**: 
   - เมื่อข้ามมาจากหน้า x60 ระบบจะดึง "ทุก Step" ใส่ตารางเก็บไว้
   - เชื่อมต่อ MQTT รอรับค่าจาก Plant 1
2. **Execute (การรันแบบปกติ)**: 
   - Operator กด ▶️ `START`
   - หน้า x61 ส่งข้อมูล *Step ที่ 1 เท่านั้น* ไปที่: `mixing/plant/1/step_cmd`
   - รอรับข้อความ `status: STEP_COMPLETE` จาก PLC (วนลูปแบบนี้จนจบ)
3. **The QC Trap (ขั้นตอนบังคับ)**:
   - เมื่อ Step ไหลไปจนถึงกลุ่ม Cooldown (`x1030`, `x1040`)
   - หน้าจอจะค้าง ไม่ Auto-advance
   - มีกล่อง Input โผล่มาให้กรอก: `Actual Brix [       ]` และ `Actual pH [       ]`
   - ต้องกรอกแล้วกด Save -> ระบบบันทึกลง DB -> ค่อยวิ่งต่อไป
4. **Conclusion (จบงาน)**: 
   - เมื่อถึงบรรทัดสุดท้าย โชว์ข้อความสำเร็จ พิมพ์เอกสารสรุป Batch Report อัตโนมัติ

---

## 4. 🔀 ลอจิกการคุยกับระบบหลังบ้าน (Backend API / Database)

เนื่องจากต้องบันทึกประวัติ (History) หน้า x61 นี้จะเป็นจุดเดียวที่ยิง API ลงฐานข้อมูล:

- **เมื่อทำ Finished 1 Step**: 
  - `POST /api/records/step`
  - Payload: `{ batch_id, step_id, actual_temp_end, duration_seconds }`
- **เมื่อกด Confirm QC Check**:
  - `POST /api/records/qc`
  - Payload: `{ batch_id, phase_id, actual_brix, actual_ph }`
- **เมื่อรันถึง Step สุดท้าย**:
  - `POST /api/batch/complete`

---

## สรุป (Conclusion)
หน้า **x61-MixingControl** ถูกออกแบบให้เป็น "**HMI อัจฉริยะ**" ไม่ใช่แค่หน้าจอมอนิเตอร์ แต่ทำตัวหน้าผู้ป้อนคำสั่งให้ PLC (S7-1200) ทำงานทีละคำสั่ง (Micro-management) ข้อดีคือลดภาระ Memory ของ PLC และช่วยให้ฝั่ง Software เก็บ Snapshot ข้อมูลทุก Step ได้ละเอียดที่สุด
