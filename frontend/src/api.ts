// All API calls for TriageRace frontend

export interface ScenarioSummary {
  id: string
  title: string
  hypothesis_count: number
  hypothesis_sources: {
    'ibm-bob-subagent': number
    'dev-placeholder': number
    other: number
  }
}

export interface PatchEdit {
  file: string
  find: string
  replace: string
}

export interface HypothesisMeta {
  id: string
  role: string
  title: string
  suspected_file: string
  suspected_line: number
  reasoning: string
  evidence: string[]
  confidence: number
  patch: PatchEdit[]
  source: string
  generated_at: string
  is_dev: boolean
}

export interface ScenarioDetail {
  id: string
  title: string
  repo_path: string
  failing_test: string
  full_suite: string
  test_timeout_seconds: number
  bug_report: string
  metrics: {
    manual_baseline_seconds: number | null
    manual_baseline_steps: number | null
    manual_baseline_note: string
    bob_hypothesis_generation_seconds: number | null
    bob_hypothesis_note: string
  }
  hypotheses: HypothesisMeta[]
}

export type HypStatus =
  | 'queued' | 'patching' | 'testing'
  | 'passed' | 'failed' | 'patch_failed' | 'timeout' | 'error'

export type RunStatus =
  | 'created' | 'racing' | 'race_done'
  | 'verifying' | 'verified' | 'verify_failed'

export interface HypothesisState extends HypothesisMeta {
  status: HypStatus
  started_at: number | null
  finished_at: number | null
  test_output: string | null
}

export interface RunState {
  run_id: string
  scenario_id: string
  status: RunStatus
  created_at: number
  race_started_at: number | null
  race_finished_at: number | null
  winner_hypothesis_id: string | null
  verify_status: string | null
  verify_started_at: number | null
  verify_finished_at: number | null
  verify_output: string | null
  baseline_status: 'fail' | 'broken' | null
  baseline_output: string | null
  race_duration_seconds: number | null
  verify_duration_seconds: number | null
  hypotheses: HypothesisState[]
}

const BASE = ''  // same origin; Vite proxy handles /api in dev

async function _get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`)
  return r.json()
}

async function _post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const text = await r.text()
    throw new Error(`POST ${path} → ${r.status}: ${text}`)
  }
  return r.json()
}

export interface HistoryEntry {
  run_id: string
  scenario_id: string
  scenario_title: string
  status: string
  created_at: number
  winner_hypothesis_id: string | null
  verify_status: string | null
  race_duration_seconds: number | null
}

export const api = {
  scenarios: (): Promise<ScenarioSummary[]> => _get('/api/scenarios'),
  scenario: (id: string): Promise<ScenarioDetail> => _get(`/api/scenarios/${id}`),
  createRun: (scenario_id: string, bug_report_text: string): Promise<{ run_id: string }> =>
    _post('/api/runs', { scenario_id, bug_report_text }),
  getRun: (run_id: string): Promise<RunState> => _get(`/api/runs/${run_id}`),
  applyWinner: (run_id: string): Promise<{ ok: boolean }> => _post(`/api/runs/${run_id}/apply`),
  history: (): Promise<HistoryEntry[]> => _get('/api/runs'),
}
