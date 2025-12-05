import os
import json
from groq import Groq


class FilePlannerAgent:
    """
    AI agent that examines the project specification + file list (paths only)
    and decides:
      - Which files must be read
      - Which existing files need updates
      - Which new files must be created
    """

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        self.system_prompt = """
You are an expert senior software engineer and system planner.

Your task:
1. Read the project description.
2. Read ONLY the file structure (paths, NOT file content).
3. Decide what files the next agent must read, update, or create.

OUTPUT STRICT JSON ONLY:

{
  "files_to_read": ["path1", "path2"],
  "files_to_update": ["path3", "path4"],
  "files_to_create": ["path5", "path6"]
}

Rules:
- Only include files needed to implement and complete the requested features.
- If a file already exists but likely incomplete → put it in "files_to_read".
- If a file needs major changes → put it in "files_to_update".
- If a required file is missing → put it in "files_to_create".
- Do NOT include file contents.
- Do NOT include explanations.
- Never wrap JSON in markdown code fences.
"""

    def _extract_json(self, text: str):
        text = text.strip()

        try:
            return json.loads(text)
        except:
            pass

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except:
                return None

        return None

    def _call_model(self, user_prompt: str):
        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_completion_tokens=2048
        )

        return resp.choices[0].message.content

    def plan(self, global_spec: str, file_list: list):
        """
        file_list: ["pom.xml", "src/main/java/.../Teacher.java", ...]
        """

        user_prompt = f"""
PROJECT SPECIFICATION:
{global_spec}

PROJECT FILE STRUCTURE:
{json.dumps(file_list, indent=2)}
"""

        raw = self._call_model(user_prompt)
        parsed = self._extract_json(raw)

        if parsed is None:
            return {
                "files_to_read": [],
                "files_to_update": [],
                "files_to_create": [],
                "error": "Could not parse JSON"
            }

        parsed.setdefault("files_to_read", [])
        parsed.setdefault("files_to_update", [])
        parsed.setdefault("files_to_create", [])

        return parsed
