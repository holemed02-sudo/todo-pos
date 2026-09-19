from pathlib import Path
import shutil, uuid
from database import BASE_DIR
BASE=BASE_DIR
IMGDIR=BASE/"assets"/"products"

def import_image(source):
    if not source: return ""
    src=Path(source)
    if not src.exists(): return ""
    IMGDIR.mkdir(parents=True,exist_ok=True)
    dst=IMGDIR/f"{uuid.uuid4().hex}{src.suffix.lower() or '.jpg'}"
    shutil.copy2(src,dst)
    return str(dst.relative_to(BASE))

def abs_image(rel):
    if not rel:return None
    p=BASE/rel
    return p if p.exists() else None
