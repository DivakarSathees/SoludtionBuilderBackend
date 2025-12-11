# utils/context_selector.py
from typing import List, Dict
import os
import re

def trim_content_for_context(content: str, max_lines: int = 200) -> str:
    """
    Reduce a file's content to the essential parts for context:
    - remove comments
    - remove import/package lines
    - drop long method bodies
    - keep declarations, signatures, annotations
    """
    lines = content.splitlines()
    out = []
    for line in lines:
        s = line.strip()
        # skip comments
        if s.startswith("//") or s.startswith("/*") or s.startswith("*"):
            continue
        # skip import/package lines
        if s.startswith("import ") or s.startswith("package "):
            continue
        # skip long blank runs
        if s == "":
            continue
        out.append(line)
        if len(out) >= max_lines:
            break

    # additional light normalization: collapse multiple spaces
    cleaned = "\n".join(out)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned


def select_relevant_context(target_path: str,
                            generated_files: List[Dict[str, str]],
                            read_files: List[Dict[str, str]],
                            max_files: int = 5) -> List[Dict[str, str]]:
    """
    Heuristic selection of small set of relevant files to pass to LLM.
    Priority:
      1) Files from same directory as target
      2) Files whose basename shares keywords with target (entity/service names)
      3) Explicit read_files matching module keywords
      4) Then fall back to a small subset of generated_files
    Returns trimmed file dicts: {"path":..., "content":...}
    """

    def basename_no_ext(p: str):
        return os.path.splitext(os.path.basename(p))[0].lower()

    target_base = basename_no_ext(target_path)
    target_dir = os.path.dirname(target_path)

    candidates = []

    # 1) same directory files (highest priority)
    for f in generated_files:
        if os.path.dirname(f["path"]) == target_dir:
            candidates.append(f)

    # 2) name-similar files from generated_files
    for f in generated_files:
        if f in candidates:
            continue
        base = basename_no_ext(f["path"])
        # match if shares prefix or common token with target_base
        if target_base and (target_base in base or base in target_base):
            candidates.append(f)

    # 3) match read_files by keyword
    for f in read_files:
        if f in candidates:
            continue
        base = basename_no_ext(f["path"])
        if target_base and (target_base in base or base in target_base):
            candidates.append(f)

    # 4) if still small, add some read_files from same module (path contains target keywords)
    for f in read_files:
        if f in candidates:
            continue
        if target_base and target_base in f["path"].lower():
            candidates.append(f)

    # 5) fallback: include first few generated files
    for f in generated_files:
        if f in candidates:
            continue
        candidates.append(f)
        if len(candidates) >= max_files:
            break

    # Final trimming & cap
    trimmed = []
    seen = set()
    for f in candidates:
        if f["path"] in seen:
            continue
        seen.add(f["path"])
        trimmed.append({
            "path": f["path"],
            "content": trim_content_for_context(f.get("content", "")),
        })
        if len(trimmed) >= max_files:
            break

    # Ensure we also include up to 2 of the original read_files not already included (small)
    idx = 0
    for rf in read_files:
        if idx >= 2:
            break
        if rf["path"] in seen:
            continue
        trimmed.append({
            "path": rf["path"],
            "content": trim_content_for_context(rf.get("content", ""))
        })
        seen.add(rf["path"])
        idx += 1

    return trimmed
