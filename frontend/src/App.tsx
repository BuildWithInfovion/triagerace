import { useState } from 'react'
import { RunState, ScenarioDetail } from './api'
import IntakeView from './components/IntakeView'
import RaceView from './components/RaceView'
import ResultView from './components/ResultView'

type View = 'intake' | 'race' | 'result'

export default function App() {
  const [view, setView] = useState<View>('intake')
  const [runId, setRunId] = useState<string | null>(null)
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null)
  const [finalRun, setFinalRun] = useState<RunState | null>(null)

  function handleRaceStarted(id: string, sc: ScenarioDetail) {
    setRunId(id)
    setScenario(sc)
    setView('race')
  }

  function handleApplied(run: RunState) {
    setFinalRun(run)
    setView('result')
  }

  function handleRunAgain() {
    setView('intake')
    setRunId(null)
    setFinalRun(null)
  }

  if (view === 'intake') {
    return <IntakeView onRaceStarted={handleRaceStarted} />
  }

  if (view === 'race' && runId && scenario) {
    return (
      <RaceView
        runId={runId}
        scenario={scenario}
        onApplied={handleApplied}
        onRunAgain={handleRunAgain}
      />
    )
  }

  if (view === 'result' && finalRun && scenario) {
    return (
      <ResultView
        run={finalRun}
        scenario={scenario}
        onRunAgain={handleRunAgain}
      />
    )
  }

  // Fallback (should not reach here)
  return <IntakeView onRaceStarted={handleRaceStarted} />
}
