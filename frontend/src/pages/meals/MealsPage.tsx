import { useState } from 'react'
import PantryTab from './PantryTab'
import PlanTab from './PlanTab'
import RecipesTab from './RecipesTab'
import ShoppingTab from './ShoppingTab'

type Tab = 'plan' | 'recipes' | 'shopping' | 'pantry'

const TABS: { key: Tab; label: string }[] = [
  { key: 'plan', label: 'This week' },
  { key: 'recipes', label: 'Recipes' },
  { key: 'shopping', label: 'Shopping list' },
  { key: 'pantry', label: 'Pantry' },
]

/** Plan the week's meals, keep recipes, shop from the plan, and track the pantry. */
export default function MealsPage() {
  const [tab, setTab] = useState<Tab>('plan')
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-5xl">
        <h1 className="mb-4 text-2xl font-bold text-white">Meals</h1>
        <div className="mb-6 flex flex-wrap gap-1 border-b border-gray-800" role="tablist">
          {TABS.map((t) => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm ${tab === t.key ? 'border-b-2 border-primary text-white' : 'text-gray-400 hover:text-white'}`}>
              {t.label}
            </button>
          ))}
        </div>
        {tab === 'plan' && <PlanTab onShop={() => setTab('shopping')} />}
        {tab === 'recipes' && <RecipesTab />}
        {tab === 'shopping' && <ShoppingTab />}
        {tab === 'pantry' && <PantryTab />}
      </div>
    </div>
  )
}
