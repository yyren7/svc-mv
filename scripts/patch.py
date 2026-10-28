"""patch.py WORKTREE SPEC.json: apply [[relative file, old text, new text], ...] to an experiment's worktree
(scripts/exp.sh). Each old text must occur exactly once, so a spec written against a line that has since changed
fails loudly instead of rendering the unpatched film."""
import json
import pathlib
import sys

w = pathlib.Path(sys.argv[1])
for rel, old, new in json.load(open(sys.argv[2], encoding="utf-8")):
    p = w / rel
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    assert n == 1, f"{rel}: {n} occurrences of {old[:60]!r}"
    p.write_text(s.replace(old, new), encoding="utf-8")
    print("patched", rel, "|", old[:50].replace("\n", " "), "->", new[:50].replace("\n", " "))
