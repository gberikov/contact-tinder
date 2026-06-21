import { createRouter, createWebHistory } from 'vue-router';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Guided wizard (feature 005) — persistent stepper shell with one child per step.
    {
      path: '/wizard',
      component: () => import('@/components/wizard/WizardLayout.vue'),
      children: [
        { path: '', redirect: '/wizard/connect' },
        {
          path: 'connect',
          name: 'connect',
          component: () => import('@/pages/wizard/ConnectStep.vue'),
        },
        {
          path: 'backup',
          name: 'backup',
          component: () => import('@/pages/wizard/BackupStep.vue'),
        },
        { path: 'draft', name: 'draft', component: () => import('@/pages/wizard/DraftStep.vue') },
        // Merge/Review/Export reuse the existing detail pages, driven by the active Draft.
        { path: 'merge', name: 'merge', component: () => import('@/pages/WorkingCopyDedup.vue') },
        {
          path: 'review',
          name: 'review',
          component: () => import('@/pages/WorkingCopyTriage.vue'),
        },
        { path: 'export', name: 'export', component: () => import('@/pages/Export.vue') },
      ],
    },

    // Entry point → the wizard.
    { path: '/', redirect: '/wizard/connect' },

    // Legacy paths → fold into the matching wizard step (FR-007 deep-link compatibility).
    { path: '/accounts', redirect: '/wizard/connect' },
    { path: '/snapshots', redirect: '/wizard/backup' },
    { path: '/working-copies', redirect: '/wizard/draft' },
    { path: '/working-copies/:id/dedup', redirect: '/wizard/merge' },
    { path: '/working-copies/:id/triage', redirect: '/wizard/review' },
    { path: '/working-copies/:id/export', redirect: '/wizard/export' },
    { path: '/working-copies/:id/delete-review', redirect: '/wizard/review' },
    { path: '/triage-sessions/:id/processing', redirect: '/wizard/review' },

    // Legacy detail pages still reachable directly when an :id is supplied.
    {
      path: '/snapshots/:id',
      name: 'snapshot',
      component: () => import('@/pages/Snapshot.vue'),
    },
  ],
});
