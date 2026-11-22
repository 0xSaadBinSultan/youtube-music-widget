"""Collect upstream notices and installed versions for redistributable builds."""
from importlib import metadata
import json
from pathlib import Path
import shutil
import sys


def main():
    source = Path(__file__).resolve().parent
    output = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist') / 'third-party-licenses'
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / 'licenses', output / 'Qt', dirs_exist_ok=True)
    shutil.copy2(source / 'THIRD_PARTY.md', output / 'THIRD_PARTY.md')
    versions = []
    for package in metadata.distributions():
        name = package.metadata.get('Name', 'unknown')
        safe_name = ''.join(c for c in name if c.isalnum() or c in '-_.')
        versions.append({'name': name, 'version': package.version})
        for entry in package.files or []:
            if (entry.name.lower().startswith(('license', 'copying', 'notice'))
                    or 'licenses' in (part.lower() for part in entry.parts)):
                src = Path(package.locate_file(entry))
                if not src.is_file():
                    continue
                # Preserve upstream paths so similarly named notices do not collide.
                parts = [part for part in entry.parts if part not in ('..', '.', '/')]
                dest = output / safe_name / Path(*parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
    (output / 'versions.json').write_text(json.dumps(sorted(versions, key=lambda p: p['name'].lower()),
                                                   indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
