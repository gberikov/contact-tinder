import { createRouter, createWebHistory } from 'vue-router';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/snapshots' },
    { path: '/accounts', name: 'accounts', component: () => import('@/pages/Accounts.vue') },
    { path: '/snapshots', name: 'snapshots', component: () => import('@/pages/Snapshots.vue') },
    {
      path: '/snapshots/:id',
      name: 'snapshot',
      component: () => import('@/pages/Snapshot.vue'),
    },
    {
      path: '/working-copies',
      name: 'working-copies',
      component: () => import('@/pages/WorkingCopies.vue'),
    },
    {
      path: '/working-copies/:id/dedup',
      name: 'working-copy-dedup',
      component: () => import('@/pages/WorkingCopyDedup.vue'),
    },
    {
      path: '/working-copies/:id/triage',
      name: 'working-copy-triage',
      component: () => import('@/pages/WorkingCopyTriage.vue'),
    },
    {
      path: '/triage-sessions/:id/processing',
      name: 'triage-processing',
      component: () => import('@/pages/Processing.vue'),
    },
    {
      path: '/working-copies/:id/delete-review',
      name: 'delete-review',
      component: () => import('@/pages/DeleteReview.vue'),
    },
  ],
});
