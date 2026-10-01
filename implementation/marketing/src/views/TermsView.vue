<script setup lang="ts">
import LegalPage from '@/components/legal/LegalPage.vue'
import { termsOfService } from '@/lib/legal/terms.generated.ts'
</script>

<template>
  <LegalPage :doc="termsOfService" badge="Legal Terms" />
</template>
