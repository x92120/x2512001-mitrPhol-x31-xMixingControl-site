<div class="cover-page">
<img src="/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0110-frontEnd/public/x_logo-512.png" class="cover-logo">
<div class="cover-title">คู่มือมาตรฐานการปฏิบัติงาน (Work Instruction)</div>
<div class="cover-subtitle">ระบบควบคุมการผลิต xMixing Control Application</div>

<table class="doc-info">
<tr>
<th>รหัสเอกสาร (Document No.)</th>
<td>WI-PRD-MIX-001</td>
</tr>
<tr>
<th>แก้ไขครั้งที่ (Revision)</th>
<td>03 (เพิ่มรายละเอียดผังงานและลอจิก)</td>
</tr>
<tr>
<th>วันที่บังคับใช้ (Effective Date)</th>
<td>25 มิถุนายน 2026</td>
</tr>
<tr>
<th>หน่วยงาน (Department)</th>
<td>ฝ่ายผลิตและฝ่ายเตรียมวัตถุดิบ</td>
</tr>
</table>
</div>

---

## 1. วัตถุประสงค์และภาพรวมระบบ (Purpose & Overview)
ระบบถูกออกแบบมาเพื่อลดข้อผิดพลาดจากคน (Human Error) ด้วยการทำงานแบบ **"คนเป็นผู้คุมจังหวะ (Monitor & Scan) และเครื่องจักร (PLC) เป็นผู้ลงมือทำ"** 

### 1.1 สรุปหน้าที่ความรับผิดชอบ (Roles & Responsibilities)
<table class="content-table">
<thead>
<tr>
<th width="20%">ผู้รับผิดชอบ</th>
<th width="80%">หน้าที่หลัก (Key Responsibilities)</th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center; font-size: 24px;">🧑‍🔧<br><b>Operator</b></td>
<td>สแกนบาร์โค้ดถุงวัตถุดิบ, กด START/PAUSE เครื่อง, กรอกค่า QC (Brix/pH), และตัดสินใจกด STOP ฉุกเฉิน</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">💻<br><b>xMixing App</b></td>
<td>โหลดสูตรการผลิต แยกย่อยเป็น Step โยนค่า Setpoint ไปที่ PLC, รับสถานะจาก PLC มาบันทึกลง Database (Auto-save) และเช็ค Error Tolerance</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">🎛️<br><b>PLC (S7-1200)</b></td>
<td>อ่านค่าน้ำหนักเครื่องชั่ง, สั่งหมุนปั๊ม/Agitator, เปิดสตรีมทำความร้อน, ควบคุม High Shear ตามคำสั่งในแต่ละ Step</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">📟<br><b>Scanner</b></td>
<td>สแกนเลขบาร์โค้ด ป้องกันการใส่ส่วนผสมผิดถัง (Wrong Bag / Wrong Box)</td>
</tr>
</tbody>
</table>

---

## 2. พจนานุกรมสัญลักษณ์ปุ่มกด (UI Controls Dictionary)

### 2.1 แถบเครื่องมือหลัก (Main Navigation)
<table class="content-table">
<thead>
<tr>
<th width="15%">ไอคอน</th>
<th width="25%">ชื่อเมนู</th>
<th width="60%">หน้าที่การทำงาน</th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center; font-size: 24px;">🏠</td>
<td><strong>HOME</strong></td>
<td>กลับหน้าจอหลักของระบบ</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">📅</td>
<td><strong>PRODUCTION PLAN</strong></td>
<td>เข้าดูแผนการผลิต กดปุ่ม `Select` ที่ Batch สถานะ `Prepared`</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">🏷️</td>
<td><strong>SKU</strong></td>
<td>ตรวจสอบสูตรการผลิต (BOM) และขั้นตอนทั้งหมดของสินค้านั้นๆ</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">⚖️</td>
<td><strong>CHECK FOR PRODUCTION</strong></td>
<td>หน้าจอสำหรับห้องเตรียมวัตถุดิบ ทำการชั่งและกด `Confirm` ทีละตัว</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">🎛️</td>
<td><strong>MIXING CONTROL</strong></td>
<td><strong>[หน้าหลักของ Operator]</strong> เข้าสู่หน้าควบคุมเครื่องผสมและสแกน</td>
</tr>
</tbody>
</table>

### 2.2 แถบควบคุมสถานะเครื่องจักร (Machine Controls)
<table class="content-table">
<thead>
<tr>
<th width="15%">ไอคอน</th>
<th width="85%">หน้าที่การทำงาน (Action)</th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center; font-size: 24px;">▶️</td>
<td><strong>Start:</strong> สั่งให้เครื่องเริ่มทำงาน หรือทำต่อหลังจากที่ระบบถูกสั่ง Hold</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">⏸️</td>
<td><strong>Pause (Hold):</strong> หยุดเครื่องชั่วคราว (PLC จะพักการปั่นและหยุดนับเวลา แต่ไม่ล้างค่า)</td>
</tr>
<tr>
<td style="text-align: center; font-size: 24px;">⏹️</td>
<td><strong>Stop (Abort):</strong> ยกเลิกการทำงานของ Batch <i>(เครื่องจะตัดไฟและล้างค่า ระบบจะพัง Batch ทิ้งทันที)</i></td>
</tr>
</tbody>
</table>

---

## 3. ขั้นตอนการปฏิบัติงานแบบละเอียด (Detailed Procedure)

### ขั้นตอนที่ 1: การเตรียมการ (Preparation)
<span class="step-number">1</span> ไปที่เมนู **CHECK FOR PRODUCTION (x60)** (สำหรับห้องเตรียม)<br>
<span class="step-number">2</span> ค้นหาและชั่งน้ำหนักวัตถุดิบ เมื่อน้ำหนักตรงเป้าหมาย ให้กด `Confirm`<br>
<span class="step-number">3</span> เมื่อ Confirm ครบทุกตัว สถานะจะกลายเป็นสีเขียว <code>Prepared</code>

<div class="screenshot-container">
<img src="/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/wi_screenshots/page_x60.png">
<div class="screenshot-caption">ภาพประกอบ: หน้าจอชั่งตวงยืนยันน้ำหนัก</div>
</div>

### ขั้นตอนที่ 2: เริ่มต้นการผลิตและ Data Flow (Execution)
<span class="step-number">1</span> Operator มาที่หน้า **MIXING CONTROL (x61)** สแกน Job Order ใบสั่งผลิต<br>
<span class="step-number">2</span> ตรวจสอบป้ายมุมบนว่าขึ้น **🟢 PLC CONNECTED**<br>
<span class="step-number">3</span> กดปุ่ม ▶️ **[START]**<br>
<span class="step-number">4</span> <b>แอปจะยิงคำสั่ง Step 1 ไปหา PLC</b> PLC จะดึงน้ำ/ทำความร้อน ทันที หน้าจอแอปจะอัปเดตค่า Actual (RPM, Temp, Weight) จาก PLC <b>ทุกๆ 1 วินาที</b>

<div class="screenshot-container">
<img src="/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/wi_screenshots/page_x61.png">
<div class="screenshot-caption">ภาพประกอบ: หน้าจอหน้าปัดคุมเครื่อง (Mixing Control)</div>
</div>

### ขั้นตอนที่ 3: กฏการสแกนและลอจิกป้องกัน (Scanning Logic & Phase Guard)
เมื่อระบบถึงจังหวะให้เติมวัตถุดิบ (แถบสีเหลือง) Operator ต้องใช้ปืนสแกนยิงบาร์โค้ด
<div class="note-box">
<strong>🔥 รูปแบบการสแกน และ Error ที่อาจพบได้:</strong><br>
1. <b>กรณีปกติตรงเงื่อนไข:</b> ระบบขึ้นเครื่องหมาย ✅ สีเขียว และเครื่องจะทำ Step ถัดไปอัตโนมัติ<br>
2. <b>กรณี ⛔ สแกนผิด Phase:</b> (เช่น หยิบของ p050 มาสแกนตอนที่ระบบรัน p030 อยู่) ระบบจะบล็อก ไม่บันทึกค่า<br>
3. <b>กรณี ⚠️ แจ้งเตือนสีเหลือง:</b> หากเผลอเอาบาร์โค้ด <i>Batch Label</i> มายิงซ้ำ ระบบจะฟ้องว่า 'คุณกำลังสแกนหัวบิลซ้ำ!'<br>
4. <b>กรณี 🚨 "WRONG BOX!" สีแดงใหญ่:</b> ห้ามเด็ดขาด! แปลว่าคุณเอาบาร์โค้ดของวัตถุดิบ Batch อื่น/กล่องอื่น มายิงใส่ถังนี้
</div>

<div class="warning-box">
<strong>★ โหมดสแกนอิสระ (Free-scan: p010 - p049)</strong><br>
ใน Phase เหล่านี้ หากมีสารเติมแต่งหลายชนิด (เช่น สี, กลิ่น, สารกันบูด) คุณสามารถสแกนบาร์โค้ด <b>ชิ้นไหนก่อนก็ได้ใน Phase เดียวกัน</b> แต่ระบบจะไม่ยอมปล่อยให้เครื่องทำงานข้ามไป Phase หน้า จนกว่าคุณจะ <b>สแกนครบทุกชิ้น</b>
</div>

### ขั้นตอนที่ 4: การกรอกค่าคุณภาพ (Manual QC - Brix/pH)
<span class="step-number">1</span> เมื่อทำงานถึง Step การตรวจเช็คคุณภาพ (Phase การ Holding หรือ Cooldown เช่น D1030/D1040)<br>
<span class="step-number">2</span> เครื่องจักรจะ <b>หยุดทำงานชั่วคราว</b> เพื่อรอให้ Operator ดึง Sampling ออกมาวัด<br>
<span class="step-number">3</span> กรอกค่า <b>Brix</b> และ <b>pH</b> ที่วัดได้จริงลงในช่องบน HMI<br>
<span class="step-number">4</span> กด <b>Confirm / Next Step</b> ระบบจึงจะอนุญาตให้ PLC ปล่อยสินค้าผ่านไปยังกระบวนการบรรจุ (Packing)

<div class="screenshot-container">
<img src="/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/wi_screenshots/page_x100.png">
<div class="screenshot-caption">ภาพประกอบ: การตรวจสอบภาพรวมทุก Plant ผ่าน Plant Monitor</div>
</div>

### ขั้นตอนที่ 5: สิ้นสุดกระบวนการ (End Batch)
<span class="step-number">1</span> เมื่อระบบทำงานครบตามจำนวน Step ของสูตร (เช่น ครบ 35/35 steps)<br>
<span class="step-number">2</span> ระบบจะแจ้งเตือน **"🎉 BATCH COMPLETE"**<br>
<span class="step-number">3</span> ข้อมูลการผลิต (เวลา, อุณหภูมิ, วัตถุดิบ, รหัสพนักงาน) จะถูกบันทึกลง Database อัตโนมัติ สามารถดูย้อนหลังได้ในหน้า `x70-Production Report` หรือพริ้นท์ใบ Report แบบ Mitr Phol ได้จากหน้า `x71-Mixing Report`

---

## 4. ตารางการแก้ไขปัญหาเบื้องต้น (Troubleshooting Guide)

<table class="content-table">
<thead>
<tr>
<th width="25%">ปัญหาที่พบหน้าจอ (Symptom)</th>
<th width="35%">สาเหตุเบื้องต้น (Root Cause)</th>
<th width="40%">วิธีการแก้ไขที่ต้องทำ (Action)</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>1. ระบบแจ้งเตือน <span style="color:red">"⛔ สแกนผิด Phase"</span></strong></td>
<td>พนักงานสแกนวัตถุดิบข้ามขั้นตอน (นำวัตถุดิบ Phase ถัดไปมาสแกนก่อน)</td>
<td>เช็คป้าย Label วัตถุดิบว่าตรงกับ Phase บนหน้าจอหรือไม่ หยิบวัตถุดิบที่ถูกต้องมาสแกนใหม่</td>
</tr>
<tr>
<td><strong>2. ระบบขึ้นจอแดงใหญ่ <span style="color:red">"🚨 WRONG BOX!"</span></strong></td>
<td>หยิบวัตถุดิบผิดกล่อง/ผิด Batch อย่างร้ายแรง</td>
<td>หยุดการเติมส่วนผสมทันที! ตรวจสอบว่านำกล่องสินค้าจากล็อตอื่นมาใช้หรือไม่ และกดยกเลิกคำสั่งบนหน้าจอ</td>
</tr>
<tr>
<td><strong>3. สแกนครบทุกตัวแล้ว แต่ "ระบบไม่ยอมไป Step ถัดไป"</strong></td>
<td>PLC Handshake ค้าง หรือ Network หน่วง / รอเช็คเซ็นเซอร์</td>
<td>รอ 3-5 วินาที -> กด Refresh (F5) -> ถ้ายังค้างให้ Supervisor กดปุ่ม <b>⏭️ (Bypass)</b> ที่หน้าจอคุม</td>
</tr>
<tr>
<td><strong>4. ขึ้น <span style="color:orange">"Scan — no volume"</span></strong></td>
<td>สแกนไม่ติดปริมาตร (Volume) อ่านค่า QR Code พลาด</td>
<td>กดเลือกลบรายการที่เพิ่งสแกน แล้วเล็งปืนสแกนใกล้ๆ ให้อ่านชัดๆ อีกครั้ง</td>
</tr>
<tr>
<td><strong>5. ไม่มีป้ายคลัง (SPP/FH) โชว์ที่วัตถุดิบ</strong></td>
<td>ไม่ได้ระบุคลังสินค้าในฐานข้อมูล Master Data (WH=NULL)</td>
<td>ระบบมี Fallback เช็คให้แล้ว หากยังไม่โชว์ป้าย แจ้งฝ่าย IT ให้เติมข้อมูลใน Master Data (อาจส่งผลให้ Free-scan เช็คไม่ได้)</td>
</tr>
<tr>
<td><strong>6. เครื่องขึ้น "PLC OFFLINE" สีเทา</strong></td>
<td>สาย LAN หลุด หรือ Service ฝั่ง Server Backend ดับ</td>
<td>ตรวจสอบปลั๊ก LAN หลังหน้าจอ HMI หากปกติให้แจ้งช่าง Automation เพื่อรีสตาร์ท <code>xmixing-backend.service</code></td>
</tr>
</tbody>
</table>
