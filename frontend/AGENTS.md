# Frontend Agent Notes

This file describes the current frontend-only MVP implementation in `frontend/`.

## Stack

- Next.js App Router (`next` 16)
- React 19
- TypeScript
- Tailwind CSS v4
- `@dnd-kit` for drag-and-drop interactions
- Vitest + Testing Library for unit/integration-style component tests
- Playwright for end-to-end browser tests

## Current Product Behavior

- Single-page Kanban board rendered at `/`.
- Fixed five columns seeded from in-memory data (`initialData`).
- Columns can be renamed inline.
- Cards can be:
  - Reordered in a column
  - Moved across columns via drag-and-drop
  - Added from a per-column form
  - Removed from a column
- No auth, backend, or persistence yet.

## Key Files

- App shell:
  - `src/app/layout.tsx`
  - `src/app/page.tsx`
  - `src/app/globals.css`
- Kanban UI:
  - `src/components/KanbanBoard.tsx`
  - `src/components/KanbanColumn.tsx`
  - `src/components/KanbanCard.tsx`
  - `src/components/KanbanCardPreview.tsx`
  - `src/components/NewCardForm.tsx`
- Board/domain utilities:
  - `src/lib/kanban.ts`

## Data Model (frontend)

Defined in `src/lib/kanban.ts`:
- `Card`: `{ id, title, details }`
- `Column`: `{ id, title, cardIds[] }`
- `BoardData`: `{ columns[], cards<Record> }`

Important helpers:
- `moveCard(columns, activeId, overId)` handles intra/inter-column card movement.
- `createId(prefix)` generates client-side IDs for new cards.

## Testing

Unit/component tests:
- `src/components/KanbanBoard.test.tsx`
- `src/lib/kanban.test.ts`

E2E tests:
- `tests/kanban.spec.ts`
- `playwright.config.ts` (spins up `npm run dev` on `127.0.0.1:3000`)

## Local Commands

From `frontend/`:

```bash
npm install
npm run dev
npm run build
npm run lint
npm run test:unit
npm run test:e2e
npm run test:all
```

## Design Language

Global color tokens in `src/app/globals.css` match project guidance:
- Accent Yellow `#ecad0a`
- Blue Primary `#209dd7`
- Purple Secondary `#753991`
- Dark Navy `#032147`
- Gray Text `#888888`

Typography:
- Display: Space Grotesk
- Body: Manrope

## Constraints to Preserve While Migrating

- Keep Kanban interactions intuitive and fast during backend integration.
- Avoid over-engineering: prefer small, clear components and utility functions.
- Preserve test coverage as behavior moves from in-memory state to API-backed state.
- Keep `/api/*` namespace reserved for backend once integrated.
