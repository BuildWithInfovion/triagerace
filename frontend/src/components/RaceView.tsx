import { useEffect, useRef, useState } from 'react'
import { api, RunState, ScenarioDetail } from '../api'
import HypothesisCard from './HypothesisCard'

interface Props {
  runId: string
  scenario: ScenarioDetail
  onApplied: (runState: RunState) => void
  onRunAgain: () => void
}

const FINAL_RACE = new Set(['race_done', 'verifying', 'verified', 'verify_failed'])
const POLL_MS = 500

function formatSecs(s: number) {
  if (s < 60) return `${s.toFixed(1)}s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

export default function RaceView({ runId, scenario, onApplied, onRunAgain }: Props) {
  const [run, setRun] = useState<RunState | null>(null)
  const [now, setNow] = useState(Date.now())
  const [applyLoading, setApplyLoading] = useState(false)
  const [applyError, setApplyError] = useState('')
  const pollerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Live clock
  useEffect(() => {
    timerRef.current = setInterval(() => setNow(Date.now()), 200)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  // Polling
  useEffect(() => {
    function poll() {
      api.getRun(runId).then(r => {
        setRun(r)
        if (FINAL_RACE.has(r.status)) {
          if (pollerRef.current) clearInterval(pollerRef.current)
          // If already verified/verify_failed, pass to result view
          if (r.status === 'verified' || r.status === 'verify_failed') {
            onApplied(r)
          }
        }
      }).catch(console.error)
    }
    poll()
    pollerRef.current = setInterval(poll, POLL_MS)
    return () => { if (pollerRef.current) clearInterval(pollerRef.current) }
  }, [runId])

  async function applyFix() {
    setApplyLoading(true)
    setApplyError('')
    try {
      await api.applyWinner(runId)
      // Resume polling — it will detect verified state
      pollerRef.current = setInterval(() => {
        api.getRun(runId).then(r => {
          setRun(r)
          if (r.status === 'verified' || r.status === 'verify_failed') {
            if (pollerRef.current) clearInterval(pollerRef.current)
            onApplied(r)
          }
        }).catch(console.error)
      }, POLL_MS)
    } catch (e: unknown) {
      setApplyError(e instanceof Error ? e.message : 'Apply failed')
      setApplyLoading(false)
    }
  }

  if (!run) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <span className="text-gray-400">Starting race…</span>
      </div>
    )
  }

  const raceStart = run.race_started_at
  const raceEnd = run.race_finished_at
  const raceSecs = raceStart
    ? raceEnd
      ? raceEnd - raceStart
      : now / 1000 - raceStart
    : null

  const allDone = FINAL_RACE.has(run.status)
  const hasWinner = !!run.winner_hypothesis_id
  const passedCount = run.hypotheses.filter(h => h.status === 'passed').length
  const consensus = allDone && passedCount > 1

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 px-8 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">TriageRace</h1>
          <p className="text-xs text-gray-400 mt-0.5">{scenario.title}</p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-mono font-bold text-white">
            {raceSecs !== null ? formatSecs(raceSecs) : '—'}
          </div>
          <div className="text-xs text-gray-400">
            {allDone ? 'Race finished' : 'Race timer'}
          </div>
        </div>
      </header>

      <main className="flex-1 px-8 py-6 max-w-7xl w-full mx-auto flex flex-col gap-6">

        {/* Baseline strip */}
        <div className={`rounded px-4 py-3 text-sm border ${
          run.baseline_status === 'fail'
            ? 'bg-gray-900 border-gray-700 text-gray-300'
            : run.baseline_status === 'broken'
            ? 'bg-red-900/40 border-red-700 text-red-200'
            : 'bg-gray-900 border-gray-800 text-gray-500'
        }`}>
          {run.baseline_status === 'fail' && (
            <>
              <span className="font-semibold text-white">Baseline:</span>{' '}
              failing test fails on original code{' '}
              <span className="text-red-400 font-bold">✗</span>{' '}
              <span className="text-gray-400">(as expected — bug is real)</span>
            </>
          )}
          {run.baseline_status === 'broken' && (
            <span className="font-semibold text-red-300">⚠ SCENARIO BROKEN — baseline test passed on unpatched code</span>
          )}
          {!run.baseline_status && (
            <span className="text-gray-400">Running baseline check…</span>
          )}
        </div>

        {/* Consensus: several independent lenses produced a passing fix */}
        {consensus && (
          <div className="bg-green-900/30 border border-green-700 rounded px-4 py-3 text-sm text-green-200">
            <span className="font-semibold">✓ Consensus: {passedCount} of {run.hypotheses.length} independent lenses</span>{' '}
            produced a fix that passes the real failing test. The highest-confidence one is selected.
          </div>
        )}

        {/* No winner */}
        {allDone && !hasWinner && (
          <div className="bg-gray-800 border border-gray-700 rounded px-4 py-3 text-sm text-gray-300">
            No hypothesis fixed the failing test. All patches were either incorrect or inapplicable.
          </div>
        )}

        {/* Hypothesis cards — 2×2 grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-2 gap-4">
          {run.hypotheses.map(h => (
            <HypothesisCard
              key={h.id}
              hyp={h}
              isWinner={h.id === run.winner_hypothesis_id}
              winnerLabel={consensus ? 'SELECTED' : 'WINNER'}
              raceStartedAt={run.race_started_at}
              now={now}
            />
          ))}
        </div>

        {/* Apply button */}
        {hasWinner && run.status === 'race_done' && (
          <div className="flex flex-col gap-2">
            {applyError && (
              <p className="text-sm text-red-400">{applyError}</p>
            )}
            <button
              className="self-start bg-green-600 hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold px-6 py-3 rounded text-base transition-colors"
              onClick={applyFix}
              disabled={applyLoading}
            >
              {applyLoading ? 'Running full suite…' : consensus ? '✅ Apply selected fix & run full suite' : '✅ Apply winning fix & run full suite'}
            </button>
          </div>
        )}

        {run.status === 'verifying' && (
          <div className="text-sm text-gray-400 animate-pulse">
            Applying winner patch and running full test suite…
          </div>
        )}

        <div className="flex justify-end">
          <button
            className="text-xs text-gray-500 hover:text-gray-300 underline"
            onClick={onRunAgain}
          >
            ← Run again
          </button>
        </div>
      </main>
    </div>
  )
}
