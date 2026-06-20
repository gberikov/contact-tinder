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
  ],
});
