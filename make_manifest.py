#!/usr/bin/env python3
"""Create checksums."""
from pathlib import Path
from hashlib import sha256
import argparse
import csv

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    records = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(part in {'.git', '__pycache__'} for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        if relative in {'SHA256SUMS', 'file_manifest.csv'}:
            continue
        h = sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1048576), b''):
                h.update(chunk)
        records.append((relative, path.stat().st_size, h.hexdigest()))
    with (root / 'file_manifest.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['relative_path', 'bytes', 'sha256'])
        writer.writerows(records)
    (root / 'SHA256SUMS').write_text(
        ''.join(f'{digest}  {path}\n' for path, _, digest in records),
        encoding='utf-8')
    print(f'Created manifest for {len(records)} files.')

if __name__ == '__main__':
    main()
