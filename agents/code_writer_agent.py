import os
import json
from groq import Groq


class CodeWriterAgent:
    """
    AI agent that writes or updates files based on:
      - global_spec (project description)
      - selected existing file contents (from scanner)
      - planner recommendations (files_to_update, files_to_create)
    """

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        # System instructions
        self.system_prompt = """
You are an expert senior software engineer.

Your job:
1. Read the project specification.
2. Read ONLY the file contents provided.
3. Read the list of files that need creation or update.
4. Produce final, complete file contents for each file.

Output ONLY JSON using this format:

{
  "edits": [
    {
      "path": "relative/path/to/file",
      "action": "create|update",
      "content": "FULL content of the file"
    }
  ]
}

Rules:
- ALWAYS output full file content (no diffs).
- NEVER explain your reasoning.
- NEVER add comments outside code.
- NEVER wrap JSON in markdown.
- If updating a file, rewrite the entire file.
- For created files, include full valid code.
- Follow best practices for the detected tech stack.
"""

    # -------------------------------
    # Safe JSON extractor
    # -------------------------------
    def _extract_json(self, text: str):
        text = text.strip()

        # 1. Try direct JSON parse
        try:
            return json.loads(text)
        except:
            pass

        # 2. Attempt to locate JSON block
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except:
                return None

        return None

    # -------------------------------
    # Model API call
    # -------------------------------
    def _call_model(self, prompt: str):
        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_completion_tokens=4096
        )
        return resp.choices[0].message.content

    # -------------------------------
    # MAIN METHOD
    # -------------------------------
    def generate_solution(self,
                          global_spec: str,
                          project_files: dict):
        """
        project_files = {
            "files_to_read": [
                { "path": "...", "content": "..." }
            ],
            "files_to_update": [...],
            "files_to_create": [...]
        }
        """

        prompt = f"""
PROJECT SPECIFICATION:
{global_spec}

EXISTING FILE CONTENTS TO READ:
{json.dumps(project_files["files_to_read"], indent=2)}

FILES REQUESTED FOR UPDATE:
{json.dumps(project_files["files_to_update"], indent=2)}

FILES REQUESTED FOR CREATION:
{json.dumps(project_files["files_to_create"], indent=2)}

IMPORTANT:
Return only JSON with the list of file edits.
"""

        raw = self._call_model(prompt)
        parsed = self._extract_json(raw)

        if parsed is None:
            return {
                "edits": [],
                "error": "Could not parse JSON from model output"
            }

        parsed.setdefault("edits", [])
        return parsed
