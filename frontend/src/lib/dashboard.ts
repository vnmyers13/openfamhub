/** Dashboard cards, in their default order. Customization picks and orders these per person. */
export const WIDGETS = [
  { key: 'events', label: "Today's events" },
  { key: 'weather', label: 'Weather' },
  { key: 'my-day', label: 'My day' },
  { key: 'meals', label: "Today's meals" },
  { key: 'stars', label: 'Family stars' },
  { key: 'announcements', label: 'Announcements' },
  { key: 'birthdays', label: 'Birthdays' },
  { key: 'sync', label: 'Calendar sync', adminOnly: true },
] as const

export type WidgetKey = (typeof WIDGETS)[number]['key']
