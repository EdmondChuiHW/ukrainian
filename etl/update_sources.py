import argparse
import concurrent.futures
import sys
from pathlib import Path
from typing import List
from urllib.request import Request, urlopen

from tqdm import tqdm

CHUNK_SIZE = 32 * 1024
DOWNLOADS = [
    (
        'Ukrainian',
        'https://kaikki.org/dictionary/Ukrainian/kaikki.org-dictionary-Ukrainian.jsonl',
        'kaikki.org-dictionary-Ukrainian.jsonl',
    ),
    (
        'English',
        'https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl',
        'kaikki.org-dictionary-English.jsonl',
    ),
]


def download_one(name: str, url: str, dest: Path, position: int, disable: bool) -> None:
    request = Request(url, headers={'User-Agent': 'etl/update_sources.py'})
    with urlopen(request, timeout=60) as response:
        total = response.getheader('Content-Length')
        total_bytes = int(total) if total and total.isdigit() else None

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, 'wb') as out_file, tqdm(
            total=total_bytes,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            desc=name,
            position=position,
            leave=True,
            disable=disable,
        ) as progress_bar:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                out_file.write(chunk)
                progress_bar.update(len(chunk))


def concat_files(source_paths: List[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as destination:
        for source_path in source_paths:
            last_chunk = b''
            with open(source_path, 'rb') as source_file:
                for chunk in iter(lambda: source_file.read(CHUNK_SIZE), b''):
                    destination.write(chunk)
                    last_chunk = chunk
            if source_path.stat().st_size > 0 and not last_chunk.endswith(b'\n'):
                destination.write(b'\n')


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    sources_dir = base_dir / 'sources'
    sources_dir.mkdir(parents=True, exist_ok=True)

    disable_progress = not sys.stdout.isatty()
    destinations = [sources_dir / filename for _, _, filename in DOWNLOADS]

    print(f'Downloading sources into {sources_dir}')
    if disable_progress:
        print('Starting downloads...')

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(DOWNLOADS)) as executor:
        futures = [
            executor.submit(download_one, name, url, dest, idx, disable_progress)
            for idx, ((name, url, _), dest) in enumerate(zip(DOWNLOADS, destinations))
        ]

        for future in concurrent.futures.as_completed(futures):
            future.result()

    combined_path = sources_dir / 'kaikki.org-dictionary-combined.jsonl'
    print(f'Concatenating files into {combined_path}')
    concat_files(destinations, combined_path)
    print('Done.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download and combine kaikki.org JSONL source files')
    parser.parse_args()
    main()
