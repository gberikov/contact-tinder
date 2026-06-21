# Contact Tinder — Frontend

Vue 3 + TypeScript (Vite) single-page app. Styled with **shadcn-vue** (Mira style, Indigo theme)
on **Tailwind CSS v4**; **Biome** is the single linter/formatter.

## The guided wizard (feature 005)

The whole contact-cleanup pipeline is presented as one guided wizard with a persistent **Stepper**:

```
Connect → Backup → Draft → Merge → Review → Export
```

- **Connect** — link/select a Google account
- **Backup** — pull a frozen Snapshot of your contacts
- **Draft** — your editable copy (formerly "working copy")
- **Merge** — find & merge duplicates
- **Review** — swipe to keep / delete
- **Export** — push changes back to Google

State is derived client-side along a **chain of active selections** (active account → backup →
draft → its merge → review → export) over the existing read endpoints in `src/services/api.ts`; the
chain persists in `localStorage` + the route (`/wizard/:step`), so a reload restores the current
step. Long jobs (Backup import, Merge dedup, Export run) show a distinct **running** state. No
backend, OAuth, or data-model changes — this layer only re-presents existing functionality.

Key files: `src/wizard/steps.ts`, `src/stores/wizard.ts`, `src/components/wizard/**`,
`src/components/ui/**` (shadcn-vue), `src/style.css` (Indigo theme tokens).

## Scripts

```bash
npm run dev      # vite dev server (proxies /api → backend)
npm run build    # vue-tsc type-check + vite build
npm run test     # vitest
npm run lint     # biome ci .   (must pass — constitution quality gate)
npm run format   # biome format --write .
```
