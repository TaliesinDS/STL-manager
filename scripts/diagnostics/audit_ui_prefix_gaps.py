import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

GENERIC_VARIANT_NAMES = {
    'bodies','body','heads','head','arms','arm','legs','leg','torsos','torso',
    'weapons','weapon','bits','accessories','poses','pose','helmets','helmet',
    'cloaks','cloak','shields','shield','spears','spear','swords','sword','backpacks','backpack',
    'hand','hands','flamer','flamers'
}
BUCKET_CONNECTORS = {"and", "&", "with"}
BUCKET_PACKAGING = {"presupported", "supported", "unsupported"}


def clean_words(text: str) -> List[str]:
    text = (text or '').lower()
    # split on non-letters, keep simple tokens
    toks = re.split(r"[^a-z]+", text)
    return [t for t in toks if t]


def is_bucket_phrase(toks: List[str]) -> bool:
    nouns = 0
    for t in toks:
        if t in GENERIC_VARIANT_NAMES:
            nouns += 1
            continue
        if (t in BUCKET_CONNECTORS) or (t in BUCKET_PACKAGING):
            continue
        return False
    return nouns >= 1


def audit(file_path: Path) -> Dict[str, Any]:
    data = json.loads(file_path.read_text(encoding='utf-8'))
    proposals = data.get('proposals', [])
    issues: List[Dict[str, Any]] = []
    for p in proposals:
        ch = p.get('changes', {}) or {}
        label = (ch.get('ui_display_en') or '').strip()
        if not label:
            continue
        # Skip already-prefixed labels
        if ':' in label:
            continue
        toks = clean_words(label)
        if not toks:
            continue
        if is_bucket_phrase(toks):
            issues.append({
                'variant_id': p.get('variant_id'),
                'rel_path': p.get('rel_path'),
                'label': label
            })
        elif all(t in GENERIC_VARIANT_NAMES for t in toks):
            issues.append({
                'variant_id': p.get('variant_id'),
                'rel_path': p.get('rel_path'),
                'label': label
            })
    return {
        'report': str(file_path),
        'total': len(proposals),
        'issues_found': len(issues),
        'issues': issues,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True, help='Input full tabletop JSON report path')
    ap.add_argument('--out', dest='out', required=True, help='Output audit JSON path')
    args = ap.parse_args()
    inp = Path(args.inp)
    out = Path(args.out)
    res = audit(inp)
    out.write_text(json.dumps(res, indent=2), encoding='utf-8')
    print(f"Wrote audit to: {out}")
    print(f"Issues found: {res['issues_found']} / {res['total']}")


if __name__ == '__main__':
    main()
