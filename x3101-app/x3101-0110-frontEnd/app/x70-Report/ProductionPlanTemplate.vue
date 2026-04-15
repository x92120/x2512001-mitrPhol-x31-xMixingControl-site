<template>
<div class="a4-page report-container">
  <div class="header text-center q-mb-xl">
    <h1 class="text-h4 text-weight-bold">Production Plan Overview</h1>
    <h2 class="text-h6 text-grey-8">Mitr Phol Sugar Corp., Ltd.</h2>
  </div>

  <div class="row q-col-gutter-md q-mb-lg">
    <div class="col-6">
      <div class="info-group">
        <label class="text-caption text-grey-7 text-uppercase">Plan ID</label>
        <div class="text-subtitle1 text-weight-medium">{{ plan.plan_id }}</div>
      </div>
    </div>
    <div class="col-6">
      <div class="info-group">
        <label class="text-caption text-grey-7 text-uppercase">Status</label>
        <div class="text-subtitle1 text-weight-medium text-primary">{{ plan.status }}</div>
      </div>
    </div>
    
    <div class="col-6">
      <div class="info-group">
        <label class="text-caption text-grey-7 text-uppercase">SKU</label>
        <div class="text-subtitle1">{{ plan.sku_id }} - {{ plan.sku_name || 'N/A' }}</div>
      </div>
    </div>
    <div class="col-6">
      <div class="info-group">
        <label class="text-caption text-grey-7 text-uppercase">Plant</label>
        <div class="text-subtitle1">{{ plan.plant || 'Main Mixing' }}</div>
      </div>
    </div>

    <div class="col-4">
      <div class="info-group">
        <label class="text-caption text-grey-7 text-uppercase">Start Date</label>
        <div class="text-subtitle1">{{ plan.start_date || '-' }}</div>
      </div>
    </div>
    <div class="col-4">
      <div class="info-group">
        <label class="text-caption text-grey-7 text-uppercase">End Date</label>
        <div class="text-subtitle1">{{ plan.end_date || '-' }}</div>
      </div>
    </div>
    <div class="col-4">
      <div class="info-group">
        <label class="text-caption text-grey-7 text-uppercase">Target Volume</label>
        <div class="text-subtitle1 text-weight-bold">{{ plan.total_volume }} kg</div>
      </div>
    </div>
  </div>

  <div class="q-mt-xl">
    <h3 class="text-h6 text-weight-medium q-mb-md">Ingredient Requirements Summary</h3>
    <table class="report-table">
      <thead>
        <tr>
          <th class="text-left">Ingredient Code</th>
          <th class="text-left">Name</th>
          <th class="text-right">Required (kg)</th>
          <th class="text-right">Completed (kg)</th>
          <th class="text-center">Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in plan.ingredients" :key="item.re_code">
          <td>{{ item.re_code }}</td>
          <td>{{ item.ingredient_name }}</td>
          <td class="text-right">{{ item.total_require }}</td>
          <td class="text-right">{{ item.total_packaged }}</td>
          <td class="text-center">
            <span v-if="item.status === 2" class="status-badge complete">Complete</span>
            <span v-else-if="item.status === 1" class="status-badge in-progress">In Progress</span>
            <span v-else class="status-badge wait">Wait</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>

<div class="page-break"></div>

<div class="a4-page report-container">
  <div class="header q-mb-lg">
    <h1 class="text-h5 text-weight-bold">Batch Progress Details</h1>
    <h2 class="text-subtitle2 text-grey-8">Plan: {{ plan.plan_id }}</h2>
  </div>

  <table class="report-table">
    <thead>
      <tr>
        <th class="text-left">Batch ID</th>
        <th class="text-left">Status</th>
        <th class="text-right">Volume (kg)</th>
        <th class="text-center">Boxed Items</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="batch in plan.batches" :key="batch.batch_id">
        <td class="text-weight-medium">{{ batch.batch_id }}</td>
        <td>
            <span class="status-badge" :class="batch.statusColorClass">{{ batch.statusLabel }}</span>
        </td>
        <td class="text-right">{{ batch.batch_size }}</td>
        <td class="text-center">{{ batch.itemsCompleted }} / {{ batch.itemsTotal }}</td>
      </tr>
    </tbody>
  </table>
  
  <div class="footer q-mt-xl text-right text-caption text-grey-6">
    Report Generated: {{ new Date().toLocaleString() }}
  </div>
</div>
</template>

<script setup lang="ts">
const props = defineProps({
  plan: {
    type: Object,
    required: true,
    default: () => ({ ingredients: [], batches: [] })
  }
})
</script>
