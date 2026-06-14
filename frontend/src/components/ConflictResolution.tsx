interface ConflictResolutionProps {
  entity: 'shopping-item' | 'chore-instance' | 'recipe'
  localData: Record<string, unknown>
  serverData: Record<string, unknown>
}

export function ConflictResolution({ entity, localData, serverData }: ConflictResolutionProps) {
  if (entity === 'shopping-item') {
    return <ShoppingItemConflict localData={localData} serverData={serverData} />
  }
  if (entity === 'recipe') {
    return <RecipeConflict localData={localData} serverData={serverData} />
  }
  return <ChoreInstanceConflict localData={localData} serverData={serverData} />
}

function ShoppingItemConflict({ localData, serverData }: Omit<ConflictResolutionProps, 'entity'>) {
  const localItem = (localData.item as string) || '(deleted)'
  const serverItem = (serverData.item as string) || '(deleted)'
  const localChecked = localData.checked as boolean
  const serverChecked = serverData.checked as boolean
  const localQty = (localData.quantity as string) || ''
  const serverQty = (serverData.quantity as string) || ''

  return (
    <div className="grid grid-cols-2 gap-4 mb-4">
      <div className="border border-blue-300 rounded p-3 bg-blue-50">
        <h3 className="font-semibold text-blue-700 mb-2">Your Version</h3>
        <p><strong>Item:</strong> {localItem}</p>
        <p><strong>Quantity:</strong> {localQty || 'not set'}</p>
        <p><strong>Checked:</strong> {localChecked ? 'Yes' : 'No'}</p>
      </div>
      <div className="border border-gray-300 rounded p-3 bg-gray-50">
        <h3 className="font-semibold text-gray-700 mb-2">Server Version</h3>
        <p><strong>Item:</strong> {serverItem}</p>
        <p><strong>Quantity:</strong> {serverQty || 'not set'}</p>
        <p><strong>Checked:</strong> {serverChecked ? 'Yes' : 'No'}</p>
      </div>
    </div>
  )
}

function ChoreInstanceConflict({ localData, serverData }: Omit<ConflictResolutionProps, 'entity'>) {
  const localStatus = (localData.status as string) || 'unknown'
  const serverStatus = (serverData.status as string) || 'unknown'
  const localCompleted = localData.completed_at as string | undefined
  const serverCompleted = serverData.completed_at as string | undefined

  return (
    <div className="grid grid-cols-2 gap-4 mb-4">
      <div className="border border-blue-300 rounded p-3 bg-blue-50">
        <h3 className="font-semibold text-blue-700 mb-2">Your Version</h3>
        <p><strong>Status:</strong> {localStatus}</p>
        {localCompleted && <p><strong>Completed:</strong> {new Date(localCompleted).toLocaleString()}</p>}
      </div>
      <div className="border border-gray-300 rounded p-3 bg-gray-50">
        <h3 className="font-semibold text-gray-700 mb-2">Server Version</h3>
        <p><strong>Status:</strong> {serverStatus}</p>
        {serverCompleted && <p><strong>Completed:</strong> {new Date(serverCompleted).toLocaleString()}</p>}
      </div>
    </div>
  )
}

function RecipeConflict({ localData, serverData }: Omit<ConflictResolutionProps, 'entity'>) {
  const localTitle = (localData.title as string) || '(deleted)'
  const serverTitle = (serverData.title as string) || '(deleted)'
  const localContent = (localData.content_text as string) || ''
  const serverContent = (serverData.content_text as string) || ''
  const localIngredients = (localData.ingredients_raw as string) || ''
  const serverIngredients = (serverData.ingredients_raw as string) || ''
  const localSteps = (localData.steps_raw as string) || ''
  const serverSteps = (serverData.steps_raw as string) || ''

  return (
    <div className="grid grid-cols-2 gap-4 mb-4">
      <div className="border border-blue-300 rounded p-3 bg-blue-50">
        <h3 className="font-semibold text-blue-700 mb-2">Your Version</h3>
        <p><strong>Title:</strong> {localTitle}</p>
        {localContent && <p><strong>Content:</strong> {localContent}</p>}
        {localIngredients && <p><strong>Ingredients:</strong> {localIngredients}</p>}
        {localSteps && <p><strong>Steps:</strong> {localSteps}</p>}
      </div>
      <div className="border border-gray-300 rounded p-3 bg-gray-50">
        <h3 className="font-semibold text-gray-700 mb-2">Server Version</h3>
        <p><strong>Title:</strong> {serverTitle}</p>
        {serverContent && <p><strong>Content:</strong> {serverContent}</p>}
        {serverIngredients && <p><strong>Ingredients:</strong> {serverIngredients}</p>}
        {serverSteps && <p><strong>Steps:</strong> {serverSteps}</p>}
      </div>
    </div>
  )
}
