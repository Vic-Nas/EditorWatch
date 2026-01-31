import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analysis import messages


def run():
    print('Validating message templates...')
    failures = []
    for key, entry in messages.MESSAGES.items():
        ctx = entry.get('example_context', {})
        rendered = messages.render(key, **ctx)
        print('-', key, '->', rendered)
        # Basic checks: not empty and no leftover '{' or '}'
        if not rendered or '{' in rendered or '}' in rendered:
            failures.append((key, rendered))
    if failures:
        print('\nFailures:')
        for k, r in failures:
            print(k, '->', r)
    else:
        print('All message templates rendered OK')


if __name__ == '__main__':
    run()
