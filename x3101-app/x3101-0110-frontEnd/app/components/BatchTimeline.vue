<template>
  <svg
    width="100%" height="100%"
    :viewBox="`0 0 ${svgW} ${svgH}`"
    preserveAspectRatio="xMidYMid meet"
    xmlns="http://www.w3.org/2000/svg"
    class="batch-timeline"
    style="display:block;overflow:visible;"
  >
    <!-- ── BATCH ID label (top-left) ── -->
    <rect :x="c(0)-28" :y="FH_Y-22" width="56" height="16" rx="3" fill="#e8eaf6"/>
    <text :x="c(0)" :y="FH_Y-10" text-anchor="middle"
          style="font-size:8px;font-family:Arial,sans-serif;font-weight:bold;fill:#1a237e">
      {{ batchId ? batchId.split('-').slice(-1)[0] : 'Batch' }}
    </text>

    <!-- FH track horizontal line -->
    <line :x1="c(0)" :y1="FH_Y" :x2="c(3)" :y2="FH_Y"
          :stroke="lineColor(fhTransferred)" stroke-width="1.5" stroke-linecap="round"/>
    <!-- SPP track horizontal line -->
    <line :x1="c(0)" :y1="SPP_Y" :x2="c(3)" :y2="SPP_Y"
          :stroke="lineColor(sppTransferred)" stroke-width="1.5" stroke-linecap="round"/>
    <!-- Vertical connector at col0 -->
    <line :x1="c(0)" :y1="FH_Y" :x2="c(0)" :y2="SPP_Y"
          stroke="#9fa8da" stroke-width="1.5"/>
    <!-- FH merge drop -->
    <line :x1="c(3)" :y1="FH_Y" :x2="c(3)" :y2="MERGE_Y"
          :stroke="lineColor(fhTransferred && sppTransferred)" stroke-width="1.5"/>
    <!-- SPP merge drop -->
    <line :x1="c(3)" :y1="SPP_Y" :x2="c(3)" :y2="MERGE_Y"
          :stroke="lineColor(fhTransferred && sppTransferred)" stroke-width="1.5"/>
    <!-- Downstream line -->
    <line :x1="c(3)" :y1="MERGE_Y" :x2="c(7)" :y2="MERGE_Y"
          :stroke="lineColor(merged)" stroke-width="1.5" stroke-linecap="round"/>
    <!-- Arrow head -->
    <polygon
      :points="`${c(7)-1},${MERGE_Y-4} ${c(7)+6},${MERGE_Y} ${c(7)-1},${MERGE_Y+4}`"
      :fill="merged ? '#1a237e' : '#cccccc'"
    />

    <!-- COL0: Batch start node -->
    <circle :cx="c(0)" :cy="FH_Y" r="7" :fill="nodeColor(true)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(0)" :y="FH_Y+3.5" text-anchor="middle"
          style="font-size:7px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">B</text>

    <!-- COL1: Prepare FH -->
    <circle :cx="c(1)" :cy="FH_Y" r="7" :fill="nodeColor(fhPrepared)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(1)" :y="FH_Y-13" text-anchor="middle"
          style="font-size:7.5px;font-family:Arial,sans-serif;font-weight:bold;fill:#1565c0">Prepare</text>
    <text :x="c(1)" :y="FH_Y-4" text-anchor="middle"
          style="font-size:6px;font-family:Arial,sans-serif;fill:#1565c0">(FH)</text>
    <text :x="c(1)" :y="FH_Y+3.5" text-anchor="middle"
          style="font-size:7px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">P</text>

    <!-- COL2: Boxed FH -->
    <circle :cx="c(2)" :cy="FH_Y" r="7" :fill="nodeColor(fhBoxed)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(2)" :y="FH_Y+14" text-anchor="middle"
          style="font-size:7.5px;font-family:Arial,sans-serif;fill:#555555">Boxed</text>
    <text :x="c(2)" :y="FH_Y+3.5" text-anchor="middle"
          style="font-size:7px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">⬜</text>

    <!-- COL3: Transfer FH -->
    <text :x="c(3)" :y="FH_Y-13" text-anchor="middle"
          style="font-size:7.5px;font-family:Arial,sans-serif;fill:#555555">Transfer</text>
    <circle :cx="c(3)" :cy="FH_Y" r="7" :fill="nodeColor(fhTransferred)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(3)" :y="FH_Y+3.5" text-anchor="middle"
          style="font-size:7px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">T</text>

    <!-- COL0: SPP start -->
    <circle :cx="c(0)" :cy="SPP_Y" r="5" fill="#9fa8da" stroke="#ffffff" stroke-width="1.5"/>

    <!-- COL1: Prepare SPP -->
    <circle :cx="c(1)" :cy="SPP_Y" r="7" :fill="nodeColor(sppPrepared)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(1)" :y="SPP_Y+16" text-anchor="middle"
          style="font-size:7.5px;font-family:Arial,sans-serif;font-weight:bold;fill:#0277bd">Prepare</text>
    <text :x="c(1)" :y="SPP_Y+24" text-anchor="middle"
          style="font-size:6px;font-family:Arial,sans-serif;fill:#0277bd">(SPP)</text>
    <text :x="c(1)" :y="SPP_Y+3.5" text-anchor="middle"
          style="font-size:7px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">P</text>

    <!-- COL2: Boxed SPP -->
    <circle :cx="c(2)" :cy="SPP_Y" r="7" :fill="nodeColor(sppBoxed)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(2)" :y="SPP_Y+3.5" text-anchor="middle"
          style="font-size:7px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">⬜</text>

    <!-- COL3: Transfer SPP -->
    <circle :cx="c(3)" :cy="SPP_Y" r="7" :fill="nodeColor(sppTransferred)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(3)" :y="SPP_Y+3.5" text-anchor="middle"
          style="font-size:7px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">T</text>

    <!-- Merge diamond -->
    <polygon
      :points="`${c(3)},${MERGE_Y-9} ${c(3)+9},${MERGE_Y} ${c(3)},${MERGE_Y+9} ${c(3)-9},${MERGE_Y}`"
      :fill="nodeColor(fhTransferred && sppTransferred)"
      stroke="#ffffff" stroke-width="1.5"
    />

    <!-- COL4: Boxed merged -->
    <circle :cx="c(4)" :cy="MERGE_Y" r="8" :fill="nodeColor(merged)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(4)" :y="MERGE_Y-14" text-anchor="middle"
          style="font-size:7.5px;font-family:Arial,sans-serif;fill:#555555">Boxed</text>
    <text :x="c(4)" :y="MERGE_Y+3.5" text-anchor="middle"
          style="font-size:8px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">✓</text>

    <!-- COL5: Transfer merged -->
    <circle :cx="c(5)" :cy="MERGE_Y" r="8" :fill="nodeColor(merged)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(5)" :y="MERGE_Y-14" text-anchor="middle"
          style="font-size:7.5px;font-family:Arial,sans-serif;fill:#555555">Transfer</text>
    <text :x="c(5)" :y="MERGE_Y+3.5" text-anchor="middle"
          style="font-size:9px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">→</text>

    <!-- COL6: Production -->
    <circle :cx="c(6)" :cy="MERGE_Y" r="8" :fill="nodeColor(inProduction)" stroke="#ffffff" stroke-width="1.5"/>
    <text :x="c(6)" :y="MERGE_Y-14" text-anchor="middle"
          style="font-size:7.5px;font-family:Arial,sans-serif;fill:#555555">Production</text>
    <text :x="c(6)" :y="MERGE_Y+3.5" text-anchor="middle"
          style="font-size:9px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">⚙</text>

    <!-- COL7: Finish -->
    <circle :cx="c(7)" :cy="MERGE_Y" r="9"
            :fill="finished ? '#2e7d32' : '#e0e0e0'"
            :stroke="finished ? '#ffffff' : '#bdbdbd'" stroke-width="2"/>
    <text :x="c(7)" :y="MERGE_Y-15" text-anchor="middle"
          style="font-size:7.5px;font-family:Arial,sans-serif;fill:#555555">Finish</text>
    <text :x="c(7)" :y="MERGE_Y+3.5" text-anchor="middle"
          style="font-size:9px;font-family:Arial,sans-serif;font-weight:bold;fill:#ffffff">🏁</text>

  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  batchId:       string | null
  fhPrepared:    boolean
  fhBoxed:       boolean
  fhTransferred: boolean
  sppPrepared:   boolean
  sppBoxed:      boolean
  sppTransferred:boolean
  inProduction?: boolean
  finished?:     boolean
}>()

// Layout constants
const svgW   = 560
const svgH   = 130
const FH_Y   = 30    // top track y
const SPP_Y  = 75    // bottom track y
const MERGE_Y= 100   // merged flow y

// Column x positions (8 fixed columns)
const COL = [28, 100, 170, 250, 320, 390, 460, 530] as const
type ColIndex = 0|1|2|3|4|5|6|7
const c = (i: ColIndex) => COL[i]

// Helpers
const merged      = computed(() => props.fhTransferred && props.sppTransferred)
const inProduction = computed(() => props.inProduction ?? false)
const finished     = computed(() => props.finished ?? false)

const nodeColor = (active: boolean) =>
  active ? '#1a237e' : '#e0e0e0'

const lineColor = (active: boolean) =>
  active ? '#1a237e' : '#cccccc'
</script>

<style scoped>
.batch-timeline { display:block; }
</style>
