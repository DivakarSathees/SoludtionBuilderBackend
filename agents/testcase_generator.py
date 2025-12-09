# agents/testcase_generator.py
import os
import json
from groq import Groq


class TestcaseGeneratorAgent:
    """
    Generates end-to-end test files based on:
      - the project description
      - the actual solution files (code)
    Writes test files JSON as {"files": [{"path":..., "content":...}]}
    """

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        self.system_prompt = """
You are an expert QA automation engineer.

Given the project description and the full solution code, produce end-to-end test files
suitable for the project's language/framework (JUnit/Test for Java, PyTest for Python,
Jest for Node, xUnit for .NET). The tests should be realistic end-to-end test cases
that exercise controllers/services based on the actual code.

Return ONLY JSON in this format:
{
  "files": [
    { "path": "src/test/...", "content": "..." }
  ]
}
"""

    def _extract_json(self, text: str):
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

    def generate_tests(self, spec: str, solution_files: list, stack: dict):
        # bundle code small; be careful with huge payloads in practice (you can trim files not needed)
        print("Generating tests for stack:", solution_files)
        # code_bundle = "\n\n".join(f"FILE: {f['path']}\n{f['content']}" for f in solution_files)
        code_bundle = "\n\n".join(
            f"FILE {f['path']}:\n{f['content']}"
            for f in solution_files
        )
        prompt = f"PROJECT DESCRIPTION:\n{spec}\n\nSOLUTION FILES:\n{code_bundle}\n\nGenerate E2E test files (compile-ready). Output only JSON as {json.dumps({'files':[]})}."
        print("Generating test cases with prompt size:", len(prompt))
        print(prompt)
        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role":"system","content":self.system_prompt},{"role":"user","content":prompt}],
            temperature=0.0,
            max_completion_tokens=8192
        )
        raw = resp.choices[0].message.content
        parsed = self._extract_json(raw)
        if parsed is None:
            return {"files": []}
        parsed.setdefault("files", [])
        return parsed
