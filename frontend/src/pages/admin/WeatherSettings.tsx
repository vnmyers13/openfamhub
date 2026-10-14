import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { searchPlaces, useSetWeatherLocation, useWeatherLocation, type Place } from '../../api/home'

const input = 'w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white disabled:opacity-50'
const button = 'rounded px-3 py-2 text-sm font-medium disabled:opacity-50'

/** Admin › Settings: where the family's weather comes from (Open-Meteo, no key). */
export default function WeatherSettings() {
  const { data: current } = useWeatherLocation()
  const save = useSetWeatherLocation()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Place[] | null>(null)
  const [units, setUnits] = useState<'fahrenheit' | 'celsius'>('fahrenheit')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const search = async (e: React.FormEvent) => {
    e.preventDefault()
    setMessage(null)
    setBusy(true)
    try {
      setResults(await searchPlaces(query.trim()))
    } catch (err) {
      setMessage({ ok: false, text: errorDetail(err, "Couldn't search places") })
    } finally {
      setBusy(false)
    }
  }
  const pick = async (place: Place | null) => {
    setMessage(null)
    try {
      await save.mutateAsync(place ? { ...place, units } : null)
      setResults(null)
      setQuery('')
      setMessage({ ok: true, text: place ? `Weather is now for ${place.name}` : 'Weather turned off' })
    } catch (err) {
      setMessage({ ok: false, text: errorDetail(err, "Couldn't save the weather location") })
    }
  }
  return (
    <section className="space-y-3 rounded-xl border border-gray-800 bg-gray-900 p-6" aria-label="Weather">
      <h2 className="text-sm font-medium text-gray-300">Weather</h2>
      {message && (
        <div className={`rounded px-3 py-2 text-sm ${message.ok ? 'bg-green-900/40 text-green-300' : 'bg-red-900/50 text-red-300'}`}>{message.text}</div>
      )}
      <p className="text-sm text-gray-400">
        {current ? <>Showing weather for <span className="text-white">{current.name}</span> in {current.units === 'celsius' ? '°C' : '°F'}.</> : 'No location yet.'}
        {current && <button className="ml-2 text-primary hover:underline" onClick={() => pick(null)}>Turn off</button>}
      </p>
      <form onSubmit={search} className="flex gap-2">
        <input className={input} placeholder="Town or city" aria-label="Find a place" value={query} minLength={2}
          onChange={(e) => setQuery(e.target.value)} />
        <select className={`${input} w-24`} aria-label="Units" value={units} onChange={(e) => setUnits(e.target.value as 'fahrenheit' | 'celsius')}>
          <option value="fahrenheit">°F</option>
          <option value="celsius">°C</option>
        </select>
        <button type="submit" className={`${button} bg-gray-800 text-gray-200 hover:bg-gray-700`} disabled={busy || query.trim().length < 2}>Search</button>
      </form>
      {results && results.length === 0 && <p className="text-sm text-gray-500">No places found.</p>}
      {results && results.length > 0 && (
        <ul className="space-y-1">
          {results.map((p) => (
            <li key={`${p.latitude},${p.longitude}`}>
              <button className="w-full rounded px-3 py-2 text-left text-sm text-gray-200 hover:bg-gray-800" onClick={() => pick(p)}>{p.name}</button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-gray-500">Forecasts come from Open-Meteo and refresh every 10 minutes.</p>
    </section>
  )
}
