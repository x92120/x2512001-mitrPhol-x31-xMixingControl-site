<template>
  <q-page class="shift-page bg-grey-2" style="min-height: 100vh; padding-bottom: 40px;">
    <!-- ═══════════════════════════════════════════════════════════════ -->
    <!-- 🔝 Top Bar / Header -->
    <!-- ═══════════════════════════════════════════════════════════════ -->
    <div class="top-nav bg-white q-px-lg q-py-sm row items-center no-wrap shadow-1" style="border-bottom: 1px solid #e8e0f0; gap: 12px; flex-wrap: wrap;">
      <div class="row items-center q-gutter-x-sm">
        <q-icon name="assignment" size="28px" color="primary" />
        <div>
          <div class="text-subtitle1 text-weight-bold text-grey-9" style="letter-spacing: -0.3px; line-height: 1.2;">
            {{ isThai ? "E-Logbook & ส่งมอบกะ" : "E-Logbook & Shift Handover" }}
          </div>
          <div class="text-caption text-grey-6" style="font-size: 11px;">
            {{ isThai ? "สมุดบันทึกส่งมอบงานประจำกะดิจิทัล" : "Digital Shift Handover & Operational Logbook" }}
          </div>
        </div>
      </div>

      <!-- Current Active / Viewing Shift Badge -->
      <q-chip dense :color="isViewingToday ? 'purple-1' : 'blue-1'" :text-color="isViewingToday ? 'purple-9' : 'blue-9'" class="q-ml-sm text-weight-bold" icon="schedule">
        <span v-if="isViewingToday" class="text-caption text-purple-9 q-mr-xs">{{ isThai ? 'กะปัจจุบัน:' : 'LIVE:' }}</span>
        <span v-else class="text-caption text-blue-9 q-mr-xs">{{ isThai ? 'กะของวันที่:' : 'VIEWING:' }}</span>
        {{ currentShiftLabel }}
        <span class="q-ml-xs text-deep-purple text-weight-bolder" v-if="isViewingToday && currentShiftInfo?.minutes_remaining">
          ({{ isThai ? 'เหลือ ' + currentShiftInfo.minutes_remaining + ' น.' : currentShiftInfo.minutes_remaining + 'm left' }})
        </span>
      </q-chip>

      <q-space />

      <!-- Plant Selector -->
      <div class="row items-center q-gutter-x-xs">
        <span class="text-caption text-grey-7 text-weight-bold">PLANT:</span>
        <q-btn-toggle
          v-model="selectedPlant"
          :options="[{label:'Plant 1',value:1},{label:'Plant 2',value:2},{label:'Plant 3',value:3}]"
          dense unelevated rounded
          color="grey-2" text-color="grey-8"
          toggle-color="primary" toggle-text-color="white"
          size="sm"
          @update:model-value="loadShiftData"
        />
      </div>

      <!-- Shift Type Selector -->
      <div class="row items-center q-gutter-x-xs">
        <span class="text-caption text-grey-7 text-weight-bold">{{ isThai ? 'กะ:' : 'SHIFT:' }}</span>
        <q-btn-toggle
          v-model="selectedShift"
          :options="shiftOptions"
          dense unelevated rounded
          color="grey-2" text-color="grey-8"
          toggle-color="primary" toggle-text-color="white"
          size="sm"
          @update:model-value="loadShiftData"
        />
      </div>

      <!-- Shift Date -->
      <q-input
        v-model="selectedDate"
        type="date"
        dense outlined
        bg-color="white"
        style="width: 145px; font-size: 12px;"
        @update:model-value="loadShiftData"
      />

      <!-- Action Buttons -->
      <div class="row items-center q-gutter-x-sm">
        <q-btn
          unelevated
          dense
          color="positive"
          icon="save"
          :label="isThai ? 'บันทึกร่าง' : 'Save Draft'"
          class="q-px-sm text-weight-bold"
          size="sm"
          :loading="savingDraft"
          @click="saveHandover('Draft')"
        />
        <q-btn
          unelevated
          dense
          color="primary"
          icon="email"
          :label="isThai ? 'ส่ง EMAIL สรุป' : 'Email Summary'"
          class="q-px-sm text-weight-bold"
          size="sm"
          @click="openEmailDialog"
        />
        <q-btn
          flat
          round
          dense
          color="primary"
          icon="refresh"
          size="sm"
          @click="loadShiftData"
        >
          <q-tooltip>{{ isThai ? 'รีเฟรชข้อมูล' : 'Refresh Data' }}</q-tooltip>
        </q-btn>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════ -->
    <!-- 📑 Main Content Tabs -->
    <!-- ═══════════════════════════════════════════════════════════════ -->
    <div class="q-px-lg q-pt-md">
      <q-tabs
        v-model="activeTab"
        dense
        align="left"
        class="bg-white text-grey-7 rounded-borders shadow-1 q-mb-md"
        active-color="primary"
        indicator-color="primary"
        active-bg-color="purple-1"
        style="border: 1px solid #e8e0f0; border-radius: 8px;"
      >
        <q-tab name="kpis" icon="analytics" :label="isThai ? 'ภาพรวม & ยอดผลิต' : 'Overview & Yield'" />
        <q-tab name="issues" icon="warning" :label="isThai ? 'ปัญหาเครื่องจักร & ซ่อมบำรุง' : 'Machine Issues & Maintenance'">
          <q-badge v-if="openIssuesCount > 0" color="red-6" floating rounded>{{ openIssuesCount }}</q-badge>
        </q-tab>
        <q-tab name="chemicals" icon="science" :label="isThai ? 'สารเคมีเฝ้าระวัง' : 'Chemical Watchlist'" />
        <q-tab name="handover" icon="how_to_reg" :label="isThai ? 'ส่งมอบ & เซ็นรับกะ (Sign-off)' : 'Handover & Sign-Off'" />
        <q-tab name="history" icon="history" :label="isThai ? 'ประวัติส่งกะย้อนหลัง' : 'Handover History'" />
      </q-tabs>

      <!-- ───────────────────────────────────────────────────────────── -->
      <!-- TAB 1: 📊 KPIs & Batches -->
      <!-- ───────────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'kpis'">
        <!-- KPI Metric Cards Grid -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-sm-6 col-md-3">
            <q-card flat bordered class="bg-white shadow-1 kpi-card" style="border-radius: 8px; border: 1px solid #e8e0f0;">
              <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
                <span class="text-caption text-grey-7 text-weight-bold">{{ isThai ? 'BATCHES สำเร็จ' : 'COMPLETED BATCHES' }}</span>
                <q-icon name="check_circle" color="green-7" size="24px" />
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-h4 text-weight-bolder text-green-7">
                  {{ shiftKpis.completed_batches || 0 }}
                  <span class="text-body2 text-grey-6">/ {{ shiftKpis.total_batches || 0 }}</span>
                </div>
                <div class="text-caption text-grey-6 q-mt-xs">
                  {{ isThai ? 'กำลังผลิต: ' + (shiftKpis.running_batches || 0) + ' Batch' : 'In Production: ' + (shiftKpis.running_batches || 0) + ' Batches' }}
                </div>
              </q-card-section>
            </q-card>
          </div>

          <div class="col-12 col-sm-6 col-md-3">
            <q-card flat bordered class="bg-white shadow-1 kpi-card" style="border-radius: 8px; border: 1px solid #e8e0f0;">
              <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
                <span class="text-caption text-grey-7 text-weight-bold">{{ isThai ? 'ยอดผลิตรวม (YIELD)' : 'TOTAL YIELD' }}</span>
                <q-icon name="scale" color="teal-7" size="24px" />
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-h4 text-weight-bolder text-teal-7">
                  {{ formatNumber(shiftKpis.total_volume_kg || 0) }}
                  <span class="text-body2 text-grey-6">kg</span>
                </div>
                <div class="text-caption text-grey-6 q-mt-xs">
                  {{ isThai ? 'เป้าหมาย: ' + formatNumber(shiftKpis.target_volume_kg || 0) + ' kg' : 'Target: ' + formatNumber(shiftKpis.target_volume_kg || 0) + ' kg' }}
                </div>
              </q-card-section>
            </q-card>
          </div>

          <div class="col-12 col-sm-6 col-md-3">
            <q-card flat bordered class="bg-white shadow-1 kpi-card" style="border-radius: 8px; border: 1px solid #e8e0f0;">
              <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
                <span class="text-caption text-grey-7 text-weight-bold">{{ isThai ? 'OEE ประจำกะ' : 'SHIFT OEE' }}</span>
                <q-icon name="speed" color="deep-purple-7" size="24px" />
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-h4 text-weight-bolder text-deep-purple-7">
                  {{ shiftKpis.oee_pct || 0 }}%
                </div>
                <div class="text-caption text-grey-6 q-mt-xs">
                  Availability: {{ shiftKpis.availability_pct || 0 }}% | Quality: {{ shiftKpis.quality_pct || 0 }}%
                </div>
              </q-card-section>
            </q-card>
          </div>

          <div class="col-12 col-sm-6 col-md-3">
            <q-card flat bordered class="bg-white shadow-1 kpi-card" style="border-radius: 8px; border: 1px solid #e8e0f0;">
              <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
                <span class="text-caption text-grey-7 text-weight-bold">{{ isThai ? 'DOWNTIME รวม' : 'TOTAL DOWNTIME' }}</span>
                <q-icon name="timer_off" color="deep-orange-7" size="24px" />
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-h4 text-weight-bolder text-deep-orange-7">
                  {{ shiftKpis.downtime_mins || 0 }}
                  <span class="text-body2 text-grey-6">{{ isThai ? 'นาที' : 'mins' }}</span>
                </div>
                <div class="text-caption text-grey-6 q-mt-xs">
                  {{ isThai ? 'ปัญหาเปิดอยู่: ' + openIssuesCount + ' รายการ' : 'Open Issues: ' + openIssuesCount }}
                </div>
              </q-card-section>
            </q-card>
          </div>
        </div>

        <!-- Batches Produced in this Shift Table -->
        <q-card flat bordered class="bg-white shadow-1 q-pa-md" style="border-radius: 8px; border: 1px solid #e8e0f0;">
          <div class="row items-center justify-between q-mb-md">
            <div class="row items-center q-gutter-x-sm">
              <q-icon name="view_list" size="22px" color="primary" />
              <span class="text-subtitle1 text-weight-bold text-grey-9">
                {{ isThai ? 'รายการ Batch ที่ผลิตในกะนี้ (Plant ' + selectedPlant + ')' : 'Shift Production Batches (Plant ' + selectedPlant + ')' }}
              </span>
            </div>
            <q-badge color="blue-1" text-color="blue-9" style="font-size: 12px; padding: 4px 8px;">
              {{ isThai ? 'ช่วงเวลา: ' : 'Time: ' }}{{ shiftData?.time_range || '-' }}
            </q-badge>
          </div>

          <q-table
            :rows="shiftBatches"
            :columns="batchColumns"
            row-key="batch_id"
            dense
            flat
            bordered
            :loading="loadingData"
            class="bg-white app-table"
            :no-data-label="isThai ? 'ไม่มีข้อมูล Batch ในช่วงเวลากะนี้' : 'No batch data recorded for this shift'"
          >
            <template v-slot:body-cell-status="props">
              <q-td :props="props">
                <q-chip
                  dense
                  size="sm"
                  :color="getStatusColor(props.value)"
                  text-color="white"
                  class="text-weight-bold"
                >
                  {{ props.value }}
                </q-chip>
              </q-td>
            </template>
            <template v-slot:body-cell-batch_size="props">
              <q-td :props="props">
                {{ formatNumber(props.value) }} kg
              </q-td>
            </template>
          </q-table>
        </q-card>
      </div>

      <!-- ───────────────────────────────────────────────────────────── -->
      <!-- TAB 2: ⚠️ Machinery Issues & Maintenance -->
      <!-- ───────────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'issues'">
        <q-card flat bordered class="bg-white shadow-1 q-pa-md q-mb-md" style="border-radius: 8px; border: 1px solid #e8e0f0;">
          <div class="row items-center justify-between q-mb-md">
            <div>
              <div class="text-subtitle1 text-weight-bold text-grey-9 row items-center q-gutter-x-sm">
                <q-icon name="build_circle" color="orange-8" size="22px" />
                <span>{{ isThai ? 'บันทึกปัญหาเครื่องจักร & การซ่อมบำรุง (Maintenance Log)' : 'Machine Issues & Maintenance Log' }}</span>
              </div>
              <div class="text-caption text-grey-6">
                {{ isThai ? 'บันทึกรายการปัญหาเครื่องที่รอซ่อม เพื่อส่งต่อให้ช่างและกะถัดไปรับทราบ' : 'Log equipment issues and pending repairs for maintenance and incoming shift.' }}
              </div>
            </div>
            <q-btn
              color="primary"
              icon="add"
              :label="isThai ? 'แจ้งปัญหาเครื่องจักร' : 'Report New Issue'"
              dense unelevated
              class="q-px-md text-weight-bold"
              @click="openAddIssueDialog"
            />
          </div>

          <!-- Issues Cards Grid -->
          <div v-if="issuesList.length > 0" class="row q-col-gutter-md">
            <div v-for="iss in issuesList" :key="iss.id" class="col-12 col-md-6">
              <q-card flat bordered class="bg-white q-pa-md issue-card shadow-1" :class="'border-' + iss.severity?.toLowerCase()" style="border-radius: 8px; border: 1px solid #e8e0f0;">
                <div class="row items-center justify-between no-wrap">
                  <div class="row items-center q-gutter-x-sm">
                    <q-chip dense :color="getSeverityColor(iss.severity)" text-color="white" size="xs" class="text-weight-bolder">
                      {{ iss.severity }}
                    </q-chip>
                    <span class="text-subtitle2 text-weight-bold text-primary">{{ iss.machine_tag }}</span>
                  </div>
                  <q-chip dense :color="getIssueStatusColor(iss.status)" text-color="white" size="xs">
                    {{ iss.status }}
                  </q-chip>
                </div>

                <div class="text-body2 text-weight-bold text-grey-9 q-mt-sm">{{ iss.title }}</div>
                <div class="text-caption text-grey-7 q-mt-xs" style="min-height: 36px;">
                  {{ iss.description || (isThai ? 'ไม่มีรายละเอียดเพิ่มเติม' : 'No additional details provided.') }}
                </div>

                <q-separator class="q-my-sm" />

                <div class="row items-center justify-between text-caption text-grey-6">
                  <div>
                    <q-icon name="person" size="14px" /> {{ isThai ? 'ผู้แจ้ง: ' : 'Reported by: ' }}<span class="text-grey-9">{{ iss.reported_by || 'Operator' }}</span>
                    <span v-if="iss.assigned_to" class="q-ml-sm">
                      <q-icon name="engineering" size="14px" /> {{ isThai ? 'ผู้รับผิดชอบ: ' : 'Assigned: ' }}<span class="text-grey-9">{{ iss.assigned_to }}</span>
                    </span>
                  </div>
                  <div class="row q-gutter-x-xs">
                    <q-btn
                      v-if="iss.status !== 'Resolved'"
                      flat dense size="xs" color="positive" icon="check" :label="isThai ? 'แก้แล้ว' : 'Resolve'"
                      @click="resolveIssue(iss.id)"
                    />
                    <q-btn flat dense size="xs" color="grey-7" icon="edit" @click="editIssue(iss)" />
                  </div>
                </div>
              </q-card>
            </div>
          </div>
          <div v-else class="text-center q-pa-xl text-grey-5">
            <q-icon name="task_alt" size="48px" color="positive" class="q-mb-sm" /><br>
            <span class="text-weight-bold text-grey-7">{{ isThai ? 'ไม่มีปัญหาเครื่องจักรค้างในระบบ (All Systems Normal)' : 'No open equipment issues in system (All Systems Normal)' }}</span>
          </div>
        </q-card>
      </div>

      <!-- ───────────────────────────────────────────────────────────── -->
      <!-- TAB 3: 🧪 Chemical & Material Watchlist -->
      <!-- ───────────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'chemicals'">
        <q-card flat bordered class="bg-white shadow-1 q-pa-md" style="border-radius: 8px; border: 1px solid #e8e0f0;">
          <div class="row items-center justify-between q-mb-md">
            <div>
              <div class="text-subtitle1 text-weight-bold text-grey-9 row items-center q-gutter-x-sm">
                <q-icon name="science" color="teal-7" size="22px" />
                <span>{{ isThai ? 'รายการสารเคมี & วัตถุดิบเฝ้าระวัง (Chemical Low-Stock Watchlist)' : 'Critical Raw Materials & Chemical Watchlist' }}</span>
              </div>
              <div class="text-caption text-grey-6">
                {{ isThai ? 'เตือนรายการสารเคมีที่สต็อกเหลือน้อย หรือต้องเตรียมเบิกล่วงหน้าสำหรับกะถัดไป' : 'Monitor low-stock raw materials or advance requisition requests for the next shift.' }}
              </div>
            </div>
            <q-btn
              color="teal-7"
              icon="add"
              :label="isThai ? 'เพิ่มรายการเฝ้าระวัง' : 'Add Watchlist Item'"
              dense unelevated
              class="q-px-md text-weight-bold"
              @click="openAddMaterialDialog"
            />
          </div>

          <q-table
            :rows="materialAlerts"
            :columns="materialColumns"
            row-key="ingredient_name"
            dense flat bordered
            class="bg-white app-table"
            :no-data-label="isThai ? 'ไม่มีรายการสารเคมีเฝ้าระวังในกะนี้' : 'No chemical alerts recorded for this shift'"
          >
            <template v-slot:body-cell-current_stock="props">
              <q-td :props="props" class="text-weight-bold" :class="props.value <= props.row.min_threshold ? 'text-negative' : 'text-positive'">
                {{ formatNumber(props.value) }} {{ props.row.unit }}
              </q-td>
            </template>
            <template v-slot:body-cell-min_threshold="props">
              <q-td :props="props">
                {{ formatNumber(props.value) }} {{ props.row.unit }}
              </q-td>
            </template>
            <template v-slot:body-cell-actions="props">
              <q-td :props="props">
                <q-btn flat dense round icon="delete" color="negative" size="xs" @click="removeMaterialAlert(props.rowIndex)" />
              </q-td>
            </template>
          </q-table>
        </q-card>
      </div>

      <!-- ───────────────────────────────────────────────────────────── -->
      <!-- TAB 4: ✍️ Digital Handover & Sign-off -->
      <!-- ───────────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'handover'">
        <div class="row q-col-gutter-md">
          <!-- Left: Handover Checklist & Outgoing Sign-off -->
          <div class="col-12 col-md-6">
            <q-card flat bordered class="bg-white shadow-1 q-pa-md" style="border-radius: 8px; border: 1px solid #e8e0f0; height: 100%;">
              <div class="text-subtitle1 text-weight-bold text-primary row items-center q-gutter-x-sm q-mb-sm">
                <q-icon name="checklist" size="22px" />
                <span>{{ isThai ? '1. รายการตรวจสอบก่อนส่งมอบ (Shift Checklist)' : '1. Pre-Handover Checklist (Shift Checklist)' }}</span>
              </div>

              <div class="q-gutter-y-xs q-mb-md">
                <q-checkbox v-model="checklist.tank_cleaned" :label="isThai ? 'ล้างถังผสม / ท่อทางเรียบร้อย (CIP / Flush OK)' : 'Mixer Tank & Piping Cleaned (CIP / Flush OK)'" color="primary" class="text-grey-9 text-weight-medium" />
                <q-checkbox v-model="checklist.area_5s" :label="isThai ? 'ทำความสะอาดพื้นที่ทำงาน 5ส เรียบร้อย' : 'Work Area Cleaned & 5S Maintained'" color="primary" class="text-grey-9 text-weight-medium" />
                <q-checkbox v-model="checklist.safety_normal" :label="isThai ? 'ระบบความปลอดภัย / Emergency Switch อยู่ในสภาพปกติ' : 'Safety System & Emergency Switch Normal'" color="primary" class="text-grey-9 text-weight-medium" />
                <q-checkbox v-model="checklist.waste_disposed" :label="isThai ? 'ทิ้งกาก/ของเสียและจัดเก็บถุงสารเคมีเรียบร้อย' : 'Waste Disposed & Raw Material Bags Stored Properly'" color="primary" class="text-grey-9 text-weight-medium" />
              </div>

              <q-separator class="q-my-md" />

              <div class="text-subtitle1 text-weight-bold text-primary row items-center q-gutter-x-sm q-mb-xs">
                <q-icon name="edit_note" size="22px" />
                <span>{{ isThai ? '2. บันทึกข้อความส่งมอบ (Outgoing Notes)' : '2. Outgoing Shift Handover Notes' }}</span>
              </div>
              <q-input
                v-model="outgoingNotes"
                type="textarea"
                rows="4"
                outlined dense
                bg-color="white"
                :placeholder="isThai ? 'ระบุสิ่งที่ต้องการเน้นย้ำ หรือฝากงานให้กะถัดไป...' : 'Enter critical notes, pending tasks, or instructions for next shift...'"
                class="q-mb-md"
              />

              <div class="row items-center justify-between">
                <div class="text-caption text-grey-7">
                  {{ isThai ? 'ผู้ส่งมอบกะ: ' : 'Outgoing Operator: ' }}<strong class="text-grey-9">{{ currentUser?.full_name || currentUser?.username || 'Operator' }}</strong>
                </div>
                <q-btn
                  unelevated
                  color="primary"
                  icon="how_to_reg"
                  :label="isThai ? 'ลงชื่อยืนยันส่งมอบกะ (Submit)' : 'Submit Shift Handover (SUBMIT)'"
                  class="text-weight-bold"
                  :loading="savingDraft"
                  @click="saveHandover('Submitted')"
                />
              </div>
            </q-card>
          </div>

          <!-- Right: Incoming Operator Acknowledge (QR Badge / Sign) -->
          <div class="col-12 col-md-6">
            <q-card flat bordered class="bg-white shadow-1 q-pa-md" style="border-radius: 8px; border: 1px solid #e8e0f0; height: 100%;">
              <div class="text-subtitle1 text-weight-bold text-deep-purple-8 row items-center q-gutter-x-sm q-mb-sm">
                <q-icon name="qr_code_scanner" size="22px" />
                <span>{{ isThai ? '3. การรับมอบงานของกะใหม่ (Incoming Sign-off)' : '3. Incoming Shift Sign-Off' }}</span>
              </div>

              <!-- Status Banner -->
              <div class="q-pa-md rounded-borders q-mb-md" :class="handoverRecord?.status === 'Acknowledged' ? 'bg-green-1 border-green text-green-9' : 'bg-grey-2 border-grey text-grey-8'" style="border: 1px solid #e0e0e0;">
                <div class="row items-center justify-between">
                  <span class="text-weight-bold">{{ isThai ? 'สถานะเอกสารส่งกะ:' : 'Handover Document Status:' }}</span>
                  <q-chip dense :color="handoverRecord?.status === 'Acknowledged' ? 'green-7' : 'amber-8'" text-color="white" class="text-weight-bold">
                    {{ handoverRecord?.status || 'Draft' }}
                  </q-chip>
                </div>
                <div v-if="handoverRecord?.acknowledged_at" class="text-caption text-green-9 q-mt-xs">
                  {{ isThai ? '✅ รับมอบแล้วโดย: ' : '✅ Acknowledged by: ' }}<strong>{{ handoverRecord.incoming_operator_name }}</strong> {{ isThai ? 'เมื่อ ' : 'at ' }}{{ handoverRecord.acknowledged_at }}
                </div>
                <div v-else class="text-caption text-amber-9 q-mt-xs text-weight-medium">
                  {{ isThai ? '⏳ รอกะถัดไปลงชื่อรับมอบงาน' : '⏳ Awaiting incoming shift sign-off' }}
                </div>
              </div>

              <div v-if="handoverRecord?.status !== 'Acknowledged'">
                <div class="text-body2 text-grey-7 q-mb-sm">
                  {{ isThai ? 'สำหรับ Operator กะใหม่: สแกน QR Badge พนักงาน หรือกดปุ่มด้านล่างเพื่อเซ็นรับมอบกะ' : 'For Next Shift Operator: Scan your QR Badge or click the button below to sign off' }}
                </div>

                <!-- QR Badge Fast Scan Box -->
                <div class="badge-scan-box q-pa-md q-mb-md text-center" style="border-radius: 10px; background: #f8f6fc; border: 2px dashed #b39ddb;">
                  <q-icon name="badge" size="36px" color="deep-purple-6" class="q-mb-xs" />
                  <div class="text-subtitle2 text-weight-bold text-deep-purple-8">
                    {{ isThai ? 'แตะบัตร QR Badge เพื่อรับกะทันที' : 'Tap / Scan QR Badge to Sign Off' }}
                  </div>
                  <q-input
                    ref="handoverBadgeRef"
                    v-model="badgeInputHandover"
                    outlined dense
                    placeholder="Waiting for RFID/QR scan..."
                    bg-color="white"
                    class="q-mt-sm scan-input"
                    @keyup.enter="handleBadgeAcknowledge"
                  >
                    <template v-slot:prepend><q-icon name="qr_code" color="deep-purple-6" /></template>
                  </q-input>
                </div>

                <q-btn
                  outline
                  color="deep-purple-8"
                  icon="verified"
                  :label="isThai ? 'ลงชื่อรับมอบงานแบบระบุชื่อ (Manual Sign)' : 'Manual Shift Sign-Off (MANUAL SIGN)'"
                  class="full-width text-weight-bold q-py-sm"
                  @click="showAcknowledgeDialog = true"
                />
              </div>
            </q-card>
          </div>
        </div>
      </div>

      <!-- ───────────────────────────────────────────────────────────── -->
      <!-- TAB 5: 📜 Handover History & Search -->
      <!-- ───────────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'history'">
        <q-card flat bordered class="bg-white shadow-1 q-pa-md" style="border-radius: 8px; border: 1px solid #e8e0f0;">
          <div class="row items-center justify-between q-mb-md">
            <div class="text-subtitle1 text-weight-bold text-grey-9 row items-center q-gutter-x-sm">
              <q-icon name="history" color="primary" size="22px" />
              <span>{{ isThai ? 'ประวัติการส่งมอบงานย้อนหลัง (Handover Archive)' : 'Shift Handover History Archive' }}</span>
            </div>
            <q-btn flat dense icon="refresh" color="primary" :label="isThai ? 'โหลดใหม่' : 'Reload'" @click="loadHistoryList" size="sm" />
          </div>

          <q-table
            :rows="historyList"
            :columns="historyColumns"
            row-key="id"
            dense flat bordered
            :loading="loadingHistory"
            class="bg-white app-table"
            :no-data-label="isThai ? 'ไม่มีประวัติการส่งกะ' : 'No handover records found'"
          >
            <template v-slot:body-cell-status="props">
              <q-td :props="props">
                <q-chip dense size="xs" :color="props.value === 'Acknowledged' ? 'green-7' : 'amber-8'" text-color="white" class="text-weight-bold">
                  {{ props.value }}
                </q-chip>
              </q-td>
            </template>
            <template v-slot:body-cell-actions="props">
              <q-td :props="props">
                <q-btn flat dense size="xs" color="primary" icon="visibility" :label="isThai ? 'ดูสรุป' : 'View Details'" @click="viewHistoryDetail(props.row.id)" />
              </q-td>
            </template>
          </q-table>
        </q-card>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════ -->
    <!-- 💬 Dialogs & Modals -->
    <!-- ═══════════════════════════════════════════════════════════════ -->

    <!-- Add Issue Dialog -->
    <q-dialog v-model="showIssueDialog">
      <q-card class="bg-white text-grey-9" style="min-width: 440px; border-radius: 10px; border: 1px solid #e8e0f0;">
        <q-card-section class="bg-primary text-white q-py-sm row items-center justify-between">
          <span class="text-subtitle1 text-weight-bold">⚠️ {{ isThai ? 'แจ้งปัญหาเครื่องจักร / ซ่อมบำรุง' : 'Report Machine Issue / Maintenance' }}</span>
          <q-btn flat round dense icon="close" v-close-popup size="sm" />
        </q-card-section>
        <q-card-section class="q-pa-md q-gutter-y-sm">
          <q-input v-model="issueForm.machine_tag" :label="isThai ? 'รหัสเครื่องจักร (Machine Tag / Tank)' : 'Machine Tag / Tank'" dense outlined bg-color="white" placeholder="e.g. Mixer Tank 1, Valve Steam A" />
          <q-input v-model="issueForm.title" :label="isThai ? 'หัวข้อปัญหา' : 'Issue Title'" dense outlined bg-color="white" :placeholder="isThai ? 'เช่น วาล์วปิดไม่สนิท, มอเตอร์มีเสียงดัง' : 'e.g. Steam valve leak, motor vibration'" />
          <q-select v-model="issueForm.severity" :options="['Low', 'Medium', 'High', 'Critical']" :label="isThai ? 'ระดับความเร่งด่วน' : 'Severity Level'" dense outlined bg-color="white" />
          <q-input v-model="issueForm.description" :label="isThai ? 'รายละเอียดอาการ' : 'Description / Symptom'" type="textarea" rows="3" dense outlined bg-color="white" />
          <q-input v-model="issueForm.assigned_to" :label="isThai ? 'มอบหมายให้ (ช่าง/ทีม)' : 'Assigned To (Technician / Team)'" dense outlined bg-color="white" :placeholder="isThai ? 'เช่น ทีม Maintenance กะบ่าย' : 'e.g. Maintenance Team B'" />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat :label="isThai ? 'ยกเลิก' : 'Cancel'" color="grey-7" v-close-popup />
          <q-btn unelevated :label="isThai ? 'บันทึกปัญหา' : 'Save Issue'" color="primary" @click="submitIssue" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Add Material Watchlist Dialog -->
    <q-dialog v-model="showMaterialDialog">
      <q-card class="bg-white text-grey-9" style="min-width: 400px; border-radius: 10px; border: 1px solid #e8e0f0;">
        <q-card-section class="bg-teal-8 text-white q-py-sm row items-center justify-between">
          <span class="text-subtitle1 text-weight-bold">🧪 {{ isThai ? 'เพิ่มรายการสารเคมีเฝ้าระวัง' : 'Add Chemical Watchlist Item' }}</span>
          <q-btn flat round dense icon="close" v-close-popup size="sm" />
        </q-card-section>
        <q-card-section class="q-pa-md q-gutter-y-sm">
          <q-input v-model="materialForm.ingredient_name" :label="isThai ? 'ชื่อสารเคมี / วัตถุดิบ' : 'Material / Ingredient Name'" dense outlined bg-color="white" />
          <q-input v-model="materialForm.mat_sap_code" :label="isThai ? 'รหัส SAP (ถ้ามี)' : 'SAP Code (Optional)'" dense outlined bg-color="white" />
          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input v-model.number="materialForm.current_stock" :label="isThai ? 'คงเหลือปัจจุบัน' : 'Current Stock'" type="number" dense outlined bg-color="white" />
            </div>
            <div class="col-6">
              <q-input v-model.number="materialForm.min_threshold" :label="isThai ? 'จุดเตือนสต็อกต่ำ' : 'Min Threshold'" type="number" dense outlined bg-color="white" />
            </div>
          </div>
          <q-input v-model="materialForm.alert_note" :label="isThai ? 'ข้อความเตือน (Note)' : 'Alert Note'" dense outlined bg-color="white" :placeholder="isThai ? 'เช่น เบิกล่วงหน้า 5 ถุง' : 'e.g. Requisition 5 bags advance'" />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat :label="isThai ? 'ยกเลิก' : 'Cancel'" color="grey-7" v-close-popup />
          <q-btn unelevated :label="isThai ? 'เพิ่มรายการ' : 'Add Item'" color="teal-7" @click="submitMaterialAlert" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Email Dispatch Dialog -->
    <q-dialog v-model="showEmailDialog">
      <q-card class="bg-white text-grey-9" style="min-width: 480px; border-radius: 10px; border: 1px solid #e8e0f0;">
        <q-card-section class="bg-primary text-white q-py-sm row items-center justify-between">
          <span class="text-subtitle1 text-weight-bold">📧 {{ isThai ? 'ส่งรายงานสรุปกะผ่าน Email' : 'Send Shift Summary Email Report' }}</span>
          <q-btn flat round dense icon="close" v-close-popup size="sm" />
        </q-card-section>
        <q-card-section class="q-pa-md q-gutter-y-sm">
          <div class="text-caption text-grey-7">
            {{ isThai ? 'ระบบจะสร้างรายงาน HTML สรุป KPI, ยอดผลิต, และปัญหาเครื่องจักร ส่งตรงเข้า Email' : 'System will generate HTML email summary of shift KPIs, yield, and machinery issues.' }}
          </div>
          <q-select
            v-model="emailRecipients"
            :label="isThai ? 'ผู้รับรายงาน (Recipients)' : 'Recipients'"
            use-input use-chips multiple
            new-value-mode="add-unique"
            dense outlined bg-color="white"
            :hint="isThai ? 'พิมพ์อีเมลแล้วกด Enter เพื่อเพิ่ม' : 'Type email and press Enter to add'"
          />
          <q-input
            v-model="emailCustomNotes"
            :label="isThai ? 'ข้อความเพิ่มเติมใน Email' : 'Additional Email Notes'"
            type="textarea" rows="2"
            dense outlined bg-color="white"
          />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat :label="isThai ? 'ยกเลิก' : 'Cancel'" color="grey-7" v-close-popup />
          <q-btn unelevated :label="isThai ? 'ส่ง Email ทันที' : 'Send Email Now'" color="primary" class="text-weight-bold" :loading="sendingEmail" @click="dispatchEmailReport" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Manual Acknowledge Sign Dialog -->
    <q-dialog v-model="showAcknowledgeDialog">
      <q-card class="bg-white text-grey-9" style="min-width: 400px; border-radius: 10px; border: 1px solid #e8e0f0;">
        <q-card-section class="bg-deep-purple-8 text-white q-py-sm row items-center justify-between">
          <span class="text-subtitle1 text-weight-bold">✍️ {{ isThai ? 'ลงชื่อรับมอบงานกะใหม่ (Manual Sign-off)' : 'Manual Incoming Shift Sign-Off' }}</span>
          <q-btn flat round dense icon="close" v-close-popup size="sm" />
        </q-card-section>
        <q-card-section class="q-pa-md q-gutter-y-sm">
          <q-input v-model="incomingNameInput" :label="isThai ? 'ชื่อ-นามสกุล ผู้รับมอบงาน' : 'Incoming Operator Full Name'" dense outlined bg-color="white" />
          <q-input v-model="incomingNotesInput" :label="isThai ? 'ข้อความตอบรับ / บันทึกเพิ่มเติม' : 'Incoming Acceptance Notes / Remarks'" type="textarea" rows="3" dense outlined bg-color="white" />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat :label="isThai ? 'ยกเลิก' : 'Cancel'" color="grey-7" v-close-popup />
          <q-btn unelevated :label="isThai ? 'ยืนยันเซ็นรับกะ' : 'Confirm Sign-Off'" color="deep-purple-7" class="text-weight-bold" @click="submitManualAcknowledge" />
        </q-card-actions>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useQuasar } from 'quasar'
import { useAuth } from '~/composables/useAuth'
import { useI18n } from '~/composables/useI18n'

const $q = useQuasar()
const appConfig = useAppConfig()
const apiBase = appConfig.apiBaseUrl || 'http://192.168.121.23:8031'
const { user: currentUser } = useAuth()
const { t, locale, isThai } = useI18n()

// State
const selectedPlant = ref<number>(1)
const selectedShift = ref<string>('Morning')
const selectedDate = ref<string>(new Date().toISOString().split('T')[0])
const activeTab = ref<string>('kpis')

const isSelectedDateWeekend = computed(() => {
  if (!selectedDate.value) return false
  const parts = selectedDate.value.split('-').map(Number)
  if (parts.length < 3) return false
  const dt = new Date(parts[0], parts[1] - 1, parts[2])
  const day = dt.getDay() // 0=Sun, 5=Fri, 6=Sat
  return day === 5 || day === 6 || day === 0
})

const isViewingToday = computed(() => {
  const todayStr = new Date().toISOString().split('T')[0]
  return selectedDate.value === todayStr
})

const shiftOptions = computed(() => {
  if (isSelectedDateWeekend.value) {
    // 2 Shifts on Friday - Sunday (06:00-18:00, 18:00-06:00)
    return [
      { label: isThai.value ? '🌅 เช้า (06:00 - 18:00)' : '🌅 Morning (06:00 - 18:00)', value: 'Morning' },
      { label: isThai.value ? '🌙 ดึก (18:00 - 06:00)' : '🌙 Night (18:00 - 06:00)', value: 'Night' }
    ]
  } else {
    // 3 Shifts on Monday - Thursday (06:00-14:00, 14:00-22:00, 22:00-06:00)
    return [
      { label: isThai.value ? '🌅 เช้า (06:00 - 14:00)' : '🌅 Morning (06:00 - 14:00)', value: 'Morning' },
      { label: isThai.value ? '🌇 บ่าย (14:00 - 22:00)' : '🌇 Afternoon (14:00 - 22:00)', value: 'Afternoon' },
      { label: isThai.value ? '🌙 ดึก (22:00 - 06:00)' : '🌙 Night (22:00 - 06:00)', value: 'Night' }
    ]
  }
})

const currentShiftInfo = ref<any>(null)

const currentShiftLabel = computed(() => {
  if (isViewingToday.value) {
    if (isThai.value) {
      return (currentShiftInfo.value?.shift_label_th || currentShiftInfo.value?.shift_label || 'กำลังโหลดกะ...')
    } else {
      return (currentShiftInfo.value?.shift_label_en || currentShiftInfo.value?.shift_label || 'Loading Shift...')
    }
  } else {
    const opt = shiftOptions.value.find((o: any) => o.value === selectedShift.value)
    return opt ? opt.label : selectedShift.value
  }
})

watch(selectedDate, () => {
  if (isSelectedDateWeekend.value && selectedShift.value === 'Afternoon') {
    selectedShift.value = 'Morning'
  }
})

const shiftData = ref<any>(null)
const shiftKpis = ref<any>({})
const shiftBatches = ref<any[]>([])
const issuesList = ref<any[]>([])
const materialAlerts = ref<any[]>([])
const handoverRecord = ref<any>(null)

const loadingData = ref<boolean>(false)
const savingDraft = ref<boolean>(false)
const sendingEmail = ref<boolean>(false)

// Checklist & Notes
const checklist = ref({
  tank_cleaned: false,
  area_5s: false,
  safety_normal: true,
  waste_disposed: false
})
const outgoingNotes = ref<string>('')
const badgeInputHandover = ref<string>('')

// Dialogs
const showIssueDialog = ref<boolean>(false)
const issueForm = ref({
  machine_tag: '',
  title: '',
  severity: 'Medium',
  description: '',
  assigned_to: ''
})

const showMaterialDialog = ref<boolean>(false)
const materialForm = ref({
  ingredient_name: '',
  mat_sap_code: '',
  current_stock: 0,
  min_threshold: 10,
  unit: 'kg',
  alert_note: ''
})

const showEmailDialog = ref<boolean>(false)
const emailRecipients = ref<string[]>(['production-leads@mitrphol.com', 'maintenance@mitrphol.com'])
const emailCustomNotes = ref<string>('')

const showAcknowledgeDialog = ref<boolean>(false)
const incomingNameInput = ref<string>('')
const incomingNotesInput = ref<string>('')

// History Tab
const historyList = ref<any[]>([])
const loadingHistory = ref<boolean>(false)

// Table Columns (Bilingual)
const batchColumns = computed(() => [
  { name: 'batch_id', label: isThai.value ? 'BATCH ID' : 'BATCH ID', field: 'batch_id', align: 'left' as const, sortable: true },
  { name: 'sku_name', label: isThai.value ? 'สูตร / SKU' : 'SKU / PRODUCT', field: 'sku_name', align: 'left' as const, sortable: true },
  { name: 'batch_size', label: isThai.value ? 'ขนาด BATCH' : 'BATCH SIZE', field: 'batch_size', align: 'right' as const, sortable: true },
  { name: 'status', label: isThai.value ? 'สถานะ' : 'STATUS', field: 'status', align: 'center' as const, sortable: true },
  { name: 'start_time', label: isThai.value ? 'เวลาเริ่ม' : 'START TIME', field: 'start_time', align: 'center' as const, sortable: true },
  { name: 'end_time', label: isThai.value ? 'เวลาเสร็จ' : 'END TIME', field: 'end_time', align: 'center' as const, sortable: true }
])

const materialColumns = computed(() => [
  { name: 'ingredient_name', label: isThai.value ? 'ชื่อสารเคมี / วัตถุดิบ' : 'MATERIAL NAME', field: 'ingredient_name', align: 'left' as const },
  { name: 'mat_sap_code', label: isThai.value ? 'SAP CODE' : 'SAP CODE', field: 'mat_sap_code', align: 'left' as const },
  { name: 'current_stock', label: isThai.value ? 'สต็อกคงเหลือ' : 'CURRENT STOCK', field: 'current_stock', align: 'right' as const },
  { name: 'min_threshold', label: isThai.value ? 'จุดแจ้งเตือนขั้นต่ำ' : 'MIN THRESHOLD', field: 'min_threshold', align: 'right' as const },
  { name: 'alert_note', label: isThai.value ? 'หมายเหตุ / การดำเนินการ' : 'NOTE / ACTION', field: 'alert_note', align: 'left' as const },
  { name: 'actions', label: isThai.value ? 'จัดการ' : 'ACTION', field: 'actions', align: 'center' as const }
])

const historyColumns = computed(() => [
  { name: 'shift_date', label: isThai.value ? 'วันที่' : 'DATE', field: 'shift_date', align: 'left' as const, sortable: true },
  { name: 'shift_type', label: isThai.value ? 'กะ' : 'SHIFT', field: 'shift_type', align: 'left' as const, sortable: true },
  { name: 'plant_id', label: isThai.value ? 'PLANT' : 'PLANT', field: 'plant_id', align: 'center' as const },
  { name: 'outgoing_operator_name', label: isThai.value ? 'ผู้ส่งมอบ' : 'OUTGOING OPERATOR', field: 'outgoing_operator_name', align: 'left' as const },
  { name: 'incoming_operator_name', label: isThai.value ? 'ผู้รับมอบ' : 'INCOMING OPERATOR', field: 'incoming_operator_name', align: 'left' as const },
  { name: 'status', label: isThai.value ? 'สถานะ' : 'STATUS', field: 'status', align: 'center' as const },
  { name: 'actions', label: isThai.value ? 'ดูข้อมูล' : 'VIEW', field: 'actions', align: 'center' as const }
])

const openIssuesCount = computed(() => {
  return issuesList.value.filter(i => i.status !== 'Resolved').length
})

// Methods
const formatNumber = (val: any) => {
  if (val === null || val === undefined) return '0.0'
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'Completed': return 'positive'
    case 'Running':
    case 'In-Progress': return 'primary'
    case 'Planned': return 'grey-7'
    case 'Interrupted':
    case 'Cancelled': return 'negative'
    default: return 'blue-grey-6'
  }
}

const getSeverityColor = (sev: string) => {
  switch (sev?.toLowerCase()) {
    case 'critical': return 'negative'
    case 'high': return 'deep-orange-7'
    case 'medium': return 'amber-8'
    case 'low': return 'blue-7'
    default: return 'grey-7'
  }
}

const getIssueStatusColor = (st: string) => {
  switch (st) {
    case 'Open': return 'negative'
    case 'In-Progress': return 'amber-8'
    case 'Resolved': return 'positive'
    default: return 'grey-7'
  }
}

// Fetch Current Shift Info (Real-time live shift for today)
const fetchCurrentShiftInfo = async () => {
  try {
    const res = await $fetch<any>(`${apiBase}/shift-logbook/current-shift`)
    currentShiftInfo.value = res
  } catch (err) {
    console.error('Failed to fetch current shift info:', err)
  }
}

// Load Shift Data (Batches, KPIs, Handover)
const loadShiftData = async () => {
  loadingData.value = true
  try {
    const params = new URLSearchParams({
      plant_id: String(selectedPlant.value),
      shift_type: selectedShift.value,
      shift_date: selectedDate.value
    })
    const res = await $fetch<any>(`${apiBase}/shift-logbook/summary?${params.toString()}`)
    if (res) {
      shiftData.value = res
      shiftKpis.value = res.kpis || {}
      shiftBatches.value = res.batches || []
      issuesList.value = res.issues || []
      materialAlerts.value = res.chemical_alerts || []
      handoverRecord.value = res.handover || null

      if (res.handover) {
        checklist.value = {
          tank_cleaned: Boolean(res.handover.checklist_tank_cleaned),
          area_5s: Boolean(res.handover.checklist_area_5s),
          safety_normal: Boolean(res.handover.checklist_safety_normal),
          waste_disposed: Boolean(res.handover.checklist_waste_disposed)
        }
        outgoingNotes.value = res.handover.outgoing_notes || ''
      } else {
        checklist.value = { tank_cleaned: false, area_5s: false, safety_normal: true, waste_disposed: false }
        outgoingNotes.value = ''
      }
    }
  } catch (err) {
    console.error('Error loading shift data:', err)
  } finally {
    loadingData.value = false
  }
}

// Save Handover (Draft or Submitted)
const saveHandover = async (status: string) => {
  savingDraft.value = true
  try {
    const payload = {
      shift_date: selectedDate.value,
      shift_type: selectedShift.value,
      plant_id: selectedPlant.value,
      status: status,
      checklist_tank_cleaned: checklist.value.tank_cleaned,
      checklist_area_5s: checklist.value.area_5s,
      checklist_safety_normal: checklist.value.safety_normal,
      checklist_waste_disposed: checklist.value.waste_disposed,
      outgoing_notes: outgoingNotes.value,
      outgoing_operator_name: currentUser?.value?.full_name || currentUser?.value?.username || 'Operator'
    }

    const res = await $fetch<any>(`${apiBase}/shift-logbook/handover`, {
      method: 'POST',
      body: payload
    })

    if (res) {
      handoverRecord.value = res
      $q.notify({
        type: 'positive',
        message: isThai.value ? `บันทึกข้อมูลกะเรียบร้อย (${status})` : `Shift handover saved (${status})`,
        position: 'top',
        timeout: 3000
      })
    }
  } catch (err) {
    console.error('Failed to save handover:', err)
    $q.notify({
      type: 'negative',
      message: isThai.value ? 'บันทึกข้อมูลไม่สำเร็จ กรุณาลองใหม่อีกครั้ง' : 'Failed to save handover record.',
      position: 'top'
    })
  } finally {
    savingDraft.value = false
  }
}

// Issues Modal Handlers
const openAddIssueDialog = () => {
  issueForm.value = {
    machine_tag: `Plant ${selectedPlant.value} - Tank ${selectedPlant.value}`,
    title: '',
    severity: 'Medium',
    description: '',
    assigned_to: ''
  }
  showIssueDialog.value = true
}

const submitIssue = async () => {
  if (!issueForm.value.title.trim()) {
    $q.notify({ type: 'warning', message: isThai.value ? 'กรุณาระบุหัวข้อปัญหา' : 'Please enter issue title' })
    return
  }
  try {
    const payload = {
      shift_date: selectedDate.value,
      shift_type: selectedShift.value,
      plant_id: selectedPlant.value,
      machine_tag: issueForm.value.machine_tag,
      title: issueForm.value.title,
      severity: issueForm.value.severity,
      description: issueForm.value.description,
      reported_by: currentUser?.value?.full_name || currentUser?.value?.username || 'Operator',
      assigned_to: issueForm.value.assigned_to,
      status: 'Open'
    }
    const res = await $fetch<any>(`${apiBase}/shift-logbook/issue`, {
      method: 'POST',
      body: payload
    })
    if (res) {
      issuesList.value.unshift(res)
      showIssueDialog.value = false
      $q.notify({ type: 'positive', message: isThai.value ? 'บันทึกปัญหาเครื่องจักรแล้ว' : 'Machine issue recorded' })
    }
  } catch (err) {
    console.error('Failed to submit issue:', err)
  }
}

const resolveIssue = async (issueId: number) => {
  try {
    await $fetch<any>(`${apiBase}/shift-logbook/issue/${issueId}`, {
      method: 'PATCH',
      body: { status: 'Resolved' }
    })
    const idx = issuesList.value.findIndex(i => i.id === issueId)
    if (idx !== -1) {
      issuesList.value[idx].status = 'Resolved'
    }
    $q.notify({ type: 'positive', message: isThai.value ? 'อัปเดตสถานะเป็นแก้ไขแล้ว' : 'Issue marked as Resolved' })
  } catch (err) {
    console.error('Failed to resolve issue:', err)
  }
}

const editIssue = (iss: any) => {
  issueForm.value = { ...iss }
  showIssueDialog.value = true
}

// Material Watchlist Handlers
const openAddMaterialDialog = () => {
  materialForm.value = {
    ingredient_name: '',
    mat_sap_code: '',
    current_stock: 0,
    min_threshold: 10,
    unit: 'kg',
    alert_note: ''
  }
  showMaterialDialog.value = true
}

const submitMaterialAlert = async () => {
  if (!materialForm.value.ingredient_name.trim()) {
    $q.notify({ type: 'warning', message: isThai.value ? 'กรุณากรอกชื่อสารเคมี' : 'Please enter material name' })
    return
  }
  try {
    const payload = {
      shift_date: selectedDate.value,
      shift_type: selectedShift.value,
      plant_id: selectedPlant.value,
      ...materialForm.value
    }
    const res = await $fetch<any>(`${apiBase}/shift-logbook/chemical-alert`, {
      method: 'POST',
      body: payload
    })
    if (res) {
      materialAlerts.value.push(res)
      showMaterialDialog.value = false
      $q.notify({ type: 'positive', message: isThai.value ? 'เพิ่มรายการเฝ้าระวังแล้ว' : 'Material alert added' })
    }
  } catch (err) {
    console.error('Failed to add material alert:', err)
  }
}

const removeMaterialAlert = async (idx: number) => {
  const item = materialAlerts.value[idx]
  if (item && item.id) {
    try {
      await $fetch<any>(`${apiBase}/shift-logbook/chemical-alert/${item.id}`, { method: 'DELETE' })
    } catch (e) {
      console.warn('Failed to delete on backend', e)
    }
  }
  materialAlerts.value.splice(idx, 1)
}

// Email Handlers
const openEmailDialog = () => {
  showEmailDialog.value = true
}

const dispatchEmailReport = async () => {
  sendingEmail.value = true
  try {
    const payload = {
      plant_id: selectedPlant.value,
      shift_type: selectedShift.value,
      shift_date: selectedDate.value,
      recipients: emailRecipients.value,
      notes: emailCustomNotes.value
    }
    await $fetch<any>(`${apiBase}/shift-logbook/send-email-summary`, {
      method: 'POST',
      body: payload
    })
    showEmailDialog.value = false
    $q.notify({
      type: 'positive',
      message: isThai.value ? 'ส่งรายงานกะผ่าน Email เรียบร้อยแล้ว' : 'Shift summary email dispatched successfully!',
      position: 'top',
      timeout: 4000
    })
  } catch (err) {
    console.error('Failed to send email:', err)
    $q.notify({
      type: 'negative',
      message: isThai.value ? 'เกิดข้อผิดพลาดในการส่ง Email' : 'Failed to send email summary.',
      position: 'top'
    })
  } finally {
    sendingEmail.value = false
  }
}

// QR Badge & Manual Sign Handlers
const handleBadgeAcknowledge = async () => {
  const code = badgeInputHandover.value.trim()
  if (!code) return
  try {
    const res = await $fetch<any>(`${apiBase}/shift-logbook/acknowledge`, {
      method: 'POST',
      body: {
        shift_date: selectedDate.value,
        shift_type: selectedShift.value,
        plant_id: selectedPlant.value,
        badge_code: code
      }
    })
    if (res) {
      handoverRecord.value = res
      badgeInputHandover.value = ''
      $q.notify({
        type: 'positive',
        message: isThai.value ? `🎉 เซ็นรับมอบกะเรียบร้อยแล้วโดย ${res.incoming_operator_name}` : `🎉 Shift acknowledged by ${res.incoming_operator_name}`,
        position: 'top',
        timeout: 4000
      })
    }
  } catch (err) {
    console.error('Badge acknowledge failed:', err)
    $q.notify({
      type: 'negative',
      message: isThai.value ? 'ไม่พบรหัส Badge หรือเกิดข้อผิดพลาด' : 'Invalid Badge or acknowledge failed.',
      position: 'top'
    })
  }
}

const submitManualAcknowledge = async () => {
  if (!incomingNameInput.value.trim()) {
    $q.notify({ type: 'warning', message: isThai.value ? 'กรุณาระบุชื่อผู้รับมอบงาน' : 'Please enter operator name' })
    return
  }
  try {
    const res = await $fetch<any>(`${apiBase}/shift-logbook/acknowledge`, {
      method: 'POST',
      body: {
        shift_date: selectedDate.value,
        shift_type: selectedShift.value,
        plant_id: selectedPlant.value,
        operator_name: incomingNameInput.value.trim(),
        incoming_notes: incomingNotesInput.value.trim()
      }
    })
    if (res) {
      handoverRecord.value = res
      showAcknowledgeDialog.value = false
      incomingNameInput.value = ''
      incomingNotesInput.value = ''
      $q.notify({
        type: 'positive',
        message: isThai.value ? `🎉 เซ็นรับมอบกะเรียบร้อยแล้ว` : `🎉 Shift handover acknowledged!`,
        position: 'top'
      })
    }
  } catch (err) {
    console.error('Manual acknowledge failed:', err)
  }
}

// History List Handler
const loadHistoryList = async () => {
  loadingHistory.value = true
  try {
    const res = await $fetch<any[]>(`${apiBase}/shift-logbook/history?plant_id=${selectedPlant.value}&limit=30`)
    historyList.value = res || []
  } catch (err) {
    console.error('Failed to load history list:', err)
  } finally {
    loadingHistory.value = false
  }
}

const viewHistoryDetail = (histId: number) => {
  const item = historyList.value.find(h => h.id === histId)
  if (item) {
    selectedDate.value = item.shift_date
    selectedShift.value = item.shift_type
    selectedPlant.value = item.plant_id
    activeTab.value = 'kpis'
    loadShiftData()
  }
}

// Lifecycle
let timerInterval: any = null

onMounted(async () => {
  await fetchCurrentShiftInfo()
  if (isViewingToday.value && currentShiftInfo.value?.shift_type) {
    selectedShift.value = currentShiftInfo.value.shift_type
  }
  await loadShiftData()

  // Refresh clock & live info every 30s
  timerInterval = setInterval(() => {
    fetchCurrentShiftInfo()
  }, 30000)
})

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
})
</script>

<style scoped>
/* Clean Quasar Framework Styling */
.shift-page {
  font-family: inherit;
}

.top-nav {
  position: sticky;
  top: 0;
  z-index: 100;
}

/* KPI Card Enhancements */
.kpi-card {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
}

/* Issue Card borders */
.issue-card {
  transition: all 0.15s ease;
}

.issue-card.border-critical {
  border-left: 4px solid #c62828 !important;
}

.issue-card.border-high {
  border-left: 4px solid #e65100 !important;
}

.issue-card.border-medium {
  border-left: 4px solid #f57f17 !important;
}

.issue-card.border-low {
  border-left: 4px solid #1976d2 !important;
}

/* App Table standard header */
.app-table :deep(thead tr:first-child th) {
  background-color: #f8fafc;
  color: #334155;
  font-weight: 700;
  font-size: 11px;
}

.app-table :deep(tbody tr:hover) {
  background-color: #f1f5f9 !important;
}

/* QR Badge Box */
.badge-scan-box {
  transition: all 0.2s ease;
}

.scan-input :deep(.q-field__control) {
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
}
</style>
