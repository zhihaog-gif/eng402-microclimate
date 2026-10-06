#!/usr/bin/env python3
"""Verify checksums."""
from pathlib import Path
from hashlib import sha256
import argparse
import sys

def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path,
                        default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root = args.directory.resolve()
    failures = []
    checked = 0
    for line in (root / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f'Path outside package: {relative}')
        if not path.is_file():
            failures.append(f'MISSING {relative}')
        elif digest(path) != expected:
            failures.append(f'CHANGED {relative}')
        checked += 1
    for failure in failures:
        print(failure)
    print(f'Checked {checked} files; {len(failures)} mismatches.')
    return bool(failures)

if __name__ == '__main__':
    sys.exit(main())
