import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'

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
    { path: '/signin', name: 'signin', component: () => import('@/views/SignInView.vue') },

    // Token landing pages. These paths are NOT free to change: `apps/accounts/tasks.py`
    // builds `{FRONTEND_BASE_URL}/verify?token=` and `/reset?token=` into emails that
    // have already been delivered to customers, so any rename orphans live links.
    // `meta.bare` drops the site nav and footer (design §2.1 — the chrome is cloned from
    // Sign in `505:124`): someone who arrived from an email is mid-task, and a nav bar
    // here invites them to wander off before the account is verified.
    { path: '/verify', name: 'verify', component: () => import('@/views/VerifyView.vue'), meta: { bare: true } },
    { path: '/reset', name: 'reset', component: () => import('@/views/ResetView.vue'), meta: { bare: true } },
    { path: '/account', name: 'account', component: () => import('@/views/AccountView.vue') },
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
  ]
})

export default router
