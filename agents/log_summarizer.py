import os
import json
from groq import Groq


class LogSummarizerAgent:
    """
    Extracts only the relevant failure sections from huge build logs.
    """

    def __init__(self):
        self.ai = Groq(api_key=os.getenv("GROQ_API_KEY"))

        self.system_prompt = """
You are an expert log analyst.

Your task:
- Read massive build logs.
- Extract only the SPECIFIC error-causing section.
- Keep the output short and focused.
- Include file names, line numbers, and exception messages.
- Output ONLY JSON:

{
  "error_summary": "a short description",
  "error_block": "the smallest block of logs that shows the actual failure"
}
"""

    def summarize(self, logs: str):
        prompt = f"""
RAW BUILD LOGS:
{logs}

Extract only the failure-causing portion.
"""

        resp = self.ai.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_completion_tokens=4096
        )

        text = resp.choices[0].message.content.strip()

        try:
            start = text.find("{")
            end = text.rfind("}")
            return json.loads(text[start:end+1])
        except:
            return {
                "error_summary": "Could not parse summary",
                "error_block": logs[-1000:]  # fallback to last lines
            }
