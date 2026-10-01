<script setup lang="ts">
import LegalPage from '@/components/legal/LegalPage.vue'
import { privacyPolicy } from '@/lib/legal/privacy.generated.ts'
</script>

<template>
  <LegalPage :doc="privacyPolicy" badge="Legal Notice" />
</template>
