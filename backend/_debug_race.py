import asyncio, os, sys, time, uuid, json, traceback
sys.path.insert(0, '.')
os.environ['TRIAGERACE_DB'] = '../test_debug.db'

from app.db import init_db, insert_run, insert_hypothesis, get_run, get_hypotheses
from app.scenarios import load_all_scenarios
from app.race import run_race

init_db()
scenarios = load_all_scenarios()
sc = scenarios['discount-threshold']
run_id = str(uuid.uuid4())
insert_run(run_id, 'discount-threshold', 'test', time.time())
for h in sc.hypotheses:
    insert_hypothesis(run_id, h.id, json.dumps(h.model_dump()))

print('Starting race for run_id:', run_id)
try:
    asyncio.run(run_race(run_id))
except Exception as e:
    traceback.print_exc()

run = get_run(run_id)
print('Run status:', run['status'])
print('Winner:', run['winner_hypothesis_id'])
print('Verify output:', run['verify_output'])
hyps = get_hypotheses(run_id)
for h in hyps:
    print(' ', h['hypothesis_id'], ':', h['status'], '|', (h['test_output'] or '')[:120])
