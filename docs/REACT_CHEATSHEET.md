# React Cheatsheet (STL-manager focused)

Quick reference for frontend work: React + TypeScript basics, common patterns, and snippets tailored to the STL-manager UI (facets, lists, detail view, job progress).

## Project setup (Vite + React + TypeScript)
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm run dev
npm run build   # outputs dist/
```

Serve `dist/` from FastAPI `StaticFiles` for production.

## Core React ideas
- Components: small, focused function components
- Props are read-only; state with `useState`
- Effects with `useEffect` for side effects (fetching on mount)
- Keys for lists: `items.map(i => <li key={i.id}>...)</li>`

## Essential imports
```tsx
import React, { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
```

## TanStack Query (react-query) basics
- Install: `npm i @tanstack/react-query`
- Setup provider in root:
```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
const qc = new QueryClient()
<QueryClientProvider client={qc}><App/></QueryClientProvider>
```
- Simple data fetch hook:
```tsx
function useFranchises() {
  return useQuery(['franchises'], () => fetch('/api/franchises').then(r => r.json()))
}
```

## Example: Franchises list component
```tsx
export function FranchisesList() {
  const { data, isLoading, error } = useFranchises()
  if (isLoading) return <div>Loading…</div>
  if (error) return <div>Error</div>
  return <ul>{data.map(f => <li key={f.id}>{f.name}</li>)}</ul>
}
```

## Variant list + facets pattern
- Keep filter state in URL query string (use `useSearchParams`) so links are shareable.
- Fetch list with query keys that include filters: `['variants', { q, designer, page }]`
- Use client-side virtualization for large lists (react-window or react-virtualized) to avoid rendering thousands of DOM nodes.

## Detail view + edit flow (optimistic update example)
```tsx
function useUpdateVariant() {
  const qc = useQueryClient()
  return useMutation((patch) => fetch(`/api/variants/${patch.id}`, { method: 'PATCH', body: JSON.stringify(patch) }), {
    onMutate: async (patch) => {
      await qc.cancelQueries(['variant', patch.id])
      const previous = qc.getQueryData(['variant', patch.id])
      qc.setQueryData(['variant', patch.id], old => ({...old, ...patch}))
      return { previous }
    },
    onError: (err, patch, context) => qc.setQueryData(['variant', patch.id], context.previous),
    onSettled: (data, err, patch) => qc.invalidateQueries(['variant', patch.id])
  })
}
```

## SSE job progress hook
```tsx
import { useEffect, useState } from 'react'
export function useSSE(url: string) {
  const [events, setEvents] = useState<any[]>([])
  useEffect(() => {
    const es = new EventSource(url)
    es.onmessage = (e) => setEvents(prev => [...prev, JSON.parse(e.data)])
    return () => es.close()
  }, [url])
  return events
}
```

## UI kit & styling
- Use Mantine, MUI or Tailwind for quick polished UI. Mantine pairs well with TS and has accessible components.

## Devtools & debugging
- React DevTools extension for component inspection
- use `console.log` sparingly, prefer breakpoints in browser DevTools
- TanStack Query Devtools help inspect cache and queries

## Accessibility & keyboard support
- Ensure lists and dialogs are keyboard accessible (focus trap in modal dialogs)
- Use `aria-*` attributes for screen reader labels

## Build & deploy notes
- Build assets: `npm run build` → copy `dist/` to repo `ui_dist/` and serve via FastAPI
- For dev, use `npm run dev` with proxy to backend or `vite` proxy config to avoid CORS

## Quick references
- React docs: https://reactjs.org/
- TanStack Query docs: https://tanstack.com/query
- Vite docs: https://vitejs.dev/

---
If you want, I can scaffold a `frontend/` folder with the basic `FranchisesList` / `VariantGrid` components wired to mock API endpoints now.
