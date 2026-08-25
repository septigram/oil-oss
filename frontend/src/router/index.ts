import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAuthStore } from '@/stores/authStore'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/pages/LoginPage.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', name: 'list', component: () => import('@/pages/IncidentListPage.vue') },
        { path: 'incidents/new', name: 'create', component: () => import('@/pages/IncidentEditPage.vue') },
        { path: 'incidents/:id', name: 'detail', component: () => import('@/pages/IncidentDetailPage.vue') },
        { path: 'incidents/:id/edit', name: 'edit', component: () => import('@/pages/IncidentEditPage.vue') },
        { path: 'procedures', name: 'procedure-list', component: () => import('@/pages/ProcedureListPage.vue') },
        { path: 'procedures/new', name: 'procedure-create', component: () => import('@/pages/ProcedureEditPage.vue') },
        { path: 'procedures/:id', name: 'procedure-detail', component: () => import('@/pages/ProcedureDetailPage.vue') },
        { path: 'procedures/:id/edit', name: 'procedure-edit', component: () => import('@/pages/ProcedureEditPage.vue') },
        {
          path: 'masters',
          name: 'masters',
          component: () => import('@/pages/MastersPage.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'admin/users',
          name: 'admin-users',
          component: () => import('@/pages/AdminUsersPage.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'admin/webhook-api-keys',
          name: 'admin-webhook-api-keys',
          component: () => import('@/pages/AdminWebhookApiKeysPage.vue'),
          meta: { requiresAdmin: true },
        },
        {
          path: 'notification-channels',
          name: 'notification-channels',
          component: () => import('@/pages/NotificationChannelsPage.vue'),
          meta: { requiresOperator: true },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.initialize(() => {
    const current = router.currentRoute.value
    if (current.name !== 'login') {
      router.push({ name: 'login', query: { redirect: current.fullPath } })
    }
  })

  if (to.meta.public) {
    if (to.name === 'login' && auth.isAuthenticated && auth.authEnabled) {
      return { name: 'list' }
    }
    return true
  }

  if (auth.authEnabled && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'list' }
  }

  if (to.meta.requiresOperator && !auth.isAdmin && !auth.isOperator) {
    return { name: 'list' }
  }

  return true
})

export default router
