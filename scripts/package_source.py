from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
destination = root.parent / 'KedaiFlow-local-source.zip'
excluded = {'.git','.venv','.local','node_modules','.next','__pycache__','.pytest_cache','private_media','test-results','playwright-report'}
with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if not path.is_file() or excluded.intersection(relative.parts):
            continue
        if path.name == '.env' or path.name.endswith(('.db','.db-shm','.db-wal','.pyc','.tsbuildinfo')):
            continue
        archive.write(path, Path('kedaiflow') / relative)
print(f'Source-only package: {destination.name}')
