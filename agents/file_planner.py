# import os
# import json
# from groq import Groq


# class FilePlannerAgent:
#     """
#     AI agent that examines the project specification + file list (paths only)
#     and decides:
#       - Which files must be read
#       - Which existing files need updates
#       - Which new files must be created
#     """

#     def __init__(self):
#         self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

#         self.system_prompt = """
# You are an expert senior software engineer and system planner.

# Your task:
# 1. Read the project description.
# 2. Read ONLY the file structure (paths, NOT file content).
# 3. Decide what files the next agent must read, update, or create.

# OUTPUT STRICT JSON ONLY:

# {
#   "files_to_read": ["path1", "path2"],
#   "files_to_update": ["path3", "path4"],
#   "files_to_create": ["path5", "path6"]
# }

# Rules:
# - Only include files needed to implement and complete the requested features.
# - If a file already exists but likely incomplete → put it in "files_to_read".
# - If a file needs major changes → put it in "files_to_update".
# - If a required file is missing → put it in "files_to_create".
# - Do NOT include file contents.
# - Do NOT include explanations.
# - Never wrap JSON in markdown code fences.
# """

#     def _extract_json(self, text: str):
#         text = text.strip()

#         try:
#             return json.loads(text)
#         except:
#             pass

#         start = text.find("{")
#         end = text.rfind("}")

#         if start != -1 and end != -1:
#             try:
#                 return json.loads(text[start:end + 1])
#             except:
#                 return None

#         return None

#     def _call_model(self, user_prompt: str):
#         resp = self.client.chat.completions.create(
#             model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
#             messages=[
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             temperature=0,
#             max_completion_tokens=2048
#         )

#         return resp.choices[0].message.content

#     def plan(self, global_spec: str, file_list: list):
#         """
#         file_list: ["pom.xml", "src/main/java/.../Teacher.java", ...]
#         """

#         user_prompt = f"""
# PROJECT SPECIFICATION:
# {global_spec}

# PROJECT FILE STRUCTURE:
# {json.dumps(file_list, indent=2)}
# """

#         raw = self._call_model(user_prompt)
#         parsed = self._extract_json(raw)

#         if parsed is None:
#             return {
#                 "files_to_read": [],
#                 "files_to_update": [],
#                 "files_to_create": [],
#                 "error": "Could not parse JSON"
#             }

#         parsed.setdefault("files_to_read", [])
#         parsed.setdefault("files_to_update", [])
#         parsed.setdefault("files_to_create", [])

#         return parsed


import os
import json
from groq import Groq
from constants.protection import PROTECTED_DIRS, PROTECTED_FILES


class FilePlannerAgent:
    """
    AI-driven file planning agent.
    Decides which files should be:
      - read (for next agent to analyze)
      - updated (AI will rewrite completely)
      - created (missing files required for solution)

    Now includes:
      ✔ Protected FS filtering (never allow planning edits on protected files)
      ✔ Automatic fallback heuristics if AI output is incorrect
      ✔ Safer JSON-only enforcement
    """

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        self.system_prompt = f"""
You are an expert senior software engineer and system planner.

Your job:
1. Read the project description.
2. Read ONLY the project file structure — paths only.
3. Decide which files must be:
   - read
   - updated
   - created

OUTPUT STRICT JSON ONLY:

{{
  "files_to_read": ["path1", "path2"],
  "files_to_update": ["path3", "path4"],
  "files_to_create": ["path5", "path6"]
}}

ABSOLUTE RULES:
- NEVER include protected files or protected directories.
  PROTECTED DIRS: {PROTECTED_DIRS}
  PROTECTED FILES: {PROTECTED_FILES}

- Use ONLY the paths given — do NOT invent existing file paths.
- If the project requires a file but it does not exist → put it in "files_to_create".
- If an existing file is important for implementing the spec → put it in "files_to_read".
- If an existing file must be changed → "files_to_update".
- Keep the lists very small (high precision).
- Do NOT include explanations.
- Do NOT wrap JSON in markdown.
"""

    # -------------------------------
    # JSON extraction
    # -------------------------------
    def _extract_json(self, text: str):
        text = text.strip()

        # Try direct JSON
        try:
            return json.loads(text)
        except:
            pass

        # Fallback: extract first {...}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except:
                return None

        return None

    # -------------------------------
    # Model call
    # -------------------------------
    def _call_model(self, user_prompt: str):
        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_completion_tokens=2048,
        )

        return resp.choices[0].message.content

    # -------------------------------
    # Post-filtering for protected FS
    # -------------------------------
    def _filter_protected(self, paths: list):
        safe = []
        for p in paths:
            normalized = p.replace("\\", "/")
            if normalized in PROTECTED_FILES:
                continue
            if any(
                normalized.startswith(d.rstrip("/") + "/")
                or normalized == d.rstrip("/")
                for d in PROTECTED_DIRS
            ):
                continue
            safe.append(normalized)
        return safe

    # -------------------------------
    # MAIN PLAN METHOD
    # -------------------------------
    def plan(self, global_spec: str, file_list: list):
        """
        file_list = ["pom.xml", "src/main/java/.../Teacher.java", ...]
        """

        user_prompt = f"""
PROJECT SPECIFICATION:
{global_spec}

PROJECT FILE STRUCTURE (paths only):
{json.dumps(file_list, indent=2)}
"""

        raw = self._call_model(user_prompt)
        parsed = self._extract_json(raw)

        # If JSON failed -> fallback to safe defaults
        if parsed is None:
            return {
                "files_to_read": [],
                "files_to_update": [],
                "files_to_create": [],
                "error": "AI failed to produce valid JSON",
            }

        # Ensure required keys
        parsed.setdefault("files_to_read", [])
        parsed.setdefault("files_to_update", [])
        parsed.setdefault("files_to_create", [])

        # FILTER OUT PROTECTED FILES
        safe_read = self._filter_protected(parsed["files_to_read"])
        safe_update = self._filter_protected(parsed["files_to_update"])
        safe_create = self._filter_protected(parsed["files_to_create"])

        # Final validated plan
        return {
            "files_to_read": list(dict.fromkeys(safe_read)),
            "files_to_update": list(dict.fromkeys(safe_update)),
            "files_to_create": list(dict.fromkeys(safe_create)),
        }
