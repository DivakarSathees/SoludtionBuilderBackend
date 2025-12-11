# import os
# import json
# from groq import Groq


# class ErrorFixerAgent:
#     """
#     AI agent that analyzes build logs and determines:
#       - the exact cause of failure
#       - which files must change
#       - full updated file contents

#     Output format:
#     {
#       "edits": [
#          {
#            "path": "src/main/java/.../TeacherServiceImpl.java",
#            "action": "update",
#            "content": "FULL UPDATED FILE CONTENT HERE"
#          }
#       ]
#     }
#     """

#     def __init__(self):
#         self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

#         self.system_prompt = """
# You are an expert senior software engineer who fixes code based on build logs.

# Your job:
# 1. Read the build error logs.
# 2. Identify the exact file(s) causing the failure.
# 3. Produce full corrected file contents.
# 4. Output ONLY JSON in this format:

# {
#   "edits": [
#     {
#       "path": "relative/path/to/file",
#       "action": "update",
#       "content": "FULL corrected file content"
#     }
#   ]
# }

# Rules:
# - Always output FULL files, not diffs.
# - Never output markdown.
# - Never explain.
# - Never leave comments in code.
# - Never add text outside JSON.
# """

#     # -----------------------------------------------------------
#     # Safe JSON extraction
#     # -----------------------------------------------------------
#     def _extract_json(self, text: str):
#         text = text.strip()

#         # Attempt direct parse
#         try:
#             return json.loads(text)
#         except:
#             pass

#         # Try substring between first { and last }
#         start = text.find("{")
#         end = text.rfind("}")

#         if start != -1 and end != -1:
#             try:
#                 return json.loads(text[start:end + 1])
#             except:
#                 return None

#         return None

#     # -----------------------------------------------------------
#     # LLM call
#     # -----------------------------------------------------------
#     def _ask_model(self, spec: str, build_logs: str, project_files: dict):
#         prompt = f"""
# PROJECT SPEC:
# {spec}

# BUILD LOGS:
# {build_logs}

# AFFECTED FILES (content included):
# {json.dumps(project_files, indent=2)}

# Your task: fix the errors by updating the affected files.
# Return ONLY JSON.
# """

#         resp = self.client.chat.completions.create(
#             model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
#             messages=[
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0,
#             max_completion_tokens=8192
#         )

#         return resp.choices[0].message.content

#     # -----------------------------------------------------------
#     # MAIN FIX METHOD
#     # -----------------------------------------------------------
#     def fix_errors(self, global_spec: str, build_logs: str, selected_files: list):
#         """
#         selected_files = [
#            { "path": "...", "content": "..." }
#         ]
#         """

#         raw = self._ask_model(
#             spec=global_spec,
#             build_logs=build_logs,
#             project_files=selected_files
#         )

#         parsed = self._extract_json(raw)

#         if parsed is None:
#             return {
#                 "edits": [],
#                 "error": "Could not parse fix JSON from model output"
#             }

#         parsed.setdefault("edits", [])
#         return parsed


# agents/error_fixer.py
import os
import json
from groq import Groq
from constants.protection import PROTECTED_DIRS, PROTECTED_FILES

class ErrorFixerAgent:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.system_prompt = f"""
You are an expert engineer who fixes build/runtime errors.

Inputs:
- project description
- summarized error block
- a set of relevant files (path + content)

Output JSON only:
{{ "edits": [ {{ "path": "...", "action":"update/create", "content":"full file" }} ] }}

Rules:
- DO NOT modify protected files or directories:
  DIRS: {PROTECTED_DIRS}
  FILES: {PROTECTED_FILES}
- If the fix would require editing a protected file, return an object with action 'skip_protected'.
- Return full file contents. No explanations.
"""
    def _extract_json(self, text):
        text = text.strip()
        try:
            return json.loads(text)
        except:
            start = text.find("{"); end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end+1])
                except:
                    return None
        return None

    def fix_errors(self, global_spec: str, build_logs: str, selected_files: list):
        prompt = f"""
PROJECT_SPEC:
{global_spec}

ERROR_BLOCK:
{build_logs}

FILES:
{json.dumps(selected_files, indent=2)}
"""
        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role":"system","content":self.system_prompt},{"role":"user","content":prompt}],
            temperature=0.0,
            max_completion_tokens=8192
        )
        raw = resp.choices[0].message.content
        parsed = self._extract_json(raw)
        if parsed is None:
            return {"edits": [], "error": "Could not parse JSON", "raw": raw}
        parsed.setdefault("edits", [])
        # Filter protected edits
        allowed = []
        blocked = []
        for e in parsed["edits"]:
            p = e.get("path", "")
            if any(p.startswith(d.rstrip("/") + "/") or p == d.rstrip("/") for d in PROTECTED_DIRS) or p in PROTECTED_FILES:
                blocked.append({"path": p, "action": "skip_protected"})
            else:
                allowed.append(e)
        return {"edits": allowed, "blocked": blocked}
