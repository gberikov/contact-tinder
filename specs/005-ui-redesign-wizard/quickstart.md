# Quickstart & Validation: Guided Wizard Redesign

A run/validation guide proving the redesign works end to end. Implementation details live in
`tasks.md`; this file is how you *check* the feature.

## Prerequisites

- Existing dev setup runs (backend on `:8000`, frontend on `:5173`); see repo root README /
  docker-compose. The wizard adds **no** new services.
- Node + npm available in `frontend/`.

## 1. Install the shadcn-vue / Tailwind v4 foundation (one-time)

```bash
cd frontend
npm install tailwindcss @tailwindcss/vite
# add tailwindcss() to vite.config.ts plugins; create src/style.css with `@import "tailwindcss";`
npx shadcn-vue@latest init        # use the customizer init-URL: base=reka, style=mira, theme=indigo
npx shadcn-vue@latest add stepper button card dialog badge input label sonner separator
```

Expected: `components.json` created (style `mira`), `src/lib/utils.ts` with `cn()`, `src/components/ui/**`
populated, Indigo CSS tokens in `src/style.css`.

## 2. Quality gates (must stay green)

```bash
cd frontend
npm run lint     # biome ci .  — single linter/formatter (constitution); generated ui/** included
npm run build    # vue-tsc -b && vite build — type-check + build
npm run test     # vitest run — wizard store + stepper specs (TDD: red first, then green)
```

## 3. End-to-end wizard walkthrough (maps to acceptance scenarios)

Start the app and open `/` (redirects into the wizard). Verify, in order:

| # | Action | Expected (spec ref) |
|---|--------|---------------------|
| 1 | Land in the app | Persistent stepper shows all 6 plain-verb steps; exactly one `current`, rest `completed`/`upcoming` (US1-AS1, FR-002/003) |
| 2 | Read each step label/description | Plain vocabulary; **"working copy" appears nowhere**, the editable copy is **"Draft"** (US2, FR-010/011) |
| 3 | On Connect, add ≥2 accounts, mark one active | Only the active account feeds Backup (FR-021) |
| 4 | Start a Backup (import) | Backup step enters **running** state; can navigate away; flips to **completed** when import finishes (FR-025/029) |
| 5 | Try to open Export before Backup done | Export shows `upcoming` + disabled (FR-006) |
| 6 | Create ≥2 Drafts, mark one active | Active Draft feeds Merge (FR-021); switching active Draft re-derives Merge/Review/Export without deleting the other Draft (FR-024) |
| 7 | Run Merge | Merge enters **running**, then **completed**; clusters reviewable (FR-025) |
| 8 | Do Review (swipe) | Swipe surface also has labeled keep/delete/process buttons (FR-028) |
| 9 | Go to Export | Dry-run preview with delete/label/undecided counts; **undecided warning** visible (FR-018/019) |
| 10 | Confirm delete | Explicit labeled confirm (not implicit); snapshot/undo available; `write_scope_required` → re-consent path intact (FR-018/028) |
| 11 | Reload the browser mid-flow | Wizard restores the correct current step + active chain, not step 1 (FR-007) |
| 12 | Shrink viewport to mobile width | Stepper stays usable; current step identifiable (FR-016/SC-007) |

## 4. UX-principle checks (FR-026…FR-029 / SC-008…SC-010)

- **Simple**: each step has a single clearly-labeled primary action in a consistent location (SC-008).
- **Predictable**: advance / back / select-active / confirm / cancel look & behave identically across
  all six steps (SC-009).
- **Feedback**: every state-changing action shows in-progress/success/error; nothing completes silently
  (FR-029/SC-010).

## 5. Done criteria

- All three quality gates (lint, build, test) pass.
- The walkthrough table passes top to bottom.
- No screen retains the pre-redesign ad-hoc styling; all use the Mira/Indigo system (SC-004).
