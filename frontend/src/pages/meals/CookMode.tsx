import { useState } from 'react'
import type { Recipe } from '../../api/meals'
import { primary, subtle } from '../chores/shared'

/** One step at a time in big type, for a phone or tablet propped up in the kitchen. */
export default function CookMode({ recipe, onClose }: { recipe: Recipe; onClose: () => void }) {
  const [i, setI] = useState(0)
  const steps = recipe.steps
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-gray-950 p-6" role="dialog" aria-label={`Cooking ${recipe.title}`}>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">{recipe.title}</h2>
        <button className={subtle} onClick={onClose}>Done</button>
      </div>
      {steps.length === 0 ? <p className="text-gray-400">This recipe has no steps yet.</p> : (
        <>
          <p className="mb-2 text-sm uppercase tracking-wider text-gray-400">Step {i + 1} of {steps.length}</p>
          <p className="flex-1 text-3xl leading-snug text-white">{steps[i]}</p>
          <div className="flex justify-between gap-3">
            <button className={`${subtle} px-6 py-3 text-lg`} disabled={i === 0} onClick={() => setI(i - 1)}>Back</button>
            {i < steps.length - 1
              ? <button className={`${primary} px-6 py-3 text-lg`} onClick={() => setI(i + 1)}>Next</button>
              : <button className={`${primary} px-6 py-3 text-lg`} onClick={onClose}>Finished</button>}
          </div>
        </>
      )}
    </div>
  )
}
