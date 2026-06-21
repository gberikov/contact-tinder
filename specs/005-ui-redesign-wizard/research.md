# Phase 0 Research: Guided Wizard Redesign

All Technical-Context unknowns for the redesign are resolved below.

## 1. What is the "Mira" style + "Indigo" theme in shadcn-vue?

- **Decision**: Use shadcn-vue with **style `mira`** and **theme `indigo`** on the **`reka`** base
  (preset family `reka-mira`). Mira ships with Hugeicons + Inter by default.
- **Rationale**: shadcn-vue exposes a small set of named **visual styles** — `vega` (classic shadcn),
  `nova` (compact), `maia` (soft/rounded), `lyra` (boxy/mono), **`mira` (compact, made for dense
  interfaces)**, `luma`, `sera`. **Indigo** is one of the valid **theme** values
  (`…, blue, cyan, … indigo, …`). The combination is selectable in the shadcn-vue customizer, which
  produces an `/init?base=reka&style=mira&theme=indigo&font=inter&iconLibrary=hugeicons` URL that the
  CLI can consume directly. Mira's "dense/compact" intent aligns with this app's data-heavy triage and
  review surfaces.
- **Alternatives considered**: `vega` (classic) — rejected, user explicitly asked for Mira;
  hand-rolled Tailwind theme — rejected, loses shadcn-vue's component set and the named-preset
  guarantee; tweakcn/third-party themes — unnecessary, Indigo is a built-in theme.
- **Application**: `npx shadcn-vue@latest init` driven by the customizer init-URL (or
  `--style mira` + Indigo theme tokens). Final exact flags/URL are pinned in `tasks.md`; the theme is
  CSS-variable based (`--primary` etc.), so Indigo lives in `src/style.css` `@theme` tokens.

## 2. Stepper component

- **Decision**: Use the shadcn-vue **Stepper** (`npx shadcn-vue@latest add stepper`), exposing
  `Stepper, StepperItem, StepperTrigger, StepperIndicator, StepperTitle, StepperDescription,
  StepperSeparator`.
- **Rationale**: First-class component built on reka-ui; supports horizontal & vertical orientation
  and a per-item `v-slot="{ state }"` yielding `active | completed | inactive`. `StepperTrigger` is a
  button (focusable/keyboard-navigable) and can be disabled to express gating (FR-006). The
  `StepperDescription` covers the per-step plain-language hint (FR-012).
- **Running state (FR-025)**: reka-ui's Stepper has no built-in "running" state. We model it in the
  wizard layer: the active step's `StepperIndicator` renders a spinner and an `data-running` style when
  `wizard.isRunning(step)` is true (driven by existing job statuses — import job `running`, dedup run
  `running`, export run `running`). This is a presentation overlay on top of `active`, not a reka-ui
  change.
- **Alternatives considered**: Custom stepper from scratch — rejected, reinvents accessible primitive;
  a plain progress bar — rejected, loses per-step labels/affordances the spec requires.

## 3. Tailwind + shadcn-vue integration into the existing Vite app

- **Decision**: **Tailwind CSS v4** via the **`@tailwindcss/vite`** plugin, then `shadcn-vue@latest
  init`. (Tailwind v3 would require pinning `shadcn-vue@1.0.3`; v4 is the current default — chosen.)
- **Rationale**: The app already uses Vite 5 + `@vitejs/plugin-vue` and the `@` alias — exactly the
  setup shadcn-vue's Vite guide targets. Steps: `npm i tailwindcss @tailwindcss/vite`; add
  `tailwindcss()` to `vite.config.ts` plugins; create `src/style.css` with `@import "tailwindcss";`
  plus the Indigo `@theme` tokens; ensure `tsconfig*.json` path alias; run `init` (writes
  `components.json`, `src/lib/utils.ts` with `cn()`, base CSS vars) and `add` the needed components.
- **New runtime deps** pulled by init/add: `reka-ui`, `class-variance-authority`, `clsx`,
  `tailwind-merge`, `tw-animate-css`, an icon set (`hugeicons`/`lucide-vue-next`).
- **Alternatives considered**: Tailwind v3 + PostCSS — rejected, more config, older path; CSS-only
  redesign without shadcn — rejected, contradicts the explicit shadcn-vue/Stepper requirement.

## 4. Biome vs. generated shadcn-vue components

- **Decision**: Keep **Biome as the single linter/formatter** (constitution). Run `biome format
  --write` over generated `src/components/ui/**` so they conform; keep the CI `biome ci .` gate
  authoritative. Only if a specific generated file genuinely fights a Biome rule, scope a minimal
  override in `biome.json` (no second formatter).
- **Rationale**: Constitution mandates Biome and forbids a competing formatter (ESLint/Prettier).
  shadcn-vue emits plain Vue/TS we own, so Biome can format it like any other source.
- **Alternatives considered**: Adding Prettier for `ui/**` — rejected (constitution violation);
  git-ignoring `ui/**` from Biome wholesale — avoided unless forced, to keep one consistent style.

## 5. Mapping the six wizard steps onto existing state (no backend change)

- **Decision**: Derive each step's completion from existing read endpoints along the active-selection
  chain; persist the chain client-side (localStorage + route params).
- **Rationale**: `services/api.ts` already exposes everything needed — see `data-model.md` for the
  full table. Summary:

  | Step | Active artifact | Existing source | "Completed" when | "Running" when |
  |------|-----------------|-----------------|------------------|----------------|
  | Connect | Account | `listAccounts()` | active account `status==='connected'` | — |
  | Backup | Snapshot | `listSnapshots()` (filter by account) | active snapshot `status==='complete'` | `getImportJob().status==='running'` |
  | Draft | WorkingCopy | `listWorkingCopies()` (filter by snapshot) | active draft exists | — |
  | Merge | DedupRun | `listDedupRuns(draft)` | run `status==='completed'` | run `status==='running'` |
  | Review | TriageSession | `listTriageSessions(draft)` | session `status==='complete'` | — |
  | Export | ExportRun | `previewExport()` / `getExportRun()` | run `status==='completed'` | run `status==='running'` |

- **Alternatives considered**: A new `/wizard/state` backend endpoint — rejected, violates the
  "frontend-only, no backend change" scope (FR-020) and the existing endpoints already suffice.

## 6. Step persistence / restore on reload (FR-007)

- **Decision**: Persist the active-selection chain (active accountId → snapshotId → workingCopyId) in
  `localStorage`, and reflect the current step in the route (`/wizard/:step` with the active draft id
  in params/query). On load, the wizard store rehydrates the chain, re-derives step state from the
  endpoints, and lands the operator on the correct current step rather than step 1.
- **Rationale**: Matches "predictable" UX (FR-027) and the spec's reload/return-visit requirement
  without new server state. Route + store keep deep-linking and refresh consistent.
- **Alternatives considered**: Server-side wizard progress — rejected (scope); pure in-memory store —
  rejected, loses state on refresh (fails FR-007).

## 7. `frontend-design` skill usage (per spec Assumptions)

- **Decision**: Invoke the `frontend-design` skill during implementation to set typography scale,
  spacing rhythm, visual hierarchy, and component intent on top of the Mira/Indigo tokens — applied to
  the wizard shell first, then each step — rather than accepting default templated styling.
- **Rationale**: Spec Assumptions + FR-026…FR-029 / SC-008…SC-010 require a deliberately simple, clear,
  predictable interface; the skill provides that design direction.
