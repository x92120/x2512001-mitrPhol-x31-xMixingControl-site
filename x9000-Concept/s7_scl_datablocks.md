# 💻 TIA Portal SCL & DB Code for xMixing S7-1200

เอกสารชุดนี้คือ Source Code ในรูปแบบ SCL (Structured Control Language) สำหรับนำไปใช้ในโปรแกรม TIA Portal โดยตรง ประกอบด้วย Type Definitions (UDT), Data Blocks, และตัวอย่าง Function Block ในการควบคุม Handshake ขาเข้า-ออก

---

## 1. User Data Types (UDTs)
การกำหนด Type ทำให้โครงสร้างตัวแปรใน TIA Portal เป็นระเบียบและเรียกใช้งานซ้ำได้ง่าย

```pascal
TYPE "type_StepCommand"
TITLE = Step Command from Backend/HMI (v2)
VERSION : 0.2
   STRUCT
      Watch_Doc     : Int;          // Watchdog counter
      Plan_ID       : String[20];   // รหัส Plan (เช่น P260411-02-01)
      Batch_ID      : String[20];   // รหัส Batch
      SKU_Name      : String[30];   // ชื่อ SKU
      Phase_ID      : String[10];   // รหัส Phase (เช่น A1010)
      Step_No       : Int;          // ลำดับ Step ปัจจุบัน
      Step_Time     : Int;          // เวลาทำงาน (วินาที)
      Step_Status   : Int;          // 0=Pending, 1=Active, 2=Complete
      Material_ID   : String[20];   // รหัสวัตถุดิบ SAP
      Re_Code       : String[20];   // รหัสผสม/Ingredient
      Target_Weight : Real;         // น้ำหนักที่ต้องการ (kg)
      Temp_SP       : Real;         // Setpoint อุณหภูมิ (°C)
      Temp_Low      : Real;         // Limit ต่ำสุด (°C)
      Temp_High     : Real;         // Limit สูงสุด (°C)
      Agitator_SP   : Real;         // ความเร็วใบกวน (RPM)
      HighShear_SP  : Real;         // ความเร็ว High Shear (RPM)
      PH_Target     : Real;         // ค่า pH เป้าหมาย
      Brix_Target   : Real;         // ค่า Brix เป้าหมาย
      HMI_Command   : Int;          // 0=IDLE, 1=START, 2=PAUSE, 3=ABORT, 9=RESET
      Cmd_NewStep   : Bool;         // Trigger bit จากระบบสั่งงานข้างนอก
   END_STRUCT;
END_TYPE

TYPE "type_RecipeStep"
TITLE = Individual Step Definition (For Array)
VERSION : 0.2
   STRUCT
      Seq           : Int;          // ลำดับที่ในอาร์เรย์ (1, 2, 3, ... 128)
      Phase_No      : Int;          // เลข Phase เช่น 10, 20, 30
      Sub_Step      : Int;          // เลข Step ภายใน Phase เช่น 10, 20, 30
      Action_Code   : String[10];   // รหัส Action (เช่น x10010, x20010)
      Phase_ID      : String[10];   // รหัส Phase (เช่น p0010, p0020)
      Re_Code       : String[20];   // รหัสผสม/Ingredient
      Target_Weight : Real;         // น้ำหนักที่ต้องการ (kg)
      Temp_SP       : Real;         // Setpoint อุณหภูมิ (°C)
      Temp_Low      : Real;         // Limit ต่ำสุด
      Temp_High     : Real;         // Limit สูงสุด
      Agitator_SP   : Real;         // ความเร็วใบกวน (RPM)
      HighShear_SP  : Real;         // ความเร็ว High Shear (RPM)
      Step_Time     : Int;          // เวลาทำงาน (วินาที)
   END_STRUCT;
END_TYPE

// ตัวอย่าง Flat Sequence:
// Seq=1  Phase_No=10 Sub_Step=10  Action_Code="x10010"  (P10 Step 10)
// Seq=2  Phase_No=10 Sub_Step=20  Action_Code="x10020"  (P10 Step 20)
// Seq=3  Phase_No=20 Sub_Step=10  Action_Code="x20010"  (P20 Step 10)
// Seq=4  Phase_No=20 Sub_Step=20  Action_Code="x20020"  (P20 Step 20)
// Seq=5  Phase_No=20 Sub_Step=30  Action_Code="x20030"  (P20 Step 30)
// Seq=6  Phase_No=20 Sub_Step=40  Action_Code="x20040"  (P20 Step 40)

TYPE "type_FullRecipe"
TITLE = Full Recipe Command (All Steps) from Node-RED/HMI
VERSION : 0.2
   STRUCT
      Batch_ID      : String[20];   // รหัส Batch
      SKU_ID        : String[20];   // รหัส SKU
      HMI_Command   : Int;          // 0=IDLE, 1=START, 2=PAUSE, 3=ABORT, 9=RESET
      Total_Steps   : Int;          // จำนวน Step ทั้งหมดใน Recipe นี้ (1-128)
      Active_Step   : Int;          // Pointer ชี้ว่าตอนนี้ต้องทำ Seq ไหน (1-128)
      Cmd_LoadRecipe: Bool;         // Trigger โหลด Recipe ใหม่
      Steps         : Array[1..128] of "type_RecipeStep"; // รองรับสูงสุด 128 Steps
   END_STRUCT;
END_TYPE

TYPE "type_Telemetry"
TITLE = Live Data to Node-RED/HMI
VERSION : 0.1
   STRUCT
      Watchdog       : Int;         // สัญญาณชีพ
      PLC_State      : Int;         // 0=Ready, 1=Run, 2=Hold, 3=Pause, 9=Error
      Current_Step   : Int;         // Step ที่ PLC กำลังทำงาน
      Step_Timer     : Int;         // จับเวลาผ่านไปแล้วกี่วินาที
      MixTank_Temp   : Real;        // อุณหภูมิในถัง
      MixTank_Weight : Real;        // น้ำหนักในถัง
      Agitator_Act   : Real;        // ความเร็วจริงใบกวน
      HighShear_Act  : Real;        // ความเร็วจริง High Shear
      Hopper_Weight  : Real;        // น้ำหนักใน Hopper ย่อย
   END_STRUCT;
END_TYPE

TYPE "type_Handshake"
TITLE = End Step Response
VERSION : 0.1
   STRUCT
      Step_Complete : Bool;         // Pulse แจ้งว่า Step จบแล้วจ้า
      Finished_Step : Int;          // ยืนยันจบ Step เบอร์...
      End_Temp      : Real;         // Snapshot อุณหภูมิ
      End_Weight    : Real;         // Snapshot น้ำหนัก
      Error_Flag    : Bool;         // ถ้ามีการหยุดจาก Alarm
      Error_Code    : Int;          // Error ระหัสไหน
   END_STRUCT;
END_TYPE
```

---

## 2. Data Blocks (DBs)
กำหนด Global DB โดยเรียกใช้ UDT ด้านบน 

```pascal
DATA_BLOCK "DB_STEP_CMD"
TITLE = DB1510 : Command From HMI
{ S7_Optimized_Access := 'FALSE' } // ตั้งเป็น Standard access (เผื่อ Node-RED ต่อแบบ Absolute Address)
AUTHOR : 'AW'
FAMILY : 'MIX'
VERSION : 0.1
NON_RETAIN
   "type_StepCommand"
BEGIN
END_DATA_BLOCK

DATA_BLOCK "DB_FULL_RECIPE"
TITLE = DB1511 : Full Recipe Array From HMI
{ S7_Optimized_Access := 'FALSE' }
AUTHOR : 'AW'
FAMILY : 'MIX'
VERSION : 0.1
NON_RETAIN
   "type_FullRecipe"
BEGIN
END_DATA_BLOCK

DATA_BLOCK "DB_TELEMETRY"
TITLE = DB1512 : Telemetry To HMI
{ S7_Optimized_Access := 'FALSE' }
AUTHOR : 'AW'
FAMILY : 'MIX'
VERSION : 0.1
NON_RETAIN
   "type_Telemetry"
BEGIN
END_DATA_BLOCK

DATA_BLOCK "DB_HANDSHAKE"
TITLE = DB1513 : Step Confirmation To HMI
{ S7_Optimized_Access := 'FALSE' }
AUTHOR : 'AW'
FAMILY : 'MIX'
VERSION : 0.1
NON_RETAIN
   "type_Handshake"
BEGIN
END_DATA_BLOCK
```

---

## 3. Handshake Function Block (FB)
FB หลักที่ทำหน้าที่ประมวลผลสัญญาณรับเข้า และเคลียร์ flag ต่างๆ อย่างปลอดภัย (Safe Pulse/Latch Logic)

```pascal
FUNCTION_BLOCK "FB_Step_Handshake"
TITLE = Step Flow Controller
VERSION : 0.1
   VAR_INPUT
      Reset_All   : Bool;    // กดตอนจะเริ่ม Batch ใหม่หรือล้าง Error
   END_VAR
   
   VAR
      ton_StepDelay  : TON_TIME;  // หน่วงเวลาก่อนตัดจบสเต็ป
      tp_CompletePulse : TP_TIME; // Pulse ออกไปให้ Node-RED (1 วิ)
      Internal_State : Int;       // State Machine ของ FB 
                                  // (0=Idle, 1=Loading, 2=Running, 3=Complete)
   END_VAR

BEGIN
   // -----------------------------------------------------------------
   // 1. รับ Trigger จาก HMI ว่ามี Step ใหม่เข้ามา
   // -----------------------------------------------------------------
   IF "DB_STEP_CMD".Cmd_NewStep AND (#Internal_State = 0 OR #Internal_State = 3) THEN
      // นำข้อมูลเข้าสู่สถานะเริ่มทำงาน
      "DB_TELEMETRY".Current_Step := "DB_STEP_CMD".Step_No;
      "DB_TELEMETRY".Step_Timer := 0;
      "DB_TELEMETRY".PLC_State := 1; // Running
      
      // ปัด Flag รับทราบ ให้ Node-RED รู้ว่ารับแล้ว
      "DB_STEP_CMD".Cmd_NewStep := FALSE; 
      
      // อัพสถานะในเครื่อง
      #Internal_State := 2; // ย้ายไปสถานะทำงานเครื่องขุมพลัง
   END_IF;

   
   // -----------------------------------------------------------------
   // 2. จำลองการประมวลผล (หรือทำงานร่วมกับ PID / Timer)
   // -----------------------------------------------------------------
   IF #Internal_State = 2 THEN
      
      // >>>> ตรงนี้คือลอจิกคุมเครื่องของจริงที่จะอ่าน Temp_SP, RPM เอาไปคุม Inverter <<<<
      
      // ตรวจจับเงื่อนไขเวลา
      IF "DB_STEP_CMD".Step_Time > 0 AND "DB_TELEMETRY".Step_Timer >= "DB_STEP_CMD".Step_Time THEN
         #Internal_State := 3; // เวลาหมด แปลว่า Step สมบูรณ์
      END_IF;
   END_IF;


   // -----------------------------------------------------------------
   // 3. ปิดจบและส่ง Status ให้ Node-RED 
   // -----------------------------------------------------------------
   IF #Internal_State = 3 THEN
      // 3.1 บันทึกค่า Snapshot ตอนจบ
      "DB_HANDSHAKE".Finished_Step := "DB_TELEMETRY".Current_Step;
      "DB_HANDSHAKE".End_Temp      := "DB_TELEMETRY".MixTank_Temp;
      "DB_HANDSHAKE".End_Weight    := "DB_TELEMETRY".MixTank_Weight;
      
      // 3.2 สร้าง Pulse (Pulse 1 วินาที ให้ Node-RED แน่ใจว่าจะอ่านทัน)
      #tp_CompletePulse(IN := TRUE, PT := T#1s);
      "DB_HANDSHAKE".Step_Complete := #tp_CompletePulse.Q;
      
      // 3.3 เมื่อจบ Pulse แล้ว เปลี่ยนกลับไปรอคำสั่งถัดไป
      IF NOT #tp_CompletePulse.Q THEN
         #tp_CompletePulse(IN := FALSE, PT := T#1s); // เคลียร์ Time
         #Internal_State := 0; // กลับไปช่อง IDLE รอรับ Cmd_NewStep อีกครั้ง
         "DB_TELEMETRY".PLC_State := 0; // Ready
      END_IF;
   END_IF;


   // -----------------------------------------------------------------
   // X. Reset ทั้งระบบ
   // -----------------------------------------------------------------
   IF #Reset_All OR "DB_STEP_CMD".HMI_Command = 3 THEN // HMI_Command 3 = Abort
      #Internal_State := 0;
      "DB_TELEMETRY".PLC_State := 0;
      "DB_STEP_CMD".Cmd_NewStep := FALSE;
      "DB_HANDSHAKE".Step_Complete := FALSE;
      #tp_CompletePulse(IN := FALSE, PT := T#1s);
   END_IF;

END_FUNCTION_BLOCK
```

---

## สรุปการตั้งค่าบน TIA Portal:
1. สร้าง UDT 3 ตัวก่อน
2. สร้าง Data Block (`DB1510`, `DB1512`, `DB1513`) และคลุม UDT
3. **ข้อควรระวังสำคัญ:** ถ้าใช้ Node-RED อ่านผ่าน `s7-comm` หรือโปรโตคอล S7 ควรกดคลิกขวาที่ Data block -> `Properties` -> เอาสัญลักษณ์ติกถูกหน้า `Optimized block access` ออก เพื่อให้ Address มีค่าพิกัดแน่นอน (เช่น `DB1510.DBW0`) Node-RED จะเห็นค่าถูกต้อง
4. ให้ฝังตัวแปรเพิ่มใน `OB1` หรือ Time Interrupt OB (ทุก 1 วิ) ไว้คอยบวก `DB_TELEMETRY.Watchdog` และ `DB_TELEMETRY.Step_Timer`
