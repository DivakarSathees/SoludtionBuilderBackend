import os
import json
from groq import Groq
import re


class CodeWriterAgent:
    """
    AI agent that writes or updates project files using LLM.
    Now with bulletproof JSON parsing & strict formatting.
    """

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        self.system_prompt = """
You are an expert senior software engineer.

You MUST respond only with VALID JSON.
No markdown, no explanations, no comments.

Your JSON format MUST be:

{
  "edits": [
    {
      "path": "relative/path/to/file",
      "action": "create | update",
      "content": "FULL file content here"
    }
  ]
}

Rules:
- Always output FULL file contents.
- Never use backticks.
- Never output text outside JSON.
- Do not add trailing commas.
"""

    # --------------------------------------------------------
    # JSON CLEANER (removes illegal characters)
    # --------------------------------------------------------
    def _clean_json_text(self, text: str):
        # Remove Markdown code fences
        text = text.replace("```json", "").replace("```", "")

        # Remove non-breaking spaces, weird unicode
        text = text.replace("\u0000", "").replace("\ufeff", "")

        # Remove leading/trailing junk before first '{' or after last '}'
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            text = text[start:end + 1]

        # Remove trailing commas in JSON-like responses
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)

        return text.strip()

    # --------------------------------------------------------
    # Safe JSON extractor
    # --------------------------------------------------------
    def _extract_json(self, text: str):
        cleaned = self._clean_json_text(text)

        try:
            return json.loads(cleaned)
        except Exception as e:
            print("\n❌ JSON PARSE ERROR:", e)
            print("RAW OUTPUT:\n", text)
            print("CLEANED OUTPUT:\n", cleaned)
            return None

    # --------------------------------------------------------
    # LLM CALL
    # --------------------------------------------------------
    def _call_model(self, prompt: str):
        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_completion_tokens=8192,
        )

        return resp.choices[0].message.content

    # --------------------------------------------------------
    # MAIN API
    # --------------------------------------------------------
    def generate_solution(self, global_spec: str, project_files: dict):
        """
        Generates updates based on planner output + existing files.
        """

        prompt = f"""
PROJECT SPECIFICATION:
{global_spec}

EXISTING SELECTED FILE CONTENTS:
{json.dumps(project_files["files_to_read"], indent=2)}

FILES THAT MUST BE UPDATED:
{json.dumps(project_files["files_to_update"], indent=2)}

FILES THAT MUST BE CREATED:
{json.dumps(project_files["files_to_create"], indent=2)}

IMPORTANT: Output ONLY JSON.
"""

        raw = self._call_model(prompt)
        parsed = self._extract_json(raw)

        if parsed is None:
            return {
                "edits": [],
                "error": "Invalid JSON from model. Check logs."
            }

        parsed.setdefault("edits", [])
        return parsed
