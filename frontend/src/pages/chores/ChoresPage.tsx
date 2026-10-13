import { useState } from 'react'
import { useAuthStore } from '../../stores/auth'
import HistoryTab from './HistoryTab'
import ManageTab from './ManageTab'
import RoutinesTab from './RoutinesTab'
import TodayTab from './TodayTab'
import TodosTab from './TodosTab'

type Tab = 'today' | 'todos' | 'routines' | 'manage' | 'history'

/** Chores, to-dos and routines: what's on today, ticking things off, and (admins) setting them up. */
export default function ChoresPage() {
  const user = useAuthStore((s) => s.user)
  const [tab, setTab] = useState<Tab>('today')
  const tabs: { key: Tab; label: string }[] = [
    { key: 'today', label: 'Today' },
    { key: 'todos', label: 'To-dos' },
    { key: 'routines', label: 'Routines' },
    ...(user?.role === 'admin' ? [{ key: 'manage' as Tab, label: 'Manage' }] : []),
    { key: 'history', label: 'Points & history' },
  ]
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-4 text-2xl font-bold text-white">Chores</h1>
        <div className="mb-6 flex flex-wrap gap-1 border-b border-gray-800" role="tablist">
          {tabs.map((t) => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm ${tab === t.key ? 'border-b-2 border-primary text-white' : 'text-gray-400 hover:text-white'}`}>
              {t.label}
            </button>
          ))}
        </div>
        {tab === 'today' && <TodayTab />}
        {tab === 'todos' && <TodosTab />}
        {tab === 'routines' && <RoutinesTab />}
        {tab === 'manage' && user?.role === 'admin' && <ManageTab />}
        {tab === 'history' && <HistoryTab />}
      </div>
    </div>
  )
}
