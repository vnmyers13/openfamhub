import { useState } from 'react'
import { errorDetail } from '../../api/client'
import {
  importRecipe, useAddFromCatalog, useCatalog, useDeleteRecipe, useRecipes, type Recipe, type RecipeDraft,
} from '../../api/meals'
import { minutesLabel } from '../../lib/meals'
import { useAuthStore } from '../../stores/auth'
import { Banner } from '../chores/Controls'
import { input, primary, subtle } from '../chores/shared'
import CookMode from './CookMode'
import RecipeForm from './RecipeForm'

type Mode = { kind: 'list' } | { kind: 'view'; id: string } | { kind: 'edit'; recipe?: Recipe; draft?: RecipeDraft }
  | { kind: 'import' } | { kind: 'catalog' }

function times(r: RecipeDraft): string {
  return [r.servings ? `Serves ${r.servings}` : '', minutesLabel(r.prep_minutes) ? `Prep ${minutesLabel(r.prep_minutes)}` : '',
    minutesLabel(r.cook_minutes) ? `Cook ${minutesLabel(r.cook_minutes)}` : ''].filter(Boolean).join(' · ')
}

function ImportForm({ onDraft, onCancel }: { onDraft: (d: RecipeDraft) => void; onCancel: () => void }) {
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const go = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      onDraft(await importRecipe(url.trim() ? { url: url.trim() } : { text }))
    } catch (err) {
      setError(errorDetail(err, "Couldn't read that recipe"))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={go} className="space-y-3 rounded-lg border border-gray-800 bg-gray-900 p-4" aria-label="Import a recipe">
      <Banner text={error} onClose={() => setError(null)} />
      <div><label htmlFor="import-url" className="mb-1 block text-xs text-gray-400">Recipe link</label>
        <input id="import-url" type="url" className={input} placeholder="https://…" value={url}
          onChange={(e) => setUrl(e.target.value)} disabled={!!text.trim()} /></div>
      <p className="text-center text-xs text-gray-500">or</p>
      <div><label htmlFor="import-text" className="mb-1 block text-xs text-gray-400">Paste the recipe</label>
        <textarea id="import-text" rows={6} className={input} value={text} onChange={(e) => setText(e.target.value)}
          disabled={!!url.trim()} placeholder={'Pancakes\nIngredients\n1 cup flour\n…\nMethod\nWhisk…'} /></div>
      <p className="text-xs text-gray-500">You'll see what was found before anything is saved.</p>
      <div className="flex justify-end gap-2">
        <button type="button" className={subtle} onClick={onCancel}>Cancel</button>
        <button type="submit" className={primary} disabled={busy || (!url.trim() && !text.trim())}>{busy ? 'Reading…' : 'Read recipe'}</button>
      </div>
    </form>
  )
}

function Catalog({ onClose, onError }: { onClose: () => void; onError: (m: string) => void }) {
  const { data } = useCatalog()
  const add = useAddFromCatalog()
  return (
    <section aria-label="Recipe ideas">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Recipe ideas</h2>
        <button className={subtle} onClick={onClose}>Back to my recipes</button>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2">
        {(data ?? []).map((r) => (
          <li key={r.key} className="flex flex-col gap-2 rounded-lg border border-gray-800 bg-gray-900 p-4">
            <p className="font-medium text-white">{r.title}</p>
            {r.description && <p className="text-sm text-gray-400">{r.description}</p>}
            <p className="text-xs text-gray-500">{times(r)}{r.tags.length ? ` · ${r.tags.join(', ')}` : ''}</p>
            <div className="mt-auto flex justify-end">
              {r.added ? <span className="text-sm text-emerald-300">In your recipes</span> : (
                <button className={primary} disabled={add.isPending} aria-label={`Add: ${r.title}`}
                  onClick={() => add.mutateAsync(r.key).catch((err) => onError(errorDetail(err, "Couldn't add it")))}>Add</button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function RecipeView({ recipe, canEdit, onEdit, onBack, onError }: {
  recipe: Recipe; canEdit: boolean; onEdit: () => void; onBack: () => void; onError: (m: string) => void
}) {
  const del = useDeleteRecipe()
  const [cooking, setCooking] = useState(false)
  const remove = async () => {
    if (!window.confirm(`Delete ${recipe.title}? Planned meals keep their name.`)) return
    try {
      await del.mutateAsync(recipe.id)
      onBack()
    } catch (err) {
      onError(errorDetail(err, "Couldn't delete the recipe"))
    }
  }
  return (
    <article className="rounded-lg border border-gray-800 bg-gray-900 p-5">
      {cooking && <CookMode recipe={recipe} onClose={() => setCooking(false)} />}
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <button className="mb-2 text-sm text-gray-400 hover:text-white" onClick={onBack}>← All recipes</button>
          <h2 className="text-2xl font-bold text-white">{recipe.title}</h2>
          {recipe.description && <p className="text-gray-400">{recipe.description}</p>}
          <p className="mt-1 text-sm text-gray-500">{times(recipe)}</p>
          {recipe.tags.length > 0 && (
            <p className="mt-2 flex flex-wrap gap-1">{recipe.tags.map((t) => <span key={t} className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-300">{t}</span>)}</p>
          )}
        </div>
        <div className="flex gap-2">
          <button className={primary} onClick={() => setCooking(true)}>Cook step by step</button>
          {canEdit && <button className={subtle} onClick={onEdit}>Edit</button>}
          {canEdit && <button className={subtle} onClick={remove}>Delete</button>}
        </div>
      </div>
      <div className="grid gap-6 md:grid-cols-[16rem_1fr]">
        <section>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">Ingredients</h3>
          <ul className="list-disc space-y-1 pl-5 text-gray-200">{recipe.ingredients.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </section>
        <section>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">Steps</h3>
          <ol className="list-decimal space-y-2 pl-5 text-gray-200">{recipe.steps.map((x, i) => <li key={i}>{x}</li>)}</ol>
        </section>
      </div>
      {(recipe.video_url || recipe.source_url) && (
        <p className="mt-4 flex gap-4 text-sm">
          {recipe.video_url && <a className="text-primary hover:underline" href={recipe.video_url} target="_blank" rel="noopener noreferrer">▶ Watch the video</a>}
          {recipe.source_url && <a className="text-primary hover:underline" href={recipe.source_url} target="_blank" rel="noopener noreferrer">Original recipe</a>}
        </p>
      )}
    </article>
  )
}

export default function RecipesTab() {
  const user = useAuthStore((s) => s.user)
  const canEdit = !!user && user.role !== 'viewer'
  const [q, setQ] = useState('')
  const [tag, setTag] = useState('')
  const { data: all } = useRecipes()
  const { data: found } = useRecipes({ ...(q.trim() ? { q: q.trim() } : {}), ...(tag ? { tag } : {}) })
  const [mode, setMode] = useState<Mode>({ kind: 'list' })
  const [error, setError] = useState<string | null>(null)
  const tags = [...new Set((all ?? []).flatMap((r) => r.tags))].sort()
  const toList = () => setMode({ kind: 'list' })

  let body
  if (mode.kind === 'edit') {
    body = <RecipeForm recipe={mode.recipe} draft={mode.draft}
      onDone={(saved) => (saved ? setMode({ kind: 'view', id: saved.id }) : mode.recipe ? setMode({ kind: 'view', id: mode.recipe.id }) : toList())} />
  } else if (mode.kind === 'import') {
    body = <ImportForm onDraft={(draft) => setMode({ kind: 'edit', draft })} onCancel={toList} />
  } else if (mode.kind === 'catalog') {
    body = <Catalog onClose={toList} onError={setError} />
  } else if (mode.kind === 'view') {
    const recipe = all?.find((r) => r.id === mode.id)
    body = recipe
      ? <RecipeView recipe={recipe} canEdit={canEdit} onEdit={() => setMode({ kind: 'edit', recipe })} onBack={toList} onError={setError} />
      : null
  } else {
    body = (
      <>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <input className={`${input} max-w-xs`} placeholder="Search recipes" aria-label="Search recipes" value={q} onChange={(e) => setQ(e.target.value)} />
          {tags.length > 0 && (
            <select className={`${input} max-w-[12rem]`} aria-label="Filter by tag" value={tag} onChange={(e) => setTag(e.target.value)}>
              <option value="">All tags</option>
              {tags.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          )}
          <span className="ml-auto flex gap-2">
            <button className={subtle} onClick={() => setMode({ kind: 'catalog' })}>Recipe ideas</button>
            {canEdit && <button className={subtle} onClick={() => setMode({ kind: 'import' })}>Import</button>}
            {canEdit && <button className={primary} onClick={() => setMode({ kind: 'edit' })}>+ Recipe</button>}
          </span>
        </div>
        {found && found.length === 0 && (
          <p className="text-sm text-gray-500">{all && all.length === 0 ? 'No recipes yet. Add one, import one, or pick from the recipe ideas.' : 'No recipes match.'}</p>
        )}
        <ul className="grid gap-3 sm:grid-cols-2">
          {(found ?? []).map((r) => (
            <li key={r.id}>
              <button className="w-full rounded-lg border border-gray-800 bg-gray-900 p-4 text-left hover:border-gray-600" onClick={() => setMode({ kind: 'view', id: r.id })}>
                <p className="font-medium text-white">{r.title}</p>
                <p className="text-xs text-gray-500">{times(r) || `${r.ingredients.length} ingredients`}{r.tags.length ? ` · ${r.tags.join(', ')}` : ''}</p>
              </button>
            </li>
          ))}
        </ul>
      </>
    )
  }
  return (
    <div>
      <Banner text={error} onClose={() => setError(null)} />
      {body}
    </div>
  )
}
