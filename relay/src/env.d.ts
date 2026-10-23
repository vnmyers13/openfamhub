import type { Env as RelayEnv } from './index'

declare global {
  namespace Cloudflare {
    interface Env extends RelayEnv {}
    interface GlobalProps {
      mainModule: typeof import('./index')
      durableNamespaces: 'FeedStore'
    }
  }
}
