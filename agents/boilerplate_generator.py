import os
import json
from groq import Groq


class BoilerplateGeneratorAgent:
    """
    AI-powered boilerplate generator.
    Generates initial folder structure and starter files for the selected stack.
    """

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        self.system_prompt = """
You are an expert software project initializer.

Your job:
1. Read the selected tech stack + detailed project description.
2. Generate a COMPLETE boilerplate project with correct folder structure.
3. Output ONLY JSON with this exact format:

{
  "files": [
    {
      "path": "relative/path/to/file.ext",
      "content": "file content here"
    }
  ],
  "commands": [
     "build or init commands here"
  ]
}

Rules:
- DO NOT write explanations.
- DO NOT include markdown.
- DO NOT wrap JSON in code fences.
- Keep boilerplate minimal but valid.
- Directory paths must use UNIX format (/).
- 'content' must be valid file content.
- commands must be shell commands runnable in the Docker container.
"""

    # ----------------------------------------------------------------------
    # JSON extraction (safe for Python 3.13 – no recursive regex)
    # ----------------------------------------------------------------------
    def _extract_json(self, text: str):
        text = text.strip()

        # Try direct JSON
        try:
            return json.loads(text)
        except:
            pass

        # Extract between first '{' and last '}'
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except:
                return None

        return None

    # ----------------------------------------------------------------------
    # Call Groq LLM
    # ----------------------------------------------------------------------
    def _call_model(self, final_prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": final_prompt}
            ],
            temperature=0.0,
            max_completion_tokens=4096,
        )

        try:
            return resp.choices[0].message.content
            
        except:
            return str(resp)

    # ----------------------------------------------------------------------
    # MAIN METHOD: Generate boilerplate JSON
    # ----------------------------------------------------------------------
    def generate_boilerplate(self, stack: dict, global_spec: str) -> dict:
        """
        stack:
          - language
          - framework
          - docker_image
          - build_tool
          - project_type
        global_spec: The complete user project description
        """

        prompt = f"""
Generate boilerplate for this project.

STACK:
{json.dumps(stack, indent=2)}

DESCRIPTION:
{global_spec}
"""

        raw = self._call_model(prompt)
        parsed = self._extract_json(raw)

        if parsed is None:
            return {
                "files": [],
                "commands": [],
                "error": "Model output could not be parsed."
            }

        parsed.setdefault("files", [])
        parsed.setdefault("commands", [])

        return parsed
