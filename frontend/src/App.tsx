import { useState } from 'react'
import { RunState, ScenarioDetail } from './api'
import IntakeView from './components/IntakeView'
import RaceView from './components/RaceView'
import ResultView from './components/ResultView'
import HistoryView from './components/HistoryView'

type View = 'intake' | 'race' | 'result' | 'history'

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
    return <IntakeView onRaceStarted={handleRaceStarted} onViewHistory={() => setView('history')} />
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
        onViewHistory={() => setView('history')}
      />
    )
  }

  if (view === 'history') {
    return <HistoryView onRunAgain={handleRunAgain} />
  }

  return <IntakeView onRaceStarted={handleRaceStarted} onViewHistory={() => setView('history')} />
}
