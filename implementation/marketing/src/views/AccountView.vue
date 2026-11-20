<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { SIGN_OUT_LABEL, SIGN_OUT_PENDING_LABEL } from '@/lib/auth/signOutFlow.ts'
import { useSignOut } from '@/lib/auth/useSignOut.ts'
import SrOnly from '@/components/core/SrOnly.vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { accountOverview, deactivateOwnDevice } from '@/lib/api/account.ts'
import { createAccountPageFlow, LOAD_FAILED } from '@/lib/accountPageFlow.ts'
import { forgetSession } from '@/lib/auth/sessionStore.ts'
import { newIdempotencyKey } from '@/lib/auth/signupPolicy.ts'
import {
  countLeftLine,
  countUsed,
  deviceLabel,
  formatAccountDate,
  formatPlanEnd,
  quotaUnavailable,
  minutesLeftLine,
  minutesUsed,
} from '@/lib/accountDisplay.ts'

/**
 * Sign out for real (ClickUp 17tnw2b2cbr). This was a link to /signin: it navigated and never
 * revoked anything, so the server session, the cookie and the session hint all survived. It now
 * runs the same revocation the navbar's Sign out does, and only then lands on /signin. If the
 * server cannot be reached the visitor is told so and stays signed in, because that is the truth:
 * the cookie is HttpOnly and only the server can end the session. The rules live in
 * `lib/auth/signOutFlow.ts`.
 */
const { pending: signOutPending, error: signOutError, run: runSignOut } = useSignOut()
const signOutButton = ref<InstanceType<typeof UiButton> | null>(null)

const handleSignOut = async () => {
  await runSignOut()
  if (signOutError.value === '') return
  // A disabled button gives up focus. After a failure the visitor is still here and is meant to
  // retry, so put focus back where they were rather than leaving a keyboard user on <body>.
  await nextTick()
  ;(signOutButton.value?.$el as HTMLElement | undefined)?.focus()
}

/**
 * The page shows only what `accountOverview` returns (ClickUp 17tnw2bhkd2). It used to be mock data
 * (a Pro plan, invoices, a licence key, Bible entitlements); none of that exists on the server, so
 * none of it is here. Load and deactivate rules live in `lib/accountPageFlow.ts`.
 */
const router = useRouter()
const flow = createAccountPageFlow({
  fetchOverview: accountOverview,
  deactivate: (id, requestId) => deactivateOwnDevice(id, requestId),
  onSessionEnded: () => {
    forgetSession()
    void router.replace({ path: '/signin', query: { next: '/account', reason: 'expired' } })
  },
  newRequestId: newIdempotencyKey,
})
const {
  status,
  overview,
  loadingMore,
  loadMoreError,
  confirmingId,
  deactivatingId,
  deactivateError,
  notice,
  load,
  loadMore,
  askDeactivate,
  cancelDeactivate,
  confirmDeactivate,
} = flow

onMounted(() => {
  void load()
})
onBeforeUnmount(() => flow.abort())

const LICENSE_STATUS: Record<string, string> = {
  ACTIVATED: 'Active',
  EXPIRING: 'Expiring soon',
  EXPIRED: 'Expired',
  SUSPENDED: 'Suspended',
  REVOKED: 'Revoked',
  CONVERTED: 'Converted',
  ARCHIVED: 'Archived',
}
const licenseStatusLabel = (value: string) => LICENSE_STATUS[value] ?? value.charAt(0) + value.slice(1).toLowerCase()
const ROLE_LABEL: Record<string, string> = { ADMIN: 'Administrator', MEMBER: 'Member' }
const roleLabel = (value: string) => ROLE_LABEL[value] ?? value.charAt(0) + value.slice(1).toLowerCase()

const planEnd = () => formatPlanEnd(overview.value?.allowance?.planEndsAt ?? null)
</script>

<template>
  <div class="account-portal">
    <div class="container">
      <!-- Portal Top Header -->
      <header class="portal-header">
        <div class="user-lockup">
          <div class="avatar">{{ overview?.orgName.charAt(0) || 'S' }}</div>
          <div>
            <h1 class="org-title">{{ overview?.orgName || 'Your account' }}</h1>
            <p v-if="overview" class="user-sub">
              {{ overview.displayName }} ({{ overview.email }}) &middot; <span class="role-tag">{{ roleLabel(overview.role) }}</span>
            </p>
          </div>
        </div>
        <div class="header-actions">
          <!-- A real <button>, not a link: it has to revoke the session before anything navigates. -->
          <UiButton
            ref="signOutButton"
            type="button"
            variant="outline"
            size="sm"
            :disabled="signOutPending"
            @click="handleSignOut"
          >
            {{ signOutPending ? SIGN_OUT_PENDING_LABEL : SIGN_OUT_LABEL }}
          </UiButton>
          <!-- A disabled button drops focus, so without this a screen-reader user hears nothing until the page
               changes. Always in the DOM and empty when idle: a live region added together with its text is not
               reliably announced. Visually hidden and absolutely positioned (SrOnly), so it moves nothing. -->
          <SrOnly role="status" aria-live="polite">{{ signOutPending ? SIGN_OUT_PENDING_LABEL : '' }}</SrOnly>
          <!-- Announced: a sign-out that silently did nothing is the failure most worth hearing about. -->
          <p v-if="signOutError" class="signout-error" role="alert">{{ signOutError }}</p>
        </div>
      </header>

      <!-- Loading -->
      <div v-if="status === 'loading'" class="portal-card" role="status" aria-live="polite">
        <p class="card-subtitle loading-text">Loading your account&hellip;</p>
        <SkeletonLoader :lines="4" :widths="[30, 80, 100, 50]" />
      </div>

      <!-- Error -->
      <div v-else-if="status === 'error' || !overview" class="alert-banner past-due" role="alert">
        <svg viewBox="0 0 20 20" fill="currentColor" class="alert-icon" aria-hidden="true">
          <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>
        <span>{{ LOAD_FAILED }}</span>
        <UiButton type="button" variant="outline" size="sm" @click="load()">Try again</UiButton>
      </div>

      <div v-else class="portal-content">
        <p v-if="notice" class="notice" role="status">{{ notice }}</p>
        <p v-if="deactivateError" class="signout-error" role="alert">{{ deactivateError }}</p>

        <!-- PLAN -->
        <section class="portal-card" aria-labelledby="plan-heading">
          <div class="card-header">
            <div>
              <h2 id="plan-heading">Plan</h2>
              <p class="card-subtitle">What your church can use today</p>
            </div>
            <UiBadge v-if="overview.license" :variant="overview.license.validNow ? 'preview' : 'warn'">
              {{ licenseStatusLabel(overview.license.status) }}
            </UiBadge>
          </div>

          <div class="plan-summary-box">
            <div class="summary-col">
              <span class="label">Current plan</span>
              <span class="value-highlight">{{ overview.allowance?.planDisplayName ?? 'No plan' }}</span>
              <span v-if="planEnd()" class="value">until {{ planEnd() }}</span>
            </div>
            <div v-if="overview.license" class="summary-col">
              <span class="label">Licence</span>
              <span class="value">{{ licenseStatusLabel(overview.license.status) }}</span>
              <span v-if="formatPlanEnd(overview.license.expiresAt)" class="value">
                Valid until {{ formatPlanEnd(overview.license.expiresAt) }}
              </span>
            </div>
            <div v-if="overview.license" class="summary-col">
              <span class="label">Computers</span>
              <span class="value">{{ overview.license.activeDeviceCount }} of {{ overview.license.deviceLimit }} computers</span>
            </div>
          </div>
        </section>

        <!-- THIS WEEK -->
        <section v-if="overview.allowance" class="portal-card" aria-labelledby="week-heading">
          <div class="card-header">
            <div>
              <h2 id="week-heading">This week</h2>
              <p v-if="formatAccountDate(overview.allowance.stt.resetsAt)" class="card-subtitle">
                Resets {{ formatAccountDate(overview.allowance.stt.resetsAt) }}
              </p>
            </div>
          </div>

          <div class="plan-summary-box">
            <div class="summary-col">
              <span class="label">Cloud transcription</span>
              <span class="value-highlight">{{ quotaUnavailable(overview.allowance.stt) ? 'Not available yet' : minutesLeftLine(overview.allowance.stt) || 'Not available' }}</span>
              <span v-if="!quotaUnavailable(overview.allowance.stt) && minutesUsed(overview.allowance.stt) !== null" class="value">
                {{ minutesUsed(overview.allowance.stt) }} min used
              </span>
            </div>
            <div class="summary-col">
              <span class="label">Notes</span>
              <span class="value-highlight">{{ quotaUnavailable(overview.allowance.notes) ? 'Not available yet' : countLeftLine(overview.allowance.notes) || 'Not available' }}</span>
              <span v-if="!quotaUnavailable(overview.allowance.notes) && countUsed(overview.allowance.notes) !== null" class="value">
                {{ countUsed(overview.allowance.notes) }} used
              </span>
            </div>
          </div>
        </section>

        <!-- DEVICES -->
        <section class="portal-card" aria-labelledby="devices-heading">
          <div class="card-header">
            <div>
              <h2 id="devices-heading">Computers</h2>
              <p class="card-subtitle">Computers signed in to SelahCue for your church</p>
            </div>
          </div>

          <p v-if="overview.devices.nodes.length === 0" class="card-subtitle">No computers are registered yet.</p>
          <div
            v-else
            class="table-responsive"
            tabindex="0"
            role="region"
            aria-label="Registered computers, scrolls sideways when wide"
          >
            <table class="data-table">
              <thead>
                <tr>
                  <th>Computer</th>
                  <th>Platform</th>
                  <th>Added</th>
                  <th v-if="overview.canDeactivateDevices">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="dev in overview.devices.nodes" :key="dev.publicId">
                  <td class="font-medium">{{ deviceLabel(dev) }}</td>
                  <td>{{ dev.platform }}<template v-if="dev.appVersion"> &middot; v{{ dev.appVersion }}</template></td>
                  <td>{{ formatAccountDate(dev.createdAt) }}</td>
                  <td v-if="overview.canDeactivateDevices">
                    <span v-if="dev.status !== 'ACTIVE'" class="current-tag">Deactivated</span>
                    <span v-else-if="confirmingId === dev.publicId" class="confirm-step" role="group" aria-label="Confirm deactivation">
                      <strong>Deactivate this computer?</strong>
                      <button type="button" class="btn-text-danger" :disabled="deactivatingId !== ''" @click="confirmDeactivate(dev.publicId)">
                        Yes, deactivate
                      </button>
                      <button type="button" class="btn-link" :disabled="deactivatingId !== ''" @click="cancelDeactivate">
                        Cancel
                      </button>
                    </span>
                    <button
                      v-else
                      type="button"
                      class="btn-text-danger"
                      :aria-label="`Deactivate ${deviceLabel(dev)}`"
                      @click="askDeactivate(dev.publicId)"
                    >
                      Deactivate
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="loadMoreError" class="signout-error" role="alert">{{ loadMoreError }}</p>
          <div v-if="overview.devices.nextCursor" class="card-actions more-actions">
            <UiButton type="button" variant="outline" size="sm" :disabled="loadingMore" @click="loadMore">
              Show more computers
            </UiButton>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.account-portal {
  padding: 40px 0 80px;
  background: var(--sc-base);
  min-height: calc(100vh - 80px);
}

.container {
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 var(--page-gutter);
}

/* Header */
.portal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--sc-border);
}

.user-lockup {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-actions {
  /* The containing block for the visually hidden status region (see SrOnly): an uncontained one can widen the page. */
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  max-width: 320px;
}

/* The same soft-red surface as the past-due banner below, so a failed action reads as one. */
.signout-error {
  margin: 0;
  padding: 8px 12px;
  background: var(--sc-live-soft);
  border: 1px solid var(--sc-live-border);
  border-radius: 8px;
  color: var(--sc-text);
  font-size: 13px;
  line-height: 1.4;
  text-align: left;
}

.avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--sc-primary), #2b2a6b);
  color: white;
  font-weight: 700;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.org-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 4px 0;
}

.user-sub {
  font-size: 14px;
  color: var(--sc-text-secondary);
  margin: 0;
}

.role-tag {
  color: var(--sc-primary);
  font-weight: 500;
}

/* Past-due alert */
.alert-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 32px;
  font-size: 14px;
  font-weight: 500;
}

.alert-banner.past-due {
  background: var(--sc-live-soft);
  border: 1px solid var(--sc-live-border);
  color: var(--sc-text);
}

.alert-icon {
  width: 20px;
  height: 20px;
  color: var(--sc-live);
  flex-shrink: 0;
}

/* Content & Cards */
.portal-content {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.portal-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 32px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.card-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 4px 0;
}

.card-subtitle {
  font-size: 14px;
  color: var(--sc-text-secondary);
  margin: 0;
}

/* Summary Box */
.plan-summary-box {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
}

.summary-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-col .label {
  font-size: 12px;
  color: var(--sc-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.value-highlight {
  font-size: 22px;
  font-weight: 700;
  color: var(--sc-primary);
}

.summary-col .value {
  font-size: 15px;
  color: var(--sc-text);
  font-weight: 500;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Data Table */
.table-responsive {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 14px;
}

.data-table th {
  background: var(--sc-elevated);
  color: var(--sc-text-muted);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 12px 16px;
  border-bottom: 1px solid var(--sc-border);
}

.data-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--sc-border);
  color: var(--sc-text-secondary);
}

.data-table tr:last-child td {
  border-bottom: none;
}

.font-medium { font-weight: 500; color: var(--sc-text); }
.current-tag { color: var(--sc-preview); font-size: 12px; margin-left: 6px; }

.btn-text-danger {
  background: none;
  border: none;
  color: var(--sc-live);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.btn-text-danger:hover { text-decoration: underline; }

.btn-link {
  background: none;
  border: none;
  color: var(--sc-primary);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.btn-link:hover { text-decoration: underline; }

.btn-text-danger:disabled, .btn-link:disabled { opacity: 0.6; cursor: not-allowed; }

/* The in-page confirm step for deactivating a computer. */
.confirm-step {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  color: var(--sc-text);
}

.notice {
  margin: 0;
  padding: 8px 12px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  color: var(--sc-text);
  font-size: 13px;
  line-height: 1.4;
}

.loading-text { margin-bottom: 16px; }
.more-actions { margin-top: 16px; }

/* Cards are always 1-up (no sidebar), so tablet only needs tighter chrome; the real
   reflow is below 768. */
@media (max-width: 1023.98px) {
  .plan-summary-box { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 767.98px) {
  .account-portal { padding: 24px 0 var(--section-pad-sm); }

  .portal-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 24px;
    padding-bottom: 20px;
  }
  .header-actions { align-items: flex-start; max-width: none; }
  .user-lockup { gap: 12px; min-width: 0; }
  .user-lockup > div { min-width: 0; }
  .org-title { font-size: 20px; overflow-wrap: anywhere; }
  .user-sub { overflow-wrap: anywhere; }

  .alert-banner { flex-direction: column; align-items: flex-start; gap: 12px; margin-bottom: 24px; }

  .portal-content { gap: 20px; }
  .portal-card { padding: 20px; border-radius: 14px; }
  .card-header { flex-wrap: wrap; gap: 10px 12px; margin-bottom: 20px; }

  .plan-summary-box { grid-template-columns: minmax(0, 1fr); padding: 16px; gap: 16px; }
  .summary-col .value { overflow-wrap: anywhere; }

  .card-actions { flex-direction: column; align-items: stretch; }
  .card-actions > * { width: 100%; }

  /* Wide tables scroll inside .table-responsive; their cells do not wrap into slivers. */
  .table-responsive { -webkit-overflow-scrolling: touch; }
  .data-table th, .data-table td { white-space: nowrap; }
  .btn-text-danger, .btn-link { min-height: 44px; padding: 0 8px; font-family: inherit; }

  .confirm-step { white-space: normal; }
}
</style>
