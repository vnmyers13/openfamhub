import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { rewardAPI } from '../api/client'
import { useAuthStore } from '../stores/auth'

type Tab = 'store' | 'requests' | 'badges' | 'history'

interface RewardItem {
  id: string
  name: string
  description?: string
  point_cost: number
  is_auto_fulfill: boolean
}

interface RewardRequest {
  id: string
  status: string
  requested_at: string
}

interface BadgeItem {
  id: string
  earned_at: string
}

interface Transaction {
  id: string
  created_at: string
  description?: string
  type?: string
  points?: number
  amount?: number
}

export default function RewardsPage() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('store')
  const [showRewardForm, setShowRewardForm] = useState(false)
  const [rewardForm, setRewardForm] = useState({
    name: '',
    description: '',
    point_cost: 50,
    is_auto_fulfill: true,
  })

  const { data: pointsData } = useQuery({
    queryKey: ['rewards-points'],
    queryFn: rewardAPI.getPointsBalance,
  })

  const { data: allowanceData } = useQuery({
    queryKey: ['rewards-allowance'],
    queryFn: rewardAPI.getAllowanceBalance,
  })

  const { data: catalog } = useQuery({
    queryKey: ['rewards-catalog'],
    queryFn: rewardAPI.getCatalog,
  })

  const { data: myRequests } = useQuery({
    queryKey: ['rewards-my-requests'],
    queryFn: rewardAPI.getMyRequests,
  })

  const { data: badges } = useQuery({
    queryKey: ['rewards-badges'],
    queryFn: rewardAPI.getBadges,
  })

  const { data: streak } = useQuery({
    queryKey: ['rewards-streak'],
    queryFn: rewardAPI.getStreak,
  })

  const purchaseMutation = useMutation({
    mutationFn: rewardAPI.purchaseReward,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rewards-points'] })
    },
  })

  const requestMutation = useMutation({
    mutationFn: rewardAPI.requestReward,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rewards-my-requests'] })
    },
  })

  const createMutation = useMutation({
    mutationFn: rewardAPI.createReward,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rewards-catalog'] })
      setShowRewardForm(false)
    },
  })

  const isAdmin = user?.role === 'admin'

  const handlePurchase = (id: string) => {
    purchaseMutation.mutate(id)
  }

  const handleRequest = (id: string) => {
    requestMutation.mutate(id)
  }

  const handleCreateReward = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(rewardForm)
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'store', label: 'Store' },
    { key: 'requests', label: 'My Requests' },
    { key: 'badges', label: 'Badges' },
    { key: 'history', label: 'History' },
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">Rewards</h1>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-gray-800 rounded-lg p-4 text-center">
            <div className="text-3xl font-bold text-yellow-400">{pointsData?.balance || 0}</div>
            <div className="text-gray-400 text-sm">Reward Points</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 text-center">
            <div className="text-3xl font-bold text-green-400">${allowanceData?.balance?.toFixed(2) || '0.00'}</div>
            <div className="text-gray-400 text-sm">Allowance</div>
          </div>
        </div>

        {streak && (
          <div className="bg-gray-800 rounded-lg p-4 mb-6 text-center">
            <div className="text-xl font-bold">🔥 {streak.current_streak} Day Streak</div>
            <div className="text-gray-400 text-sm">Longest: {streak.longest_streak} days</div>
          </div>
        )}

        <div className="flex gap-2 mb-6 border-b border-gray-700">
          {tabs.map(tab => (
            <button
              key={tab.key}
              className={`px-4 py-2 ${activeTab === tab.key ? 'bg-blue-600 rounded-t-lg' : 'text-gray-400 hover:text-white'}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'store' && (
          <div className="space-y-3">
            {isAdmin && (
              <button
                onClick={() => setShowRewardForm(!showRewardForm)}
                className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg mb-4"
              >
                {showRewardForm ? 'Cancel' : 'Add Reward'}
              </button>
            )}

            {showRewardForm && (
              <form onSubmit={handleCreateReward} className="bg-gray-800 rounded-lg p-4 space-y-3 mb-4">
                <input
                  type="text"
                  placeholder="Reward name"
                  value={rewardForm.name}
                  onChange={e => setRewardForm({ ...rewardForm, name: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                  required
                />
                <input
                  type="text"
                  placeholder="Description"
                  value={rewardForm.description}
                  onChange={e => setRewardForm({ ...rewardForm, description: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                />
                <input
                  type="number"
                  placeholder="Point cost"
                  value={rewardForm.point_cost}
                  onChange={e => setRewardForm({ ...rewardForm, point_cost: parseInt(e.target.value) || 50 })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                  min="1"
                />
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={rewardForm.is_auto_fulfill}
                    onChange={e => setRewardForm({ ...rewardForm, is_auto_fulfill: e.target.checked })}
                    className="rounded"
                  />
                  Auto-fulfill (no admin approval needed)
                </label>
                <button type="submit" className="w-full bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
                  Create Reward
                </button>
              </form>
            )}

            {catalog?.map((reward: RewardItem) => (
              <div key={reward.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
                <div>
                  <div className="font-medium">{reward.name}</div>
                  <div className="text-sm text-gray-400">{reward.description || 'No description'}</div>
                  <div className="text-sm text-yellow-400">{reward.point_cost} points</div>
                </div>
                {reward.is_auto_fulfill ? (
                  <button
                    onClick={() => handlePurchase(reward.id)}
                    disabled={pointsData?.balance && pointsData.balance < reward.point_cost}
                    className="bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg"
                  >
                    Redeem
                  </button>
                ) : (
                  <button
                    onClick={() => handleRequest(reward.id)}
                    className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
                  >
                    Request
                  </button>
                )}
              </div>
            )) || <p className="text-gray-400 text-center py-8">No rewards available</p>}
          </div>
        )}

        {activeTab === 'requests' && (
          <div className="space-y-2">
            {myRequests?.map((req: RewardRequest) => (
              <div key={req.id} className="bg-gray-800 rounded-lg p-3 flex justify-between items-center">
                <div>
                  <span className="text-gray-400">{new Date(req.requested_at).toLocaleDateString()}</span>
                  <span className={`ml-4 px-2 py-1 rounded text-xs ${
                    req.status === 'approved' ? 'bg-green-600' :
                    req.status === 'rejected' ? 'bg-red-600' : 'bg-yellow-600'
                  }`}>
                    {req.status}
                  </span>
                </div>
              </div>
            )) || <p className="text-gray-400 text-center py-8">No reward requests</p>}
          </div>
        )}

        {activeTab === 'badges' && (
          <div className="space-y-3">
            {badges?.map((badge: BadgeItem) => (
              <div key={badge.id} className="bg-gray-800 rounded-lg p-4 text-center">
                <div className="text-3xl mb-2">🏆</div>
                <div className="text-gray-400 text-sm">Earned {new Date(badge.earned_at).toLocaleDateString()}</div>
              </div>
            )) || <p className="text-gray-400 text-center py-8">No badges earned yet. Complete chores to earn badges!</p>}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-2">
            <h2 className="text-lg font-semibold mb-2">Points History</h2>
            {pointsData?.transactions.map((tx: Transaction) => (
              <div key={tx.id} className="bg-gray-800 rounded-lg p-3 flex justify-between">
                <div>
                  <span className="text-gray-400">{new Date(tx.created_at).toLocaleDateString()}</span>
                  <span className="ml-4 text-sm">{tx.description || tx.type}</span>
                </div>
                <span className={(tx.points || 0) > 0 ? 'text-green-400' : 'text-red-400'}>
                  {(tx.points || 0) > 0 ? '+' : ''}{tx.points}
                </span>
              </div>
            ))}
            <h2 className="text-lg font-semibold mb-2 mt-6">Allowance History</h2>
            {allowanceData?.transactions.map((tx: Transaction) => (
              <div key={tx.id} className="bg-gray-800 rounded-lg p-3 flex justify-between">
                <div>
                  <span className="text-gray-400">{new Date(tx.created_at).toLocaleDateString()}</span>
                  <span className="ml-4 text-sm">{tx.description || tx.type}</span>
                </div>
                <span className="text-green-400">+${tx.amount}</span>
              </div>
            ))}
            {(!pointsData?.transactions?.length && !allowanceData?.transactions?.length) && (
              <p className="text-gray-400 text-center py-8">No transaction history</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
