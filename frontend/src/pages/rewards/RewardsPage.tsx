import { useState } from 'react'
import { useAuthStore } from '../../stores/auth'
import AllowanceTab from './AllowanceTab'
import BadgesTab from './BadgesTab'
import ManageTab from './ManageTab'
import RequestsTab from './RequestsTab'
import ShopTab from './ShopTab'

type Tab = 'shop' | 'requests' | 'badges' | 'allowance' | 'manage'

/** Spend points, follow requests, see badges and allowance; admins set it all up. */
export default function RewardsPage() {
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin'
  const [tab, setTab] = useState<Tab>('shop')
  const tabs: { key: Tab; label: string }[] = [
    { key: 'shop', label: 'Rewards' },
    { key: 'requests', label: 'Requests' },
    { key: 'badges', label: 'Badges' },
    { key: 'allowance', label: 'Allowance' },
    ...(isAdmin ? [{ key: 'manage' as Tab, label: 'Manage' }] : []),
  ]
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-4 text-2xl font-bold text-white">Rewards</h1>
        <div className="mb-6 flex flex-wrap gap-1 border-b border-gray-800" role="tablist">
          {tabs.map((t) => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm ${tab === t.key ? 'border-b-2 border-primary text-white' : 'text-gray-400 hover:text-white'}`}>
              {t.label}
            </button>
          ))}
        </div>
        {tab === 'shop' && <ShopTab />}
        {tab === 'requests' && <RequestsTab />}
        {tab === 'badges' && <BadgesTab />}
        {tab === 'allowance' && <AllowanceTab />}
        {tab === 'manage' && isAdmin && <ManageTab />}
      </div>
    </div>
  )
}
