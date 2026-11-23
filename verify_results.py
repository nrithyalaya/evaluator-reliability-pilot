"""Verify archived model outputs and recalculate descriptive scores (stdlib only).

Run: python verify_results.py
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, json, sys

ROOT = Path(__file__).resolve().parent

def read(path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def verify():
    dataset = ROOT / 'data/benchmark_v2.csv'
    manifest = json.loads((ROOT / 'results/colab_live_manifest.json').read_text())
    actual_sha = hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert actual_sha == manifest['dataset_sha256'], 'Benchmark hash does not match original run manifest'
    cases = read(dataset)
    assert len(cases)==640 and len({x['case_id'] for x in cases})==640, 'Unexpected benchmark size/duplicate IDs'
    rows = read(ROOT / 'results/colab_live_raw.csv')
    assert manifest['status']=='completed' and manifest['test_mode']=='actual_model_inference'
    assert len(rows)==manifest['calls_written']==manifest['test_calls_planned']==20
    case_by_id={r['case_id']:r for r in cases}
    counts=defaultdict(Counter)
    pairs=defaultdict(dict)
    seen=set()
    for r in rows:
        assert r['run_id']==manifest['run_id'] and r['model']==manifest['model']
        assert not r['error'].strip() and r['prediction'] in ('CORRECT','INCORRECT')
        assert r['task_id']==manifest['task_id'] and r['split']=='development'
        assert r['case_id'] in case_by_id, f"Missing case ID {r['case_id']}"
        key=(r['case_id'],r['rubric'])
        assert key not in seen, 'Repeated model case/rubric pair'
        seen.add(key)
        case=case_by_id[r['case_id']]
        assert all(r[k]==case[k] for k in ('task_id','style','split'))
        assert r['rubric'] in ('basic','boundary')
        truth=case['is_correct']=='1'
        prediction=r['prediction']=='CORRECT'
        counts[r['rubric']]['total']+=1
        counts[r['rubric']]['correct_grade']+=(truth==prediction)
        counts[r['rubric']]['false_accept']+=(not truth and prediction)
        counts[r['rubric']]['false_reject']+=(truth and not prediction)
        pairs[r['case_id']][r['rubric']]=r['prediction']
    assert len(pairs)==10 and all(len(v)==2 for v in pairs.values())
    assert counts['basic']==Counter({'total':10,'correct_grade':5,'false_accept':4,'false_reject':1})
    assert counts['boundary']==Counter({'total':10,'correct_grade':5,'false_accept':3,'false_reject':2})
    mismatch=sum(v['basic']!=v['boundary'] for v in pairs.values())
    assert mismatch==2
    # Explicit check: attack and placebo have identical verdict patterns for each correctness class and rubric.
    for suffix in ('0','1'):
        for rubric in ('basic','boundary'):
            a=pairs[f'T039_{suffix}_instruction'][rubric]
            p=pairs[f'T039_{suffix}_placebo'][rubric]
            assert a==p, 'Attack and placebo verdict patterns differ'
    print('PASS: 640 unique constructed cases; manifest SHA256 verified')
    print('PASS: 20 real-run records, 20 parseable grades, no recorded execution errors')
    print('PASS: 10 matched presentations / 2 grading prompts, 2 verdict differences')
    print('BASIC: accuracy=5/10 false_accept=4/5 false_reject=1/5')
    print('BOUNDARY: accuracy=5/10 false_accept=3/5 false_reject=2/5')
    print('INSTRUCTION vs PLACEBO: same verdict pattern in this run')
    print('LIMITATION: Only one development-set question; observations are descriptive and inconclusive')

if __name__=='__main__':
    try: verify()
    except (AssertionError,ValueError,KeyError) as ex:
        print('VERIFICATION FAILED:',str(ex),file=sys.stderr)
        raise SystemExit(1)
