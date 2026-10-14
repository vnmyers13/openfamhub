import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { useSaveRecipe, type Recipe, type RecipeDraft } from '../../api/meals'
import { toLines } from '../../lib/meals'
import { Banner } from '../chores/Controls'
import { input, primary, subtle } from '../chores/shared'

const label = 'mb-1 block text-xs text-gray-400'
const num = (v: string) => (v.trim() === '' ? null : Math.max(0, Math.trunc(Number(v)) || 0))

/** Add or edit a recipe; an import arrives here as a draft to review before saving. */
export default function RecipeForm({ recipe, draft, onDone }: {
  recipe?: Recipe; draft?: RecipeDraft; onDone: (saved?: Recipe) => void
}) {
  const start = recipe ?? draft
  const save = useSaveRecipe()
  const [title, setTitle] = useState(start?.title ?? '')
  const [description, setDescription] = useState(start?.description ?? '')
  const [servings, setServings] = useState(start?.servings?.toString() ?? '')
  const [prep, setPrep] = useState(start?.prep_minutes?.toString() ?? '')
  const [cook, setCook] = useState(start?.cook_minutes?.toString() ?? '')
  const [tags, setTags] = useState((start?.tags ?? []).join(', '))
  const [ingredients, setIngredients] = useState((start?.ingredients ?? []).join('\n'))
  const [steps, setSteps] = useState((start?.steps ?? []).join('\n'))
  const [source, setSource] = useState(start?.source_url ?? '')
  const [video, setVideo] = useState(start?.video_url ?? '')
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const saved = await save.mutateAsync({
        id: recipe?.id, title: title.trim(), description: description.trim() || null,
        servings: num(servings) || null, prep_minutes: num(prep), cook_minutes: num(cook),
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
        ingredients: toLines(ingredients), steps: toLines(steps),
        source_url: source.trim() || null, video_url: video.trim() || null,
      })
      onDone(saved)
    } catch (err) {
      setError(errorDetail(err, "Couldn't save the recipe"))
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-gray-800 bg-gray-900 p-4" aria-label={recipe ? `Edit ${recipe.title}` : 'New recipe'}>
      <Banner text={error} onClose={() => setError(null)} />
      <div><label htmlFor="recipe-title" className={label}>Recipe</label>
        <input id="recipe-title" className={input} value={title} maxLength={128} required onChange={(e) => setTitle(e.target.value)} /></div>
      <div><label htmlFor="recipe-desc" className={label}>About it (optional)</label>
        <input id="recipe-desc" className={input} value={description} maxLength={1000} onChange={(e) => setDescription(e.target.value)} /></div>
      <div className="grid grid-cols-3 gap-3">
        <div><label htmlFor="recipe-servings" className={label}>Serves</label>
          <input id="recipe-servings" type="number" min={1} className={input} value={servings} onChange={(e) => setServings(e.target.value)} /></div>
        <div><label htmlFor="recipe-prep" className={label}>Prep (min)</label>
          <input id="recipe-prep" type="number" min={0} className={input} value={prep} onChange={(e) => setPrep(e.target.value)} /></div>
        <div><label htmlFor="recipe-cook" className={label}>Cook (min)</label>
          <input id="recipe-cook" type="number" min={0} className={input} value={cook} onChange={(e) => setCook(e.target.value)} /></div>
      </div>
      <div><label htmlFor="recipe-tags" className={label}>Tags, separated by commas (e.g. dinner, vegetarian)</label>
        <input id="recipe-tags" className={input} value={tags} onChange={(e) => setTags(e.target.value)} /></div>
      <div className="grid gap-3 md:grid-cols-2">
        <div><label htmlFor="recipe-ingredients" className={label}>Ingredients, one per line</label>
          <textarea id="recipe-ingredients" rows={8} className={input} value={ingredients} onChange={(e) => setIngredients(e.target.value)} /></div>
        <div><label htmlFor="recipe-steps" className={label}>Steps, one per line</label>
          <textarea id="recipe-steps" rows={8} className={input} value={steps} onChange={(e) => setSteps(e.target.value)} /></div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div><label htmlFor="recipe-source" className={label}>Where it's from (link)</label>
          <input id="recipe-source" type="url" className={input} value={source} onChange={(e) => setSource(e.target.value)} /></div>
        <div><label htmlFor="recipe-video" className={label}>Video (link)</label>
          <input id="recipe-video" type="url" className={input} value={video} onChange={(e) => setVideo(e.target.value)} /></div>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" className={subtle} onClick={() => onDone()}>Cancel</button>
        <button type="submit" className={primary} disabled={save.isPending || !title.trim()}>Save recipe</button>
      </div>
    </form>
  )
}
