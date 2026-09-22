"""Run on the VPS as root: consistent DB snapshot plus photos, keep seven days."""
import os,sqlite3,tarfile,tempfile,time
from pathlib import Path
os.umask(0o077)
source=Path('/var/lib/homefood');destination=Path('/var/backups/homefood');destination.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    db=sqlite3.connect(source/'homefood.sqlite');snapshot=sqlite3.connect(Path(temp)/'homefood.sqlite')
    try:db.backup(snapshot)
    finally:db.close();snapshot.close()
    with tarfile.open(destination/(time.strftime('%Y-%m-%d-%H%M%S')+'.tar.gz'),'w:gz') as archive:
        archive.add(Path(temp)/'homefood.sqlite',arcname='homefood.sqlite');archive.add(source/'photos',arcname='photos')
for file in destination.glob('*.tar.gz'):
    if file.stat().st_mtime<time.time()-7*86400:file.unlink()
