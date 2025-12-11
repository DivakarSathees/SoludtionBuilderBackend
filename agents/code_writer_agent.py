
# # agents/code_writer_agent.py
# import os
# import json
# from groq import Groq
# from constants.protection import PROTECTED_DIRS, PROTECTED_FILES

# class CodeWriterAgent:
#     def __init__(self):
#         self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
#         self.system_prompt = f"""
# You are an expert software engineer.

# You will be given:
# - project spec
# - selected existing file contents
# - a list of files to update/create

# Return JSON only:
# {{ "edits": [ {{ "path": "relative/path", "action":"create|update", "content": "full file content" }} ] }}

# IMPORTANT:
# - The following files and directories are PROTECTED and MUST NOT be edited:
#   DIRS: {PROTECTED_DIRS}
#   FILES: {PROTECTED_FILES}
# - If a requested change touches any protected resource, DO NOT modify it.
#   Instead return an edit with action 'skip_protected' for that path.
# - Output full file contents (no diffs), no explanations, no markdown.
# """

#     def _extract_json(self, text: str):
#         text = text.strip()
#         try:
#             return json.loads(text)
#         except:
#             start = text.find("{"); end = text.rfind("}")
#             if start != -1 and end != -1:
#                 try:
#                     return json.loads(text[start:end+1])
#                 except:
#                     return None
#         return None

#     def _call_model(self, prompt: str):
#         resp = self.client.chat.completions.create(
#             model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
#             messages=[{"role":"system","content":self.system_prompt},{"role":"user","content":prompt}],
#             temperature=0.0,
#             max_completion_tokens=4096
#         )
#         return resp.choices[0].message.content

#     def generate_solution(self, global_spec: str, project_files: dict):
#         """
#         project_files:
#           - files_to_read: [{path, content}]
#           - files_to_update: [...]
#           - files_to_create: [...]
#         """
#         prompt = f"""
# PROJECT_SPEC:
# {global_spec}

# FILES_TO_READ:
# {json.dumps(project_files.get("files_to_read", []), indent=2)}

# FILES_TO_UPDATE:
# {json.dumps(project_files.get("files_to_update", []), indent=2)}

# FILES_TO_CREATE:
# {json.dumps(project_files.get("files_to_create", []), indent=2)}
# """
#         raw = self._call_model(prompt)
#         print("\n--- RAW MODEL OUTPUT ---\n", raw)
#         parsed = self._extract_json(raw)
#         if parsed is None:
#             return {"edits": [], "error": "Could not parse JSON from model output", "raw": raw}
#         parsed.setdefault("edits", [])
#         # Respect protected: model was instructed, but we also double-check here
#         safe_edits = []
#         blocked = []
#         for e in parsed["edits"]:
#             p = e.get("path", "")
#             if any(p.startswith(d.rstrip("/") + "/") or p == d.rstrip("/") for d in PROTECTED_DIRS) or p in PROTECTED_FILES:
#                 blocked.append({"path": p, "action": "skip_protected"})
#             else:
#                 safe_edits.append(e)
#         return {"edits": safe_edits, "blocked": blocked}


# agents/code_writer_agent.py
import os
import json
from groq import Groq
from constants.protection import PROTECTED_DIRS, PROTECTED_FILES
from utils.context_selector import select_relevant_context

class CodeWriterAgent:
    """
    Chunked, context-aware Code Writer.
    - Generates one file per LLM call
    - Provides relevant trimmed previous-file context to preserve consistency
    - Enforces protected-file rules
    """

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.system_prompt = f"""
You are an expert senior software engineer.

You will receive:
- Project specification (requirements).
- A single target file path to CREATE or UPDATE.
- A small set of RELATED files (trimmed), previously generated or selected by the planner.

Return STRICT JSON only:

{{ "path": "<target path>", "action": "create|update", "content": "<full file content>" }}

Rules:
- Output only the JSON object (no markdown, no explanation).
- NEVER modify protected files or directories.
  Protected DIRS: {PROTECTED_DIRS}
  Protected FILES: {PROTECTED_FILES}
- The 'content' must be the COMPLETE file text (full source file).
- Use consistent names, method signatures, imports, and packages consistent with the provided RELATED files.
- If you cannot modify because the target is protected, return:
  {{ "path": "<target path>", "action": "skip_protected", "content": "" }}
"""

    def _extract_json(self, text: str):
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            # Fallback: extract first {...}
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    return None
            return None

    def _call_model(self, prompt: str, max_tokens: int = 4096):
        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role": "system", "content": self.system_prompt},
                      {"role": "user", "content": prompt}],
            temperature=0.0,
            max_completion_tokens=max_tokens
        )
        # Groq response model returns choices[0].message.content
        return resp.choices[0].message.content

    # -------------------------
    # Generate single file (one LLM call)
    # -------------------------
    def generate_file(self, global_spec: str, target_path: str, action: str,
                      related_files: list, project_files: dict):
        """
        related_files: list of {"path":..., "content":...} (trimmed)
        action: "create" or "update"
        """
        # Respect protected files
        normalized = target_path.replace("\\", "/")
        for d in PROTECTED_DIRS:
            if normalized == d.rstrip("/") or normalized.startswith(d.rstrip("/") + "/"):
                return {"path": target_path, "action": "skip_protected", "content": ""}

        if normalized in PROTECTED_FILES:
            return {"path": target_path, "action": "skip_protected", "content": ""}

        prompt = f"""
PROJECT SPEC:
{global_spec}

PROJECT FILE PLAN (paths only):
{json.dumps({
    "files_to_read": project_files.get("files_to_read", []),
    "files_to_update": project_files.get("files_to_update", []),
    "files_to_create": project_files.get("files_to_create", []),
}, indent=2)}

TARGET:
path: {target_path}
action: {action}

RELATED_FILES (trimmed):
{json.dumps(related_files, indent=2)}


Write the COMPLETE content of the TARGET file. Return only JSON as described.
"""

        raw = self._call_model(prompt)
        parsed = self._extract_json(raw)
        if parsed is None:
            return {"path": target_path, "action": "error", "content": "", "raw": raw}

        # Make sure parsed contains required fields
        parsed.setdefault("path", target_path)
        parsed.setdefault("action", action)
        parsed.setdefault("content", "")

        return parsed

    # -------------------------
    # Generate all files chunked with context awareness
    # -------------------------
    def generate_solution(self, global_spec: str, project_files: dict, max_context_files: int = 5):
        """
        project_files:
           - files_to_read: [{path, content}]
           - files_to_update: [path, ...]
           - files_to_create: [path, ...]
        Approach:
           - Keep an in-memory list of generated_files (path+content)
           - For each target file, select a small relevant context using select_relevant_context
           - Call generate_file with that small context
        """
        edits = []
        read_map = {f["path"]: f["content"] for f in project_files.get("files_to_read", [])}
        read_files = [{"path": p, "content": c} for p, c in read_map.items()]

        generated_files = []  # keeps previous successful generations: {"path","content"}

        # Order: updates first (so we can modify existing files), then creates
        for path in project_files.get("files_to_update", []):
            # Build small relevant context
            context = select_relevant_context(path, generated_files, read_files, max_files=max_context_files)
            result = self.generate_file(global_spec, path, "update", context, project_files)
            edits.append(result)
            print(f"Generated file: {path} with action: {result.get('action')}")
            # If successful create/update, store in generated_files to provide context for later files
            if result.get("action") in ("create", "update") and result.get("content"):
                generated_files.append({"path": path, "content": result["content"]})

        for path in project_files.get("files_to_create", []):
            context = select_relevant_context(path, generated_files, read_files, max_files=max_context_files)
            result = self.generate_file(global_spec, path, "create", context, project_files)
            edits.append(result)
            print(f"Generated file: {path} with action: {result.get('action')}")
            if result.get("action") in ("create", "update") and result.get("content"):
                generated_files.append({"path": path, "content": result["content"]})

        return {"edits": edits}
