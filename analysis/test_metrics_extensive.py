import sys
import os
import math
import random
from pprint import pprint

# Ensure workspace root is on sys.path so 'analysis' package imports reliably
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analysis import metrics

MS = 1000


def now_ms():
    return int(random.randint(1_000_000, 9_000_000))


def make_event(t, typ='insert', char_count=1, file='file.py'):
    return {'timestamp': t, 'type': typ, 'char_count': char_count, 'file': file}


def scenario_empty():
    return []


def scenario_only_deletes():
    t = now_ms()
    return [make_event(t + i * 1000, 'delete', char_count=1) for i in range(5)]


def scenario_zero_chars():
    t = now_ms()
    return [make_event(t + i * 500, 'insert', char_count=0) for i in range(4)]


def scenario_identical_timestamps():
    t = now_ms()
    return [make_event(t, 'insert', char_count=random.randint(1,5)) for _ in range(6)]


def scenario_regular_intervals(n=5, interval_ms=1000):
    t = now_ms()
    return [make_event(t + i * interval_ms, 'insert', char_count=random.randint(1,5)) for i in range(n)]


def scenario_varied_intervals(n=6):
    t = now_ms()
    events = []
    cur = t
    for i in range(n):
        step = random.choice([200, 500, 1000, 2000, 5000])
        cur += step
        events.append(make_event(cur, 'insert', char_count=random.randint(1,6)))
    return events


def scenario_large_pastes():
    t = now_ms()
    events = []
    for i in range(8):
        if i % 3 == 0:
            events.append(make_event(t + i * 1000, 'insert', char_count=500))
        else:
            events.append(make_event(t + i * 1000, 'insert', char_count=random.randint(1,8)))
    return events


def scenario_mixed_with_deletes():
    t = now_ms()
    ev = []
    for i in range(12):
        if i % 4 == 0:
            ev.append(make_event(t + i * 400, 'delete', char_count=random.randint(1,4)))
        else:
            ev.append(make_event(t + i * 400, 'insert', char_count=random.randint(1,8)))
    return ev


def scenario_high_velocity():
    t = now_ms()
    # Many chars in short windows -> high CPM
    events = []
    for i in range(60):
        events.append(make_event(t + i * 500, 'insert', char_count=50))
    return events


def scenario_sessions():
    t = now_ms()
    ev = []
    # session 1
    for i in range(5):
        ev.append(make_event(t + i * 1000, 'insert', char_count=10, file='a.py'))
    # big gap
    t += 60 * 1000 * 10
    # session 2
    for i in range(3):
        ev.append(make_event(t + i * 2000, 'insert', char_count=5, file='b.py'))
    return ev


SCENARIOS = {
    'empty': scenario_empty,
    'only_deletes': scenario_only_deletes,
    'zero_chars': scenario_zero_chars,
    'identical_timestamps': scenario_identical_timestamps,
    'regular_intervals': scenario_regular_intervals,
    'varied_intervals': scenario_varied_intervals,
    'large_pastes': scenario_large_pastes,
    'mixed_with_deletes': scenario_mixed_with_deletes,
    'high_velocity': scenario_high_velocity,
    'sessions': scenario_sessions,
}


def validate_metrics(m):
    failures = []

    # Keys to check and their valid ranges
    checks = [
        ('incremental_score', 0.0, 10.0),
        ('typing_variance', 0.0, 10.0),
        ('error_correction_ratio', 0.0, 10.0),
        ('paste_burst_count', 0, None),
        ('session_consistency', 0.0, 10.0),
        ('velocity', None, None),
        ('overall_score', 0.0, 10.0),
    ]

    for key, low, high in checks:
        if key not in m:
            failures.append(f'missing key: {key}')
            continue
        val = m[key]
        # velocity is nested
        if key == 'velocity':
            if not isinstance(val, dict):
                failures.append('velocity not dict')
                continue
            vs = val.get('score', None)
            if vs is None:
                failures.append('velocity.score missing')
            else:
                if math.isnan(vs):
                    failures.append('velocity.score is NaN')
                if not (0.0 <= vs <= 10.0):
                    failures.append(f'velocity.score out of range: {vs}')
            continue

        if isinstance(val, (int, float)):
            if isinstance(val, float) and math.isnan(val):
                failures.append(f'{key} is NaN')
            if low is not None and val < low:
                failures.append(f'{key} < {low}: {val}')
            if high is not None and val > high:
                failures.append(f'{key} > {high}: {val}')
        else:
            # allow paste_burst_count to be int
            if key == 'paste_burst_count' and isinstance(val, int):
                pass
            else:
                failures.append(f'{key} has unexpected type: {type(val)}')

    return failures


def run_once(name, gen_func):
    print('\n--- Scenario:', name)
    events = gen_func() if callable(gen_func) else gen_func
    # sort by timestamp (some generators may produce ordered events but be safe)
    events = sorted(events, key=lambda e: e['timestamp'])

    # Run individual metrics
    inc = metrics.incremental_score(events)
    tv = metrics.typing_variance(events)
    ec = metrics.error_correction_ratio(events)
    pb = metrics.paste_burst_detection(events)
    vel = metrics.code_velocity_analysis(events)
    sc = metrics.session_consistency_score(events)
    fl = metrics.file_level_analysis(events)
    wp = metrics.analyze_work_patterns(events)
    allm = metrics.calculate_all_metrics(events)

    summary = {
        'incremental_score': inc,
        'typing_variance': tv,
        'error_correction_ratio': ec,
        'paste_burst_count': pb,
        'session_consistency': sc,
        'velocity': vel,
        'overall_score': allm.get('overall_score', None),
    }

    pprint(summary)

    failures = validate_metrics({**summary, **({'file_risks': fl} if fl else {})})
    if failures:
        print('FAILURES:')
        for f in failures:
            print(' -', f)
    else:
        print('OK')

    return summary, failures


def run_all():
    random.seed(42)
    all_failures = {}
    results = {}
    for name, gen in SCENARIOS.items():
        res, failures = run_once(name, gen)
        results[name] = res
        if failures:
            all_failures[name] = failures

    print('\n=== Summary ===')
    print('Total scenarios:', len(SCENARIOS))
    print('Failures:', len(all_failures))
    if all_failures:
        for k, v in all_failures.items():
            print('\nScenario', k)
            for it in v:
                print(' -', it)

    return results, all_failures


if __name__ == '__main__':
    run_all()
