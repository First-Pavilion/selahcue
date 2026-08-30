import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import { confirmSession, refreshIfExpiringSoon } from '@/lib/auth/sessionStore.ts'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to) {
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0, behavior: 'smooth' }
  },
  routes: [
    // Marketing Site Routes
    { path: '/', name: 'home', component: HomeView },
    { path: '/features', name: 'features', component: () => import('@/views/FeaturesView.vue') },
    { path: '/pricing', name: 'pricing', component: () => import('@/views/PricingView.vue') },
    { path: '/download', name: 'download', component: () => import('@/views/DownloadView.vue') },
    { path: '/about', name: 'about', component: () => import('@/views/AboutView.vue') },
    { path: '/contact', name: 'contact', component: () => import('@/views/ContactView.vue') },
    { path: '/support', name: 'support', component: () => import('@/views/SupportView.vue') },
    { path: '/docs', name: 'docs', component: () => import('@/views/DocsView.vue') },
    { path: '/changelog', name: 'changelog', component: () => import('@/views/ChangelogView.vue') },
    { path: '/blog', name: 'blog', component: () => import('@/views/BlogView.vue') },
    { path: '/careers', name: 'careers', component: () => import('@/views/CareersView.vue') },
    { path: '/privacy', name: 'privacy', component: () => import('@/views/PrivacyView.vue') },
    { path: '/terms', name: 'terms', component: () => import('@/views/TermsView.vue') },
    // The auth trio. `meta.bare` for the same reason /verify and /reset carry it (design
    // §2.1): these frames are cloned from Sign in `505:124`, which is a bare centred card
    // with its own brand lockup. Someone signing in is mid-task, and a nav bar offering
    // Features / Pricing / Download is an invitation to wander off before they finish.
    { path: '/signin', name: 'signin', component: () => import('@/views/SignInView.vue'), meta: { bare: true } },
    { path: '/signup', name: 'signup', component: () => import('@/views/SignUpView.vue'), meta: { bare: true } },
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('@/views/ForgotPasswordView.vue'),
      meta: { bare: true },
    },

    // Token landing pages. These paths are NOT free to change: `apps/accounts/tasks.py`
    // builds `{FRONTEND_BASE_URL}/verify?token=` and `/reset?token=` into emails that
    // have already been delivered to customers, so any rename orphans live links.
    // `meta.bare` drops the site nav and footer (design §2.1 — the chrome is cloned from
    // Sign in `505:124`): someone who arrived from an email is mid-task, and a nav bar
    // here invites them to wander off before the account is verified.
    { path: '/verify', name: 'verify', component: () => import('@/views/VerifyView.vue'), meta: { bare: true } },
    { path: '/reset', name: 'reset', component: () => import('@/views/ResetView.vue'), meta: { bare: true } },
    // `requiresSession` is enforced by the guard below. See its comment for what that
    // does and — more importantly — what it does not.
    {
      path: '/account',
      name: 'account',
      component: () => import('@/views/AccountView.vue'),
      meta: { requiresSession: true },
    },
    { path: '/affiliates', name: 'affiliates', component: () => import('@/views/AffiliatesView.vue') },

    // External Affiliate Portal Routes
    { path: '/affiliates/dashboard', name: 'affiliate-dashboard', component: () => import('@/views/affiliates/AffiliateDashboardView.vue') },
    { path: '/affiliates/referrals', name: 'affiliate-referrals', component: () => import('@/views/affiliates/AffiliateReferralsView.vue') },
    { path: '/affiliates/payouts', name: 'affiliate-payouts', component: () => import('@/views/affiliates/AffiliatePayoutsView.vue') },
    { path: '/affiliates/resources', name: 'affiliate-resources', component: () => import('@/views/affiliates/AffiliateResourcesView.vue') },
    { path: '/affiliates/settings', name: 'affiliate-settings', component: () => import('@/views/affiliates/AffiliateSettingsView.vue') },
    { path: '/affiliates/help', name: 'affiliate-help', component: () => import('@/views/affiliates/AffiliateHelpView.vue') },

    // Internal Staff Admin Console Routes
    { path: '/admin', name: 'admin-overview', component: () => import('@/views/admin/AdminOverviewView.vue') },
    { path: '/admin/customers', name: 'admin-customers', component: () => import('@/views/admin/AdminCustomersView.vue') },
    { path: '/admin/customers/:id', name: 'admin-customer-detail', component: () => import('@/views/admin/AdminCustomerDetailView.vue') },
    { path: '/admin/users', name: 'admin-users', component: () => import('@/views/admin/AdminUsersView.vue') },
    { path: '/admin/subscriptions', name: 'admin-subscriptions', component: () => import('@/views/admin/AdminSubscriptionsView.vue') },
    { path: '/admin/licenses', name: 'admin-licenses', component: () => import('@/views/admin/AdminLicensesView.vue') },
    { path: '/admin/affiliates', name: 'admin-affiliates', component: () => import('@/views/admin/AdminAffiliatesView.vue') },
    { path: '/admin/payouts', name: 'admin-payouts', component: () => import('@/views/admin/AdminPayoutsView.vue') },
    { path: '/admin/settings', name: 'admin-settings', component: () => import('@/views/admin/AdminSettingsView.vue') },

    // MEDIUM-4 (Cody). There was no catch-all, so any path with no route resolved with
    // ZERO matched components and rendered a BLANK PAGE. That is reachable from a link —
    // `/signin?next=/anything` signs the visitor in and leaves them looking at nothing —
    // and a blank page after a successful sign-in is exactly the dead end C-005 and FR-552
    // forbid. `safeNextPath` cannot fix this on its own: it is pure and dependency-free by
    // design and has no view of the route table, and giving it one would couple the
    // open-redirect guard to the router for a problem the router should not have had.
    //
    // Placed last so it only ever matches what nothing else did.
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
    },
  ]
})

/**
 * Keep signed-out visitors off `meta.requiresSession` routes.
 *
 * THIS IS NOT A SECURITY BOUNDARY, and reading it as one would be a mistake with
 * consequences. The server authorises every request against the `selahcue_account_session`
 * cookie; a guard living in JavaScript that anyone can step over in devtools protects
 * nothing. What it does is stop a signed-out visitor landing on a page of empty panels
 * and failed requests, and stop a signed-OUT one being told they are signed in.
 *
 * It asks the server rather than trusting local state, every time. The session hint is
 * attacker-writable localStorage and goes stale in the one direction that matters —
 * claiming a session that was revoked minutes ago by a password change or a sign-out
 * elsewhere. `confirmSession` is the only thing here that decides.
 *
 * The `unreachable` branch lets the visitor through ON PURPOSE. A transport failure says
 * nothing about whether the session is valid, and bouncing a signed-in user to a sign-in
 * page because their connection blipped signs them out of their own account and asks for
 * a password that was never the problem. Since the guard is not the boundary, letting
 * them through costs nothing: the page's own requests will fail and it will say so, which
 * is the accurate thing for it to say. Reporting "your session ended" would not be.
 */
router.beforeEach((to) => {
  // Returns a BOOLEAN, not a promise, for every route that is not guarded — which is all
  // of them but one. An `async` guard returns a promise even on the early-exit path, and
  // vue-router awaits it on every navigation, delaying the FIRST paint of every page on
  // the site to serve a check that only /account needs. That is not theoretical: it made
  // the /verify state harness flaky the moment it was introduced, because the view no
  // longer mounted inside the window that scenario allows.
  if (to.meta.requiresSession !== true) return true

  return confirmSession().then((check) => {
    if (check === 'live') {
      // Opportunistic and unawaited: extending a session that still has weeks left on it
      // must not hold up the navigation the visitor actually asked for. It is a no-op
      // unless the session is inside its last week — see the threshold's comment for why
      // rotation is done rarely rather than often.
      void refreshIfExpiringSoon()
      return true
    }
    if (check === 'unreachable') return true

    // `next` so the visitor lands where they were going once they sign in — sanitised at
    // the point of use by `safeNextPath`, never trusted as a URL here. `reason` is what
    // lets /signin say "you've been signed out" instead of showing a bare form to someone
    // who was mid-task and has no idea why they are looking at it.
    return { path: '/signin', query: { next: to.fullPath, reason: 'expired' } }
  })
})

export default router
