<template>
  <q-page class="shift-page bg-dark-page text-white" style="min-height: 100vh; padding-bottom: 40px;">
    <!-- ═══════════════════════════════════════════════════════════════ -->
    <!-- 🔝 Top Bar / Header -->
    <!-- ═══════════════════════════════════════════════════════════════ -->
    <div class="top-nav q-px-lg q-py-sm row items-center no-wrap shadow-3" style="background: #111827; border-bottom: 1px solid rgba(255,255,255,0.08); gap: 12px; flex-wrap: wrap;">
      <div class="row items-center q-gutter-x-sm">
        <q-icon name="assignment" size="28px" color="amber-4" />
        <div>
          <div class="text-subtitle1 text-weight-bolder text-white" style="letter-spacing: -0.3px; line-height: 1.2;">
            E-Logbook & Shift Handover
          </div>
          <div class="text-caption text-grey-5" style="font-size: 11px;">
            {{ isThai ? "สมุดบันทึกส่งมอบงานประจำกะดิจิทัล" : "Digital Shift Handover & Operational Logbook" }}
          </div>
        </div>
      </div>

      <!-- Current Active Shift Badge -->
      <q-chip dense color="deep-purple-9" text-color="deep-purple-2" class="q-ml-sm text-weight-bold" icon="schedule">
        {{ currentShiftInfo?.shift_label || 'กำลังโหลด...' }}
        <span class="q-ml-xs text-amber-3" v-if="currentShiftInfo?.minutes_remaining">
          (เหลือ {{ currentShiftInfo.minutes_remaining }} น.)
        </span>
      </q-chip>

      <q-space />

      <!-- Plant Selector -->
      <div class="row items-center q-gutter-x-xs">
        <span class="text-caption text-grey-4 text-weight-bold">PLANT:</span>
        <q-btn-toggle
          v-model="selectedPlant"
          :options="[{label:'Plant 1',value:1},{label:'Plant 2',value:2},{label:'Plant 3',value:3}]"
          dense unelevated rounded
          color="blue-grey-9" text-color="grey-4"
          toggle-color="primary" toggle-text-color="white"
          size="sm"
          @update:model-value="loadShiftData"
        />
      </div>

      <!-- Shift Type Selector -->
      <div class="row items-center q-gutter-x-xs">
        <span class="text-caption text-grey-4 text-weight-bold">{{ isThai ? 'กะ:' : 'SHIFT:' }}</span>
        <q-btn-toggle
          v-model="selectedShift"
          :options="shiftOptions"
          dense unelevated rounded
          color="blue-grey-9" text-color="grey-4"
          toggle-color="amber-9" toggle-text-color="white"
          size="sm"
          @update:model-value="loadShiftData"
        />
      </div>

      <!-- Shift Date -->
      <q-input
        v-model="selectedDate"
        type="date"
        dense outlined dark
        bg-color="grey-10"
        style="width: 140px; font-size: 12px;"
        @update:model-value="loadShiftData"
      />

      <!-- Action Buttons -->
      <div class="row items-center q-gutter-x-sm">
        <q-btn
          unelevated
          dense
          color="teal-7"
          icon="save"
          label="บันทึกร่าง"
          class="q-px-sm text-weight-bold"
          size="sm"
          :loading="savingDraft"
          @click="saveHandover('Draft')"
        />
        <q-btn
          unelevated
          dense
          color="amber-8"
          icon="email"
          label="ส่ง Email สรุป"
          class="q-px-sm text-weight-bold text-dark"
          size="sm"
          @click="openEmailDialog"
        />
        <q-btn
          outline
          dense
          color="grey-4"
          icon="refresh"
          round
          size="sm"
          @click="loadShiftData"
        >
          <q-tooltip>รีเฟรชข้อมูล</q-tooltip>
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
        class="text-grey-5 bg-grey-10 rounded-borders q-mb-md"
        active-color="amber-4"
        indicator-color="amber-4"
        style="border: 1px solid rgba(255,255,255,0.06); border-radius: 10px;"
      >
        <q-tab name="kpis" icon="analytics" label="ภาพรวม & ยอดผลิต" />
        <q-tab name="issues" icon="warning" label="ปัญหาเครื่องจักร & ซ่อมบำรุง">
          <q-badge v-if="openIssuesCount > 0" color="red-6" floating rounded>{{ openIssuesCount }}</q-badge>
        </q-tab>
        <q-tab name="chemicals" icon="science" label="สารเคมีเฝ้าระวัง" />
        <q-tab name="handover" icon="how_to_reg" label="ส่งมอบ & เซ็นรับกะ (Sign-off)" />
        <q-tab name="history" icon="history" label="ประวัติส่งกะย้อนหลัง" />
      </q-tabs>

      <!-- ───────────────────────────────────────────────────────────── -->
      <!-- TAB 1: 📊 KPIs & Batches -->
      <!-- ───────────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'kpis'">
        <!-- KPI Metric Cards Grid -->
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-sm-6 col-md-3">
            <q-card class="kpi-card bg-slate shadow-4">
              <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
                <span class="text-caption text-grey-4 text-weight-bold">BATCHES สำเร็จ</span>
                <q-icon name="check_circle" color="green-4" size="22px" />
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-h4 text-weight-bolder text-green-4">
                  {{ shiftKpis.completed_batches || 0 }}
                  <span class="text-body2 text-grey-5">/ {{ shiftKpis.total_batches || 0 }}</span>
                </div>
                <div class="text-caption text-grey-5 q-mt-xs">
                  กำลังผลิต: {{ shiftKpis.running_batches || 0 }} Batch
                </div>
              </q-card-section>
            </q-card>
          </div>

          <div class="col-12 col-sm-6 col-md-3">
            <q-card class="kpi-card bg-slate shadow-4">
              <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
                <span class="text-caption text-grey-4 text-weight-bold">ยอดผลิตรวม (YIELD)</span>
                <q-icon name="scale" color="cyan-4" size="22px" />
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-h4 text-weight-bolder text-cyan-4">
                  {{ formatNumber(shiftKpis.total_volume_kg || 0) }}
                  <span class="text-body2 text-grey-5">kg</span>
                </div>
                <div class="text-caption text-grey-5 q-mt-xs">
                  เป้าหมาย: {{ formatNumber(shiftKpis.target_volume_kg || 0) }} kg
                </div>
              </q-card-section>
            </q-card>
          </div>

          <div class="col-12 col-sm-6 col-md-3">
            <q-card class="kpi-card bg-slate shadow-4">
              <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
                <span class="text-caption text-grey-4 text-weight-bold">OEE ประจำกะ</span>
                <q-icon name="speed" color="lime-4" size="22px" />
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-h4 text-weight-bolder text-lime-4">
                  {{ shiftKpis.oee_pct || 0 }}%
                </div>
                <div class="text-caption text-grey-5 q-mt-xs">
                  Availability: {{ shiftKpis.availability_pct || 0 }}% | Quality: {{ shiftKpis.quality_pct || 0 }}%
                </div>
              </q-card-section>
            </q-card>
          </div>

          <div class="col-12 col-sm-6 col-md-3">
            <q-card class="kpi-card bg-slate shadow-4">
              <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
                <span class="text-caption text-grey-4 text-weight-bold">DOWNTIME รวม</span>
                <q-icon name="timer_off" color="orange-4" size="22px" />
              </q-card-section>
              <q-card-section class="q-pt-none">
                <div class="text-h4 text-weight-bolder text-orange-4">
                  {{ shiftKpis.downtime_mins || 0 }}
                  <span class="text-body2 text-grey-5">นาที</span>
                </div>
                <div class="text-caption text-grey-5 q-mt-xs">
                  ปัญหาเปิดอยู่: {{ openIssuesCount }} รายการ
                </div>
              </q-card-section>
            </q-card>
          </div>
        </div>

        <!-- Batches Produced in this Shift Table -->
        <q-card class="bg-slate shadow-4 q-pa-md" style="border-radius: 12px;">
          <div class="row items-center justify-between q-mb-md">
            <div class="row items-center q-gutter-x-sm">
              <q-icon name="view_list" size="20px" color="cyan-3" />
              <span class="text-subtitle1 text-weight-bold">รายการ Batch ที่ผลิตในกะนี้ (Plant {{ selectedPlant }})</span>
            </div>
            <q-badge color="blue-grey-8" text-color="grey-3">
              ช่วงเวลา: {{ shiftData?.time_range || '-' }}
            </q-badge>
          </div>

          <q-table
            :rows="shiftBatches"
            :columns="batchColumns"
            row-key="batch_id"
            dense
            dark
            flat
            :loading="loadingData"
            class="custom-table"
            no-data-label="ไม่มีข้อมูล Batch ในช่วงเวลากะนี้"
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
        <q-card class="bg-slate shadow-4 q-pa-md q-mb-md" style="border-radius: 12px;">
          <div class="row items-center justify-between q-mb-md">
            <div>
              <div class="text-subtitle1 text-weight-bold row items-center q-gutter-x-sm">
                <q-icon name="build_circle" color="orange-4" size="22px" />
                <span>บันทึกปัญหาเครื่องจักร & การซ่อมบำรุง (Maintenance Log)</span>
              </div>
              <div class="text-caption text-grey-5">
                บันทึกรายการปัญหาเครื่องที่รอซ่อม เพื่อส่งต่อให้ช่างและกะถัดไปรับทราบ
              </div>
            </div>
            <q-btn
              color="primary"
              icon="add"
              label="แจ้งปัญหาเครื่องจักร"
              dense unelevated
              class="q-px-md text-weight-bold"
              @click="openAddIssueDialog"
            />
          </div>

          <!-- Issues Cards Grid -->
          <div v-if="issuesList.length > 0" class="row q-col-gutter-md">
            <div v-for="iss in issuesList" :key="iss.id" class="col-12 col-md-6">
              <q-card class="bg-grey-10 text-white q-pa-md issue-card" :class="'border-' + iss.severity?.toLowerCase()">
                <div class="row items-center justify-between no-wrap">
                  <div class="row items-center q-gutter-x-sm">
                    <q-chip dense :color="getSeverityColor(iss.severity)" text-color="white" size="xs" class="text-weight-bolder">
                      {{ iss.severity }}
                    </q-chip>
                    <span class="text-subtitle2 text-weight-bold text-cyan-3">{{ iss.machine_tag }}</span>
                  </div>
                  <q-chip dense :color="getIssueStatusColor(iss.status)" text-color="white" size="xs">
                    {{ iss.status }}
                  </q-chip>
                </div>

                <div class="text-body2 text-weight-bold q-mt-sm">{{ iss.title }}</div>
                <div class="text-caption text-grey-4 q-mt-xs" style="min-height: 36px;">
                  {{ iss.description || 'ไม่มีรายละเอียดเพิ่มเติม' }}
                </div>

                <q-separator dark class="q-my-sm" style="opacity: 0.15;" />

                <div class="row items-center justify-between text-caption text-grey-5">
                  <div>
                    <q-icon name="person" size="14px" /> ผู้แจ้ง: {{ iss.reported_by || 'Operator' }}
                    <span v-if="iss.assigned_to" class="q-ml-sm">
                      <q-icon name="engineering" size="14px" /> ผู้รับผิดชอบ: {{ iss.assigned_to }}
                    </span>
                  </div>
                  <div class="row q-gutter-x-xs">
                    <q-btn
                      v-if="iss.status !== 'Resolved'"
                      flat dense size="xs" color="green-4" icon="check" label="แก้แล้ว"
                      @click="resolveIssue(iss.id)"
                    />
                    <q-btn flat dense size="xs" color="grey-4" icon="edit" @click="editIssue(iss)" />
                  </div>
                </div>
              </q-card>
            </div>
          </div>
          <div v-else class="text-center q-pa-xl text-grey-5">
            <q-icon name="task_alt" size="48px" color="green-5" class="q-mb-sm" /><br>
            <span class="text-weight-bold">ไม่มีปัญหาเครื่องจักรค้างในระบบ (All Systems Normal)</span>
          </div>
        </q-card>
      </div>

      <!-- ───────────────────────────────────────────────────────────── -->
      <!-- TAB 3: 🧪 Chemical & Material Watchlist -->
      <!-- ───────────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 'chemicals'">
        <q-card class="bg-slate shadow-4 q-pa-md" style="border-radius: 12px;">
          <div class="row items-center justify-between q-mb-md">
            <div>
              <div class="text-subtitle1 text-weight-bold row items-center q-gutter-x-sm">
                <q-icon name="science" color="cyan-4" size="22px" />
                <span>รายการสารเคมี & วัตถุดิบเฝ้าระวัง (Chemical Low-Stock Watchlist)</span>
              </div>
              <div class="text-caption text-grey-5">
                เตือนรายการสารเคมีที่สต็อกเหลือน้อย หรือต้องเตรียมเบิกล่วงหน้าสำหรับกะถัดไป
              </div>
            </div>
            <q-btn
              color="teal-7"
              icon="add"
              label="เพิ่มรายการเฝ้าระวัง"
              dense unelevated
              class="q-px-md text-weight-bold"
              @click="openAddMaterialDialog"
            />
          </div>

          <q-table
            :rows="materialAlerts"
            :columns="materialColumns"
            row-key="ingredient_name"
            dense dark flat
            class="custom-table"
            no-data-label="ไม่มีรายการสารเคมีเฝ้าระวังในกะนี้"
          >
            <template v-slot:body-cell-current_stock="props">
              <q-td :props="props" class="text-weight-bold" :class="props.value <= props.row.min_threshold ? 'text-red-4' : 'text-green-4'">
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
                <q-btn flat dense round icon="delete" color="red-4" size="xs" @click="removeMaterialAlert(props.rowIndex)" />
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
            <q-card class="bg-slate shadow-4 q-pa-md" style="border-radius: 12px; height: 100%;">
              <div class="text-subtitle1 text-weight-bold text-amber-4 row items-center q-gutter-x-sm q-mb-sm">
                <q-icon name="checklist" size="22px" />
                <span>1. รายการตรวจสอบก่อนส่งมอบ (Shift Checklist)</span>
              </div>

              <div class="q-gutter-y-xs q-mb-md">
                <q-checkbox v-model="checklist.tank_cleaned" dark label="ล้างถังผสม / ท่อทางเรียบร้อย (CIP / Flush OK)" color="teal-5" />
                <q-checkbox v-model="checklist.area_5s" dark label="ทำความสะอาดพื้นที่ทำงาน 5ส เรียบร้อย" color="teal-5" />
                <q-checkbox v-model="checklist.safety_normal" dark label="ระบบความปลอดภัย / Emergency Switch อยู่ในสภาพปกติ" color="teal-5" />
                <q-checkbox v-model="checklist.waste_disposed" dark label="ทิ้งกาก/ของเสียและจัดเก็บถุงสารเคมีเรียบร้อย" color="teal-5" />
              </div>

              <q-separator dark class="q-my-md" style="opacity: 0.15;" />

              <div class="text-subtitle1 text-weight-bold text-primary row items-center q-gutter-x-sm q-mb-xs">
                <q-icon name="edit_note" size="22px" />
                <span>2. บันทึกข้อความส่งมอบ (Outgoing Notes)</span>
              </div>
              <q-input
                v-model="outgoingNotes"
                type="textarea"
                rows="4"
                outlined dark dense
                bg-color="grey-10"
                placeholder="ระบุสิ่งที่ต้องการเน้นย้ำ หรือฝากงานให้กะถัดไป..."
                class="q-mb-md"
              />

              <div class="row items-center justify-between">
                <div class="text-caption text-grey-4">
                  ผู้ส่งมอบกะ: <strong class="text-white">{{ currentUser?.full_name || currentUser?.username || 'Operator' }}</strong>
                </div>
                <q-btn
                  unelevated
                  color="amber-9"
                  text-color="dark"
                  icon="how_to_reg"
                  label="ลงชื่อยืนยันส่งมอบกะ (Submit)"
                  class="text-weight-bold"
                  :loading="savingDraft"
                  @click="saveHandover('Submitted')"
                />
              </div>
            </q-card>
          </div>

          <!-- Right: Incoming Operator Acknowledge (QR Badge / Sign) -->
          <div class="col-12 col-md-6">
            <q-card class="bg-slate shadow-4 q-pa-md" style="border-radius: 12px; height: 100%;">
              <div class="text-subtitle1 text-weight-bold text-purple-3 row items-center q-gutter-x-sm q-mb-sm">
                <q-icon name="qr_code_scanner" size="22px" />
                <span>3. การรับมอบงานของกะใหม่ (Incoming Sign-off)</span>
              </div>

              <!-- Status Banner -->
              <div class="q-pa-md rounded-borders q-mb-md" :class="handoverRecord?.status === 'Acknowledged' ? 'bg-green-10 text-white' : 'bg-grey-10 text-grey-4'" style="border: 1px solid rgba(255,255,255,0.1);">
                <div class="row items-center justify-between">
                  <span class="text-weight-bold">สถานะเอกสารส่งกะ:</span>
                  <q-chip dense :color="handoverRecord?.status === 'Acknowledged' ? 'green-6' : 'amber-8'" text-color="white" class="text-weight-bold">
                    {{ handoverRecord?.status || 'Draft' }}
                  </q-chip>
                </div>
                <div v-if="handoverRecord?.acknowledged_at" class="text-caption text-grey-3 q-mt-xs">
                  ✅ รับมอบแล้วโดย: <strong>{{ handoverRecord.incoming_operator_name }}</strong> เมื่อ {{ handoverRecord.acknowledged_at }}
                </div>
                <div v-else class="text-caption text-amber-3 q-mt-xs">
                  ⏳ รอกะถัดไปลงชื่อรับมอบงาน
                </div>
              </div>

              <div v-if="handoverRecord?.status !== 'Acknowledged'">
                <div class="text-body2 text-grey-3 q-mb-sm">
                  สำหรับ Operator กะใหม่: สแกน <strong>QR Badge พนักงาน</strong> หรือกดปุ่มด้านล่างเพื่อเซ็นรับมอบกะ
                </div>

                <!-- QR Badge Fast Scan Box -->
                <div class="badge-scan-box q-pa-md q-mb-md text-center" style="border-radius: 12px; background: rgba(126, 87, 194, 0.15); border: 2px dashed #7e57c2;">
                  <q-icon name="badge" size="36px" color="deep-purple-3" class="q-mb-xs" />
                  <div class="text-subtitle2 text-weight-bold text-purple-2">แตะบัตร QR Badge เพื่อรับกะทันที</div>
                  <q-input
                    ref="handoverBadgeRef"
                    v-model="badgeInputHandover"
                    outlined dense dark
                    placeholder="Waiting for RFID/QR scan..."
                    bg-color="grey-10"
                    class="q-mt-sm scan-input"
                    @keyup.enter="handleBadgeAcknowledge"
                  >
                    <template v-slot:prepend><q-icon name="qr_code" color="purple-3" /></template>
                  </q-input>
                </div>

                <q-btn
                  unelevated
                  color="deep-purple-7"
                  icon="verified"
                  label="ลงชื่อรับมอบงานแบบระบุชื่อ (Manual Sign)"
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
        <q-card class="bg-slate shadow-4 q-pa-md" style="border-radius: 12px;">
          <div class="row items-center justify-between q-mb-md">
            <div class="text-subtitle1 text-weight-bold row items-center q-gutter-x-sm">
              <q-icon name="history" color="amber-4" size="22px" />
              <span>ประวัติการส่งมอบงานย้อนหลัง (Handover Archive)</span>
            </div>
            <q-btn flat dense icon="refresh" color="grey-4" label="โหลดใหม่" @click="loadHistoryList" size="sm" />
          </div>

          <q-table
            :rows="historyList"
            :columns="historyColumns"
            row-key="id"
            dense dark flat
            :loading="loadingHistory"
            class="custom-table"
            no-data-label="ไม่มีประวัติการส่งกะ"
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
                <q-btn flat dense size="xs" color="cyan-3" icon="visibility" label="ดูสรุป" @click="viewHistoryDetail(props.row.id)" />
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
      <q-card class="bg-grey-10 text-white" style="min-width: 440px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.1);">
        <q-card-section class="bg-primary text-white q-py-sm row items-center justify-between">
          <span class="text-subtitle1 text-weight-bold">⚠️ แจ้งปัญหาเครื่องจักร / ซ่อมบำรุง</span>
          <q-btn flat round dense icon="close" v-close-popup size="sm" />
        </q-card-section>
        <q-card-section class="q-pa-md q-gutter-y-sm">
          <q-input v-model="issueForm.machine_tag" label="รหัสเครื่องจักร (Machine Tag / Tank)" dense outlined dark bg-color="grey-9" placeholder="เช่น Mixer 1, Valve Steam A, Holding Tank 2" />
          <q-input v-model="issueForm.title" label="หัวข้อปัญหา" dense outlined dark bg-color="grey-9" placeholder="เช่น วาล์วปิดไม่สนิท, มอเตอร์มีเสียงดัง" />
          <q-select v-model="issueForm.severity" :options="['Low', 'Medium', 'High', 'Critical']" label="ระดับความเร่งด่วน" dense outlined dark bg-color="grey-9" />
          <q-input v-model="issueForm.description" label="รายละเอียดอาการ" type="textarea" rows="3" dense outlined dark bg-color="grey-9" />
          <q-input v-model="issueForm.assigned_to" label="มอบหมายให้ (ช่าง/ทีม)" dense outlined dark bg-color="grey-9" placeholder="เช่น ทีม Maintenance กะบ่าย" />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="ยกเลิก" color="grey-4" v-close-popup />
          <q-btn unelevated label="บันทึกปัญหา" color="primary" @click="submitIssue" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Add Material Watchlist Dialog -->
    <q-dialog v-model="showMaterialDialog">
      <q-card class="bg-grey-10 text-white" style="min-width: 400px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.1);">
        <q-card-section class="bg-teal-8 text-white q-py-sm row items-center justify-between">
          <span class="text-subtitle1 text-weight-bold">🧪 เพิ่มรายการสารเคมีเฝ้าระวัง</span>
          <q-btn flat round dense icon="close" v-close-popup size="sm" />
        </q-card-section>
        <q-card-section class="q-pa-md q-gutter-y-sm">
          <q-input v-model="materialForm.ingredient_name" label="ชื่อสารเคมี / วัตถุดิบ" dense outlined dark bg-color="grey-9" />
          <q-input v-model="materialForm.mat_sap_code" label="รหัส SAP (ถ้ามี)" dense outlined dark bg-color="grey-9" />
          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input v-model.number="materialForm.current_stock" label="คงเหลือปัจจุบัน" type="number" dense outlined dark bg-color="grey-9" />
            </div>
            <div class="col-6">
              <q-input v-model.number="materialForm.min_threshold" label="จุดเตือนสต็อกต่ำ" type="number" dense outlined dark bg-color="grey-9" />
            </div>
          </div>
          <q-input v-model="materialForm.alert_note" label="ข้อความเตือน (Note)" dense outlined dark bg-color="grey-9" placeholder="เช่น เบิกล่วงหน้า 5 ถุง" />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="ยกเลิก" color="grey-4" v-close-popup />
          <q-btn unelevated label="เพิ่มรายการ" color="teal-7" @click="submitMaterialAlert" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Email Dispatch Dialog -->
    <q-dialog v-model="showEmailDialog">
      <q-card class="bg-grey-10 text-white" style="min-width: 480px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.1);">
        <q-card-section class="bg-amber-9 text-dark q-py-sm row items-center justify-between">
          <span class="text-subtitle1 text-weight-bolder">📧 ส่งรายงานสรุปกะผ่าน Email</span>
          <q-btn flat round dense icon="close" v-close-popup size="sm" />
        </q-card-section>
        <q-card-section class="q-pa-md q-gutter-y-sm">
          <div class="text-caption text-grey-4">
            ระบบจะสร้างรายงาน HTML สรุป KPI, ยอดผลิต, และปัญหาเครื่องจักร ส่งตรงเข้า Email
          </div>
          <q-select
            v-model="emailRecipients"
            label="ผู้รับรายงาน (Recipients)"
            use-input use-chips multiple
            new-value-mode="add-unique"
            dense outlined dark bg-color="grey-9"
            hint="พิมพ์อีเมลแล้วกด Enter เพื่อเพิ่ม"
          />
          <q-input
            v-model="emailCustomNotes"
            type="textarea"
            rows="2"
            label="ข้อความเพิ่มเติมถึงผู้บริหาร (Optional)"
            dense outlined dark bg-color="grey-9"
          />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="ยกเลิก" color="grey-4" v-close-popup />
          <q-btn unelevated label="ส่ง Email ทันที" color="amber-8" text-color="dark" :loading="sendingEmail" @click="dispatchEmailReport" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Manual Acknowledge Dialog -->
    <q-dialog v-model="showAcknowledgeDialog">
      <q-card class="bg-grey-10 text-white" style="min-width: 380px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.1);">
        <q-card-section class="bg-deep-purple-8 text-white q-py-sm row items-center justify-between">
          <span class="text-subtitle1 text-weight-bold">✍️ ลงชื่อรับมอบงาน (Incoming Sign)</span>
          <q-btn flat round dense icon="close" v-close-popup size="sm" />
        </q-card-section>
        <q-card-section class="q-pa-md q-gutter-y-sm">
          <q-input v-model="incomingNameInput" label="ชื่อผู้รับมอบงาน (Incoming Operator)" dense outlined dark bg-color="grey-9" />
          <q-input v-model="incomingNotesInput" label="บันทึกข้อความรับมอบ" type="textarea" rows="2" dense outlined dark bg-color="grey-9" />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="ยกเลิก" color="grey-4" v-close-popup />
          <q-btn unelevated label="ยืนยันรับกะ" color="deep-purple-7" @click="submitManualAcknowledge" />
        </q-card-actions>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
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

watch(selectedDate, () => {
  if (isSelectedDateWeekend.value && selectedShift.value === 'Afternoon') {
    selectedShift.value = 'Morning'
  }
})

const currentShiftInfo = ref<any>(null)
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
const emailRecipients = ref<string[]>(['supervisor@mitrphol.com', 'plant.manager@mitrphol.com'])
const emailCustomNotes = ref<string>('')

const showAcknowledgeDialog = ref<boolean>(false)
const incomingNameInput = ref<string>('')
const incomingNotesInput = ref<string>('')

// History
const historyList = ref<any[]>([])
const loadingHistory = ref<boolean>(false)

const openIssuesCount = computed(() => {
  return issuesList.value.filter(i => i.status !== 'Resolved').length
})

// Columns
const batchColumns = [
  { name: 'batch_id', label: 'BATCH ID', field: 'batch_id', align: 'left', sortable: true },
  { name: 'sku_name', label: 'SKU / PRODUCT', field: 'sku_name', align: 'left', sortable: true },
  { name: 'batch_size', label: 'BATCH SIZE', field: 'batch_size', align: 'right', sortable: true },
  { name: 'status', label: 'STATUS', field: 'status', align: 'center', sortable: true },
  { name: 'created_at', label: 'START TIME', field: 'created_at', align: 'center' },
  { name: 'updated_at', label: 'END TIME', field: 'updated_at', align: 'center' }
]

const materialColumns = [
  { name: 'ingredient_name', label: 'ชื่อสารเคมี / วัตถุดิบ', field: 'ingredient_name', align: 'left' },
  { name: 'mat_sap_code', label: 'รหัส SAP', field: 'mat_sap_code', align: 'left' },
  { name: 'current_stock', label: 'คงเหลือ', field: 'current_stock', align: 'right' },
  { name: 'min_threshold', label: 'เกณฑ์ต่ำสุด', field: 'min_threshold', align: 'right' },
  { name: 'alert_note', label: 'หมายเหตุ', field: 'alert_note', align: 'left' },
  { name: 'actions', label: '', field: 'actions', align: 'center' }
]

const historyColumns = [
  { name: 'shift_date', label: 'วันที่', field: 'shift_date', align: 'left' },
  { name: 'plant', label: 'Plant', field: (row: any) => `Plant ${row.plant}`, align: 'center' },
  { name: 'shift_type', label: 'กะ', field: 'shift_type', align: 'center' },
  { name: 'outgoing_operator_name', label: 'ผู้ส่งมอบ', field: 'outgoing_operator_name', align: 'left' },
  { name: 'incoming_operator_name', label: 'ผู้รับมอบ', field: 'incoming_operator_name', align: 'left' },
  { name: 'status', label: 'สถานะ', field: 'status', align: 'center' },
  { name: 'actions', label: 'การกระทำ', field: 'actions', align: 'center' }
]

// ─────────────────────────────────────────────────────────────────────────────
// Methods
// ─────────────────────────────────────────────────────────────────────────────

const formatNumber = (val: number) => {
  return Number(val || 0).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

const getStatusColor = (st: string) => {
  if (['Done', 'Completed', 'Finished'].includes(st)) return 'green-7'
  if (['Running', 'Active', 'In_Progress', 'In Progress'].includes(st)) return 'blue-7'
  return 'grey-7'
}

const getSeverityColor = (sev: string) => {
  if (sev === 'Critical') return 'red-8'
  if (sev === 'High') return 'orange-8'
  if (sev === 'Medium') return 'amber-8'
  return 'blue-8'
}

const getIssueStatusColor = (st: string) => {
  if (st === 'Resolved') return 'green-7'
  if (st === 'In_Progress') return 'blue-7'
  return 'orange-7'
}

const loadCurrentShiftInfo = async () => {
  try {
    const res = await $fetch<any>(`${apiBase}/shift-logbook/current-shift-info`)
    currentShiftInfo.value = res
    if (res?.shift_type && !selectedShift.value) {
      selectedShift.value = res.shift_type
    }
  } catch (err) {
    console.error('Failed to load current shift info:', err)
  }
}

const loadShiftData = async () => {
  loadingData.value = true
  try {
    const res = await $fetch<any>(`${apiBase}/shift-logbook/kpi-summary`, {
      params: {
        plant: selectedPlant.value,
        shift_type: selectedShift.value,
        shift_date: selectedDate.value
      }
    })
    shiftData.value = res
    shiftKpis.value = res.kpis || {}
    shiftBatches.value = res.batches || []
    issuesList.value = res.open_issues || []

    // Also check if existing handover record is saved
    const handovers = await $fetch<any[]>(`${apiBase}/shift-logbook/handovers`, {
      params: {
        plant: selectedPlant.value,
        shift_type: selectedShift.value,
        shift_date: selectedDate.value
      }
    })
    if (handovers && handovers.length > 0) {
      const hDetail = await $fetch<any>(`${apiBase}/shift-logbook/handovers/${handovers[0].id}`)
      handoverRecord.value = hDetail
      if (hDetail.checklist) checklist.value = hDetail.checklist
      if (hDetail.outgoing_notes) outgoingNotes.value = hDetail.outgoing_notes
      if (hDetail.material_alerts) materialAlerts.value = hDetail.material_alerts
    } else {
      handoverRecord.value = null
    }
  } catch (err: any) {
    $q.notify({ type: 'negative', message: 'เกิดข้อผิดพลาดในการดึงข้อมูลกะ: ' + (err.message || '') })
  } finally {
    loadingData.value = false
  }
}

const saveHandover = async (status: string) => {
  savingDraft.value = true
  try {
    const payload = {
      plant: selectedPlant.value,
      shift_type: selectedShift.value,
      shift_date: selectedDate.value,
      outgoing_operator_name: currentUser.value?.full_name || currentUser.value?.username || 'Operator',
      status: status,
      production_kpis: shiftKpis.value,
      checklist: checklist.value,
      outgoing_notes: outgoingNotes.value,
      material_alerts: materialAlerts.value
    }

    const res = await $fetch<any>(`${apiBase}/shift-logbook/handovers`, {
      method: 'POST',
      body: payload
    })

    $q.notify({
      type: 'positive',
      message: status === 'Submitted' ? '✅ ส่งมอบงานประจำกะเรียบร้อยแล้ว!' : '💾 บันทึกแบบร่างเรียบร้อยแล้ว'
    })
    await loadShiftData()
  } catch (err: any) {
    $q.notify({ type: 'negative', message: 'บันทึกไม่สำเร็จ: ' + (err.message || '') })
  } finally {
    savingDraft.value = false
  }
}

const openAddIssueDialog = () => {
  issueForm.value = {
    machine_tag: `Mixer Tank ${selectedPlant.value}`,
    title: '',
    severity: 'Medium',
    description: '',
    assigned_to: ''
  }
  showIssueDialog.value = true
}

const submitIssue = async () => {
  if (!issueForm.value.title || !issueForm.value.machine_tag) {
    $q.notify({ type: 'warning', message: 'กรุณาระบุเครื่องจักรและหัวข้อปัญหา' })
    return
  }
  try {
    await $fetch(`${apiBase}/shift-logbook/issues`, {
      method: 'POST',
      body: {
        plant: selectedPlant.value,
        ...issueForm.value,
        reported_by: currentUser.value?.full_name || currentUser.value?.username || 'Operator'
      }
    })
    $q.notify({ type: 'positive', message: 'บันทึกปัญหาเครื่องจักรแล้ว' })
    showIssueDialog.value = false
    await loadShiftData()
  } catch (err: any) {
    $q.notify({ type: 'negative', message: 'บันทึกไม่สำเร็จ: ' + err.message })
  }
}

const resolveIssue = async (id: number) => {
  try {
    await $fetch(`${apiBase}/shift-logbook/issues/${id}`, {
      method: 'PUT',
      body: { status: 'Resolved' }
    })
    $q.notify({ type: 'positive', message: 'อัปเดตสถานะเป็นแก้ไขแล้ว' })
    await loadShiftData()
  } catch (err: any) {
    $q.notify({ type: 'negative', message: 'อัปเดตไม่สำเร็จ: ' + err.message })
  }
}

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

const submitMaterialAlert = () => {
  if (!materialForm.value.ingredient_name) return
  materialAlerts.value.push({ ...materialForm.value })
  showMaterialDialog.value = false
  $q.notify({ type: 'positive', message: 'เพิ่มรายการเฝ้าระวังเรียบร้อย' })
}

const removeMaterialAlert = (index: number) => {
  materialAlerts.value.splice(index, 1)
}

const handleBadgeAcknowledge = async () => {
  const code = badgeInputHandover.value.trim()
  if (!code) return
  try {
    // Check badge code via auth API
    const authRes = await $fetch<any>(`${apiBase}/auth/badge-login`, {
      method: 'POST',
      body: { badge_code: code }
    })
    
    if (authRes?.user && handoverRecord.value?.id) {
      await $fetch(`${apiBase}/shift-logbook/handovers/${handoverRecord.value.id}/acknowledge`, {
        method: 'POST',
        body: {
          incoming_operator_id: authRes.user.id,
          incoming_operator_name: authRes.user.full_name || authRes.user.username,
          incoming_notes: 'รับมอบงานผ่านการสแกน QR Badge'
        }
      })
      $q.notify({ type: 'positive', message: `✅ สแกนสำเร็จ! ยินดีต้อนรับ ${authRes.user.full_name}` })
      badgeInputHandover.value = ''
      await loadShiftData()
    } else {
      $q.notify({ type: 'warning', message: 'กรุณาบันทึกส่งกะ (Submit) ก่อนทำการรับมอบ' })
    }
  } catch (err: any) {
    $q.notify({ type: 'negative', message: 'รหัส QR Badge ไม่ถูกต้อง: ' + (err.message || '') })
  }
}

const submitManualAcknowledge = async () => {
  if (!incomingNameInput.value.trim()) {
    $q.notify({ type: 'warning', message: 'กรุณาระบุชื่อผู้รับมอบงาน' })
    return
  }
  if (!handoverRecord.value?.id) {
    $q.notify({ type: 'warning', message: 'ยังไม่มีเอกสารส่งมอบกะ กรุณากดบันทึกส่งมอบก่อน' })
    return
  }

  try {
    await $fetch(`${apiBase}/shift-logbook/handovers/${handoverRecord.value.id}/acknowledge`, {
      method: 'POST',
      body: {
        incoming_operator_name: incomingNameInput.value.trim(),
        incoming_notes: incomingNotesInput.value.trim()
      }
    })
    $q.notify({ type: 'positive', message: '✅ เซ็นรับมอบงานเรียบร้อยแล้ว!' })
    showAcknowledgeDialog.value = false
    await loadShiftData()
  } catch (err: any) {
    $q.notify({ type: 'negative', message: 'เซ็นรับมอบไม่สำเร็จ: ' + err.message })
  }
}

const openEmailDialog = () => {
  showEmailDialog.value = true
}

const dispatchEmailReport = async () => {
  sendingEmail.value = true
  try {
    const res = await $fetch<any>(`${apiBase}/shift-logbook/send-email-report`, {
      method: 'POST',
      body: {
        handover_id: handoverRecord.value?.id,
        plant: selectedPlant.value,
        shift_type: selectedShift.value,
        shift_date: selectedDate.value,
        recipient_emails: emailRecipients.value,
        custom_notes: emailCustomNotes.value
      }
    })
    $q.notify({
      type: 'positive',
      message: '📧 ส่งรายงานทาง Email เรียบร้อยแล้ว! (' + res.smtp_status + ')'
    })
    showEmailDialog.value = false
  } catch (err: any) {
    $q.notify({ type: 'negative', message: 'ส่ง Email ไม่สำเร็จ: ' + err.message })
  } finally {
    sendingEmail.value = false
  }
}

const loadHistoryList = async () => {
  loadingHistory.value = true
  try {
    const res = await $fetch<any[]>(`${apiBase}/shift-logbook/handovers`)
    historyList.value = res || []
  } catch (err) {
    console.error('Failed to load history list:', err)
  } finally {
    loadingHistory.value = false
  }
}

const viewHistoryDetail = async (id: number) => {
  try {
    const detail = await $fetch<any>(`${apiBase}/shift-logbook/handovers/${id}`)
    $q.dialog({
      title: `รายละเอียดการส่งกะ #${detail.id}`,
      message: `Plant ${detail.plant} | ${detail.shift_type} (${detail.shift_date})<br>
                <strong>ผู้ส่ง:</strong> ${detail.outgoing_operator_name || '-'} | <strong>ผู้รับ:</strong> ${detail.incoming_operator_name || '-'}<br>
                <strong>ยอดผลิต:</strong> ${formatNumber(detail.production_kpis?.total_volume_kg || 0)} kg | <strong>Batches:</strong> ${detail.production_kpis?.completed_batches || 0}<br>
                <strong>โน้ต:</strong> ${detail.outgoing_notes || '-'}`,
      html: true,
      ok: { label: 'ปิด', color: 'primary' }
    })
  } catch (err) {
    console.error(err)
  }
}

// Lifecycle & Timers
let shiftTimer: any = null

onMounted(async () => {
  await loadCurrentShiftInfo()
  await loadShiftData()
  await loadHistoryList()

  // Update timer every 30s
  shiftTimer = setInterval(loadCurrentShiftInfo, 30000)
})

onUnmounted(() => {
  if (shiftTimer) clearInterval(shiftTimer)
})
</script>

<style scoped>
.bg-dark-page {
  background-color: #0b0f19;
}
.bg-slate {
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.kpi-card {
  border-radius: 12px;
  transition: transform 0.2s, box-shadow 0.2s;
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
.custom-table :deep(thead tr th) {
  background-color: #111827;
  color: #94a3b8;
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
}
.custom-table :deep(tbody tr:hover) {
  background-color: rgba(255, 255, 255, 0.04) !important;
}
.issue-card {
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  transition: all 0.2s;
}
.border-critical {
  border-left: 4px solid #ef4444 !important;
}
.border-high {
  border-left: 4px solid #f97316 !important;
}
.border-medium {
  border-left: 4px solid #eab308 !important;
}
.border-low {
  border-left: 4px solid #3b82f6 !important;
}
</style>
