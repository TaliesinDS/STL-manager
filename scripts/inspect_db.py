"""Simple DB inspector: prints counts and a few sample rows for Variant, File, Archive, Collection, Character.
"""
from pathlib import Path
import sys

proj_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(proj_root))

from db.session import get_session
from db.models import Variant, File, Archive, Collection, Character


def inspect():
    with get_session() as session:
        v_count = session.query(Variant).count()
        f_count = session.query(File).count()
        a_count = session.query(Archive).count()
        c_count = session.query(Collection).count()
        ch_count = session.query(Character).count()

        print(f"Variants: {v_count}")
        print(f"Files:    {f_count}")
        print(f"Archives: {a_count}")
        print(f"Collections: {c_count}")
        print(f"Characters: {ch_count}\n")

        print("Sample Variants:")
        for v in session.query(Variant).limit(5):
            print(f"- id={v.id} rel_path={v.rel_path} filename={v.filename} files={len(v.files)}")

        print("\nSample Files:")
        for f in session.query(File).limit(5):
            print(f"- id={f.id} rel_path={f.rel_path} filename={f.filename} hash={f.hash_sha256}")


if __name__ == '__main__':
    inspect()
