import { useMutation, useQueryClient } from '@tanstack/react-query'
import { enqueueOperation } from '../lib/idb'
import { useOfflineStore } from '../lib/offline-state'

interface UseOfflineMutationOptions<TData, TVariables> {
  queryKey: unknown[]
  entity: 'shopping-item' | 'chore-instance'
  endpoint: string
  mutationType: 'create' | 'update' | 'delete'
  mutationFn: (variables: TVariables) => Promise<TData>
}

export function useOfflineMutations<TData, TVariables>({
  queryKey,
  entity,
  endpoint,
  mutationType,
  mutationFn,
}: UseOfflineMutationOptions<TData, TVariables>) {
  const queryClient = useQueryClient()
  const incrementPending = useOfflineStore((s) => s.incrementPending)

  return useMutation<TData, unknown, TVariables>({
    mutationFn: async (variables: TVariables) => {
      const isOnline = navigator.onLine

      if (isOnline) {
        return mutationFn(variables)
      }

      await enqueueOperation({
        type: mutationType,
        entity,
        data: variables as Record<string, unknown>,
        endpoint,
      })

      incrementPending()
      return variables as unknown as TData
    },
    onSuccess: (_data, _variables, _context) => {
      queryClient.invalidateQueries({ queryKey })
    },
  })
}
