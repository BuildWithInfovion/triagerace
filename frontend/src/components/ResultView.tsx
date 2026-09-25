import { useState } from 'react'
import { RunState, ScenarioDetail } from '../api'

interface Props {
  run: RunState
  scenario: ScenarioDetail
  onRunAgain: () => void
}

function formatSecs(s: number | null): string {
  if (s === null || s === undefined) return '—'
  if (s < 60) return `${s.toFixed(1)}s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

function mmss(s: number | null): string {
  if (s === null || s === undefined) return '—'
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

export default function ResultView({ run, scenario, onRunAgain }: Props) {
  const [showOutput, setShowOutput] = useState(false)

  const winner = run.hypotheses.find(h => h.id === run.winner_hypothesis_id)
  const metrics = scenario.metrics

  const raceSecs = run.race_duration_seconds
  const verifySecs = run.verify_duration_seconds
  const bobHypSecs = metrics.bob_hypothesis_generation_seconds
  const manualSecs = metrics.manual_baseline_seconds

  const totalAssistedSecs =
    (bobHypSecs !== null ? bobHypSecs : null) !== null &&
    raceSecs !== null &&
    verifySecs !== null
      ? (bobHypSecs ?? 0) + raceSecs + verifySecs
      : null

  const speedup =
    manualSecs !== null && totalAssistedSecs !== null && totalAssistedSecs > 0
      ? manualSecs / totalAssistedSecs
      : null

  // Parse suite pass count from verify_output
  const verifyOut = run.verify_output ?? ''
  const suiteMatch = verifyOut.match(/(\d+) passed/)
  const failMatch = verifyOut.match(/(\d+) failed/)
  const passedCount = suiteMatch ? parseInt(suiteMatch[1]) : null
  const failedCount = failMatch ? parseInt(failMatch[1]) : 0

  const repoUrl = import.meta.env.VITE_REPO_URL ?? ''

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      <header className="border-b border-gray-800 px-8 py-5">
        <h1 className="text-3xl font-bold">TriageRace</h1>
        <p className="text-gray-400 mt-1 text-sm">Results — {scenario.title}</p>
      </header>

      <main className="flex-1 px-8 py-8 max-w-4xl w-full mx-auto flex flex-col gap-8">

        {/* Verify status banner */}
        <div className={`rounded px-4 py-3 text-base font-semibold border ${
          run.verify_status === 'verified'
            ? 'bg-green-900/30 border-green-600 text-green-200'
            : 'bg-red-900/30 border-red-700 text-red-200'
        }`}>
          {run.verify_status === 'verified'
            ? `✓ ${passedCount !== null ? passedCount : '?'} passed, ${failedCount} failed — full suite is green`
            : '✗ Full suite failed after applying the winning patch'}
        </div>

        {/* Winning patch diff */}
        {winner && (
          <section>
            <h2 className="text-sm font-medium text-gray-300 mb-2">Winning patch</h2>
            <p className="text-xs text-gray-400 mb-1">{winner.role} — <span className="text-white">{winner.title}</span></p>
            <div className="font-mono text-xs rounded overflow-hidden border border-gray-700">
              {winner.patch.map((edit, i) => (
                <div key={i}>
                  {edit.find.split('\n').map((line, j) => (
                    <div key={`f${j}`} className="bg-red-950/60 text-red-300 px-3 py-0.5 whitespace-pre">- {line}</div>
                  ))}
                  {edit.replace.split('\n').map((line, j) => (
                    <div key={`r${j}`} className="bg-green-950/60 text-green-300 px-3 py-0.5 whitespace-pre">+ {line}</div>
                  ))}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Full suite output */}
        <section>
          <button
            className="text-sm text-gray-400 hover:text-gray-200 mb-1"
            onClick={() => setShowOutput(v => !v)}
          >
            {showOutput ? '▾' : '▸'} Full pytest output
          </button>
          {showOutput && (
            <pre className="bg-gray-900 border border-gray-800 rounded p-3 text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap max-h-80 overflow-y-auto">
              {verifyOut || '(no output)'}
            </pre>
          )}
        </section>

        {/* Metrics panel */}
        <section>
          <h2 className="text-sm font-medium text-gray-300 mb-3">Measured results</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

            {/* Manual */}
            <div className="bg-gray-900 border border-gray-700 rounded p-4 flex flex-col gap-2">
              <p className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Manual baseline</p>
              <p className="text-4xl font-mono font-bold text-white">
                {manualSecs !== null ? mmss(manualSecs) : '—'}
              </p>
              {metrics.manual_baseline_steps !== null && (
                <p className="text-xs text-gray-400">{metrics.manual_baseline_steps} manual steps</p>
              )}
              {manualSecs === null && (
                <p className="text-xs text-yellow-500">not measured yet</p>
              )}
              <p className="text-xs text-gray-600 leading-snug">{metrics.manual_baseline_note}</p>
            </div>

            {/* Assisted */}
            <div className="bg-gray-900 border border-gray-700 rounded p-4 flex flex-col gap-2">
              <p className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Assisted (IBM Bob)</p>
              <p className="text-4xl font-mono font-bold text-white">
                {totalAssistedSecs !== null ? mmss(totalAssistedSecs) : '—'}
              </p>
              <div className="text-xs text-gray-400 flex flex-col gap-0.5">
                <span>Bob hypothesis generation: <span className="text-white font-mono">{formatSecs(bobHypSecs)}</span></span>
                <span>Race (4 parallel tests): <span className="text-white font-mono">{formatSecs(raceSecs)}</span></span>
                <span>Verify (full suite): <span className="text-white font-mono">{formatSecs(verifySecs)}</span></span>
              </div>
              {totalAssistedSecs === null && (
                <p className="text-xs text-yellow-500">not fully measured yet</p>
              )}
              <p className="text-xs text-gray-600 leading-snug">{metrics.bob_hypothesis_note}</p>
            </div>
          </div>

          {/* Speed-up */}
          {speedup !== null && (
            <div className="mt-4 text-center">
              <span className="text-5xl font-black text-green-400">{speedup.toFixed(1)}×</span>
              <p className="text-sm text-gray-400 mt-1">faster than manual debugging</p>
            </div>
          )}
        </section>

        {/* Footer */}
        <footer className="border-t border-gray-800 pt-4 text-xs text-gray-500 flex flex-col gap-1">
          <p>
            Hypotheses generated by 4 parallel IBM Bob subagents · session logs in{' '}
            <code>bob_sessions/</code>
          </p>
          {repoUrl && (
            <a href={repoUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
              GitHub repo →
            </a>
          )}
        </footer>

        <button
          className="self-start bg-gray-800 hover:bg-gray-700 text-white px-5 py-2 rounded text-sm"
          onClick={onRunAgain}
        >
          ← Run again
        </button>
      </main>
    </div>
  )
}
