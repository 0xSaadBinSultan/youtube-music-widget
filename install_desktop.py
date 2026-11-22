#!/usr/bin/env python3
"""Create a project-local venv and optionally start the portable desktop app."""
import argparse
from pathlib import Path
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    env = root / '.venv'
    python = env / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(env)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r',
                    str(root / 'requirements-desktop.txt')], check=True)
    if args.run:
        return subprocess.call([str(python), str(root / 'desktop.py')] +
                               (['--demo'] if args.demo else []), cwd=root)
    print('Installed. Start with: ' + str(python) + ' desktop.py')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
