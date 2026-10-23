import { useState } from 'react'
import {
  useCalendarSubscriptions,
  useCreateCalendarSubscription,
  useRevealCalendarSubscription,
  useRotateCalendarSubscription,
  useRevokeCalendarSubscription,
  type SubscriptionKind,
  type CalendarSubscriptionListItem,
} from '../../api/calendarSubscriptions'
import { errorDetail } from '../../api/client'

type DialogState =
  | { kind: 'none' }
  | { kind: 'create'; kindType: SubscriptionKind }
  | { kind: 'reveal'; kindType: SubscriptionKind; url: string }
  | { kind: 'rotate'; kindType: SubscriptionKind; url: string }
  | { kind: 'error'; message: string }

/** A single subscription card in the list. */
function SubscriptionCard({
  sub,
  onAction,
}: {
  sub: CalendarSubscriptionListItem
  onAction: (action: 'create' | 'reveal' | 'rotate' | 'revoke', kind: SubscriptionKind) => void
}) {
  const { active, kind, last_published_at, last_error } = sub

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <span className="text-white font-medium capitalize">{kind}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${active ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-300'}`}>
            {active ? 'Active' : 'Inactive'}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onAction('create', kind)}
            className="text-gray-400 hover:text-white text-sm px-2 py-1"
          >
            {active ? 'Recreate' : 'Create'} {kind} subscription
          </button>
          <button
            onClick={() => onAction('reveal', kind)}
            className="text-gray-400 hover:text-white text-sm px-2 py-1"
          >
            Reveal {kind}
          </button>
          <button
            onClick={() => onAction('rotate', kind)}
            className="text-gray-400 hover:text-white text-sm px-2 py-1"
          >
            Rotate {kind}
          </button>
          <button
            onClick={() => onAction('revoke', kind)}
            className="text-red-400 hover:text-red-300 text-sm px-2 py-1"
          >
            Revoke {kind}
          </button>
        </div>
      </div>
      <div className="text-xs text-gray-500 space-y-0.5">
        {last_published_at && <p>Last published: {new Date(last_published_at).toLocaleString()}</p>}
        {last_error && <p className="text-red-400">Error: {last_error}</p>}
      </div>
    </div>
  )
}

/** URL dialog: shows the URL with a copy button, closes on Close/Escape. */
function UrlDialog({ url, onClose }: { url: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-xl rounded-xl border border-gray-800 bg-gray-900 p-6">
        <h2 className="text-lg font-semibold text-white mb-2">Subscription URL</h2>
        <p className="text-sm text-gray-400 mb-4">
          This URL is encrypted at rest and revealed only for your current session. It is not stored in the listing.
        </p>
        <div className="flex gap-2 mb-4">
          <code className="flex-1 truncate rounded bg-gray-800 px-3 py-2 text-xs text-gray-200">{url}</code>
          <button
            onClick={handleCopy}
            className="rounded bg-gray-700 px-3 py-1 text-sm text-white hover:bg-gray-600"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <div className="flex justify-end">
          <button onClick={onClose} className="rounded bg-primary px-4 py-1.5 text-sm text-white hover:bg-primary-dark">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

/** Error toast: shown briefly, then dismissed. */
function ErrorToast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="mb-4 rounded bg-red-900/50 px-4 py-2 text-sm text-red-300" role="alert">
      {message}
      <button onClick={onClose} className="ml-2 text-red-400 hover:text-red-300" aria-label="Dismiss">×</button>
    </div>
  )
}

export default function CalendarSubscriptions() {
  const { data: subscriptions = [] } = useCalendarSubscriptions()
  const [dialog, setDialog] = useState<DialogState>({ kind: 'none' })

  const { mutateAsync: createSub, error: createError } = useCreateCalendarSubscription()
  const { mutateAsync: revealSub, error: revealError } = useRevealCalendarSubscription()
  const { mutateAsync: rotateSub, error: rotateError } = useRotateCalendarSubscription()
  const { mutateAsync: revokeSub, error: revokeError } = useRevokeCalendarSubscription()

  // Show the first error from any mutation, or clear it.
  const apiError = createError || revealError || rotateError || revokeError
  const apiErrorText = apiError ? errorDetail(apiError, 'Operation failed') : null

  const handleAction = async (action: 'create' | 'reveal' | 'rotate' | 'revoke', kind: SubscriptionKind) => {
    try {
      let url: string
      if (action === 'create') {
        const result = await createSub(kind)
        url = result.subscription_url
      } else if (action === 'reveal') {
        const result = await revealSub(kind)
        url = result.subscription_url
      } else if (action === 'rotate') {
        const result = await rotateSub(kind)
        url = result.subscription_url
      } else {
        // Revoke: confirm first.
        const sub = subscriptions.find((s) => s.kind === kind)
        if (!sub) return
        if (!confirm(`Revoke the "${kind}" subscription? It will stop delivering events.`)) return
        await revokeSub(kind)
        return
      }
      setDialog({ kind: 'reveal', kindType: kind, url })
    } catch {
      // Errors from mutations are picked up by apiErrorText.
    }
  }

  const closeDialog = () => setDialog({ kind: 'none' })

  return (
    <div className="min-h-screen bg-gray-950 p-4">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-6">Calendar Subscriptions</h1>
        <p className="text-sm text-gray-400 mb-6">
          Managed subscriptions deliver your family calendar to external devices via encrypted relay URLs.
          URLs are never stored in the listing — they appear only in a focused dialog during create, reveal, or rotate.
          {apiErrorText && (
            <ErrorToast message={apiErrorText} onClose={() => { /* error will clear on next action */ }} />
          )}
        </p>

        {subscriptions.length === 0 ? (
          <div>
            <p className="text-gray-400 mb-4">No subscriptions yet. Create one to start delivering events.</p>
            <div className="flex gap-2">
              <button
                onClick={() => handleAction('create', 'titles')}
                className="bg-primary hover:bg-primary-dark text-white px-4 py-1.5 rounded text-sm"
              >
                Create titles subscription
              </button>
              <button
                onClick={() => handleAction('create', 'full')}
                className="bg-primary hover:bg-primary-dark text-white px-4 py-1.5 rounded text-sm"
              >
                Create full subscription
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {subscriptions.map((sub) => (
              <SubscriptionCard key={sub.id} sub={sub} onAction={handleAction} />
            ))}
          </div>
        )}

        {/* URL dialog */}
        {dialog.kind === 'reveal' && (
          <UrlDialog url={dialog.url} onClose={closeDialog} />
        )}
      </div>
    </div>
  )
}
