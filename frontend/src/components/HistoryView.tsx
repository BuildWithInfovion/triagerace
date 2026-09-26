import { useEffect, useState } from 'react'
import { api, HistoryEntry } from '../api'

interface Props {
  onRunAgain: () => void
}

function formatDate(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

function formatSecs(s: number | null): string {
  if (s === null) return '—'
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    verified: 'bg-green-800 text-green-200',
    race_done: 'bg-blue-800 text-blue-200',
    racing: 'bg-yellow-800 text-yellow-200 animate-pulse',
    verify_failed: 'bg-red-800 text-red-200',
    created: 'bg-gray-700 text-gray-300',
  }
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded ${map[status] ?? 'bg-gray-700 text-gray-300'}`}>
      {status.replace('_', ' ').toUpperCase()}
    </span>
  )
}

export default function HistoryView({ onRunAgain }: Props) {
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.history()
      .then(data => { setEntries(data); setLoading(false) })
      .catch(() => { setError('Failed to load history'); setLoading(false) })
  }, [])

  const verified = entries.filter(e => e.verify_status === 'verified').length
  const avgRace = entries.filter(e => e.race_duration_seconds !== null).length > 0
    ? entries.reduce((sum, e) => sum + (e.race_duration_seconds ?? 0), 0) /
      entries.filter(e => e.race_duration_seconds !== null).length
    : null

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      <header className="border-b border-gray-800 px-8 py-5">
        <h1 className="text-3xl font-bold">TriageRace</h1>
        <p className="text-gray-400 mt-1 text-sm">Race history — all runs</p>
      </header>

      <main className="flex-1 px-8 py-8 max-w-5xl w-full mx-auto flex flex-col gap-6">

        {/* Summary stats */}
        {entries.length > 0 && (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded p-4 text-center">
              <p className="text-3xl font-bold text-white">{entries.length}</p>
              <p className="text-xs text-gray-400 mt-1">Total races</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded p-4 text-center">
              <p className="text-3xl font-bold text-green-400">{verified}</p>
              <p className="text-xs text-gray-400 mt-1">Verified fixes</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded p-4 text-center">
              <p className="text-3xl font-bold text-blue-400">
                {avgRace !== null ? `${avgRace.toFixed(1)}s` : '—'}
              </p>
              <p className="text-xs text-gray-400 mt-1">Avg race time</p>
            </div>
          </div>
        )}

        {loading && <p className="text-gray-500">Loading…</p>}
        {error && <p className="text-red-400">{error}</p>}

        {!loading && entries.length === 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded p-6 text-center text-gray-500">
            No races yet. Run your first race to see history here.
          </div>
        )}

        {/* History table */}
        {entries.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 uppercase tracking-wide">
                  <th className="text-left px-4 py-3">When</th>
                  <th className="text-left px-4 py-3">Scenario</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Winner</th>
                  <th className="text-right px-4 py-3">Race time</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(e => (
                  <tr key={e.run_id} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/40">
                    <td className="px-4 py-3 text-gray-400 whitespace-nowrap">{formatDate(e.created_at)}</td>
                    <td className="px-4 py-3 text-gray-200">{e.scenario_title}</td>
                    <td className="px-4 py-3"><StatusBadge status={e.status} /></td>
                    <td className="px-4 py-3">
                      {e.winner_hypothesis_id ? (
                        <span className="text-green-400 font-medium">{e.winner_hypothesis_id}</span>
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-white">
                      {formatSecs(e.race_duration_seconds)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex gap-3">
          <button
            className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded text-sm font-semibold"
            onClick={onRunAgain}
          >
            🏁 New race
          </button>
          <button
            className="bg-gray-800 hover:bg-gray-700 text-gray-300 px-5 py-2 rounded text-sm"
            onClick={() => api.history().then(setEntries)}
          >
            ↺ Refresh
          </button>
        </div>
      </main>
    </div>
  )
}
