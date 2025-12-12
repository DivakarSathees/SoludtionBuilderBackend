# import os
# import json
# from groq import Groq


# class LogSummarizerAgent:
#     """
#     Extracts only the relevant failure sections from huge build logs.
#     """

#     def __init__(self):
#         self.ai = Groq(api_key=os.getenv("GROQ_API_KEY"))

#         self.system_prompt = """
# You are an expert log analyst.

# Your task:
# - Read massive build logs.
# - Extract only the SPECIFIC error-causing section.
# - Keep the output short and focused.
# - Include file names, line numbers, and exception messages.
# - Output ONLY JSON:

# {
#   "error_summary": "a short description",
#   "error_block": "the smallest block of logs that shows the actual failure"
# }
# """

#     def summarize(self, logs: str):
#         # write log to file for debugging
#         with open("build_logs.txt", "w") as f:
#             f.write(logs)
#         prompt = f"""
# RAW BUILD LOGS:
# {logs}

# Extract only the failure-causing portion.
# """

#         resp = self.ai.chat.completions.create(
#             model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
#             messages=[
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0,
#             max_completion_tokens=4096
#         )

#         text = resp.choices[0].message.content.strip()

#         try:
#             start = text.find("{")
#             end = text.rfind("}")
#             return json.loads(text[start:end+1])
#         except:
#             return {
#                 "error_summary": "Could not parse summary",
#                 "error_block": logs[-1000:]  # fallback to last lines
#             }


import os
import json
from groq import Groq
import re


class LogSummarizerAgent:
    """
    Safe, chunked log summarizer.
    Extracts relevant failure sections from very large build logs.
    """

    def __init__(self):
        self.ai = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

        self.system_prompt = """
You are an expert build-log analyst.

Your tasks:
1. Identify the REAL failure cause.
2. Extract ONLY the smallest block of logs showing:
   - file names
   - line numbers
   - the actual error / exception
3. Output STRICT JSON:

{
  "error_summary": "<short summary>",
  "error_block": "<minimal log block>"
}
"""

    # ------------------------------------------------------------
    # 1. Local prefiltering (very important)
    # ------------------------------------------------------------
    def _extract_error_candidates(self, logs: str) -> str:
        lines = logs.splitlines()

        keywords = [
            "error", "Error", "ERROR", "Exception", "Traceback",
            "failed", "FAIL", "fatal", "compilation", "undefined", "not found"
        ]

        candidates = []
        for i, line in enumerate(lines):
            if any(k in line for k in keywords):
                # capture ~20 lines before and after
                start = max(i - 20, 0)
                end = min(i + 20, len(lines))
                block = "\n".join(lines[start:end])
                candidates.append(block)

        # fallback if nothing detected
        if not candidates:
            return "\n".join(lines[-300:])

        # concatenate
        joined = "\n\n--- BLOCK ---\n\n".join(candidates)

        # limit size to ~50k chars
        return joined[-50000:]

    # ------------------------------------------------------------
    # 2. Chunk a large text safely
    # ------------------------------------------------------------
    def _chunk(self, text: str, size: int = 12000):
        return [text[i:i + size] for i in range(0, len(text), size)]

    # ------------------------------------------------------------
    # 3. Summarize chunks
    # ------------------------------------------------------------
    def _summarize_chunk(self, chunk: str) -> dict:
        prompt = f"""
Below is a segment of filtered build logs.
Extract ONLY the smallest log block that contains the real failure.

LOG CHUNK:
{chunk}
"""
        with open("log_summarizer_prompt.txt", "a") as f:
            f.write("--- New Chunk Prompt ---\n")
            f.write(prompt)
            f.write("\n--- End Chunk Prompt ---\n\n")

        resp = self.ai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_completion_tokens=2048
        )

        text = resp.choices[0].message.content

        # Extract JSON safely
        try:
            start = text.index("{")
            end = text.rindex("}")
            return json.loads(text[start:end + 1])
        except:
            return {
                "error_summary": "Chunk parse failed",
                "error_block": chunk[-5000:]
            }

    # ------------------------------------------------------------
    # MAIN PUBLIC METHOD
    # ------------------------------------------------------------
    def summarize(self, logs: str):
        # 1) Pre-save full logs for debugging
        with open("build_logs.txt", "w", encoding="utf-8") as f:
            f.write(logs)

        # 2) Local filtering (critical)
        filtered = self._extract_error_candidates(logs)

        # 3) Chunk if needed
        chunks = self._chunk(filtered)

        # 4) Summarize each chunk
        chunk_summaries = [self._summarize_chunk(c) for c in chunks]

        # 5) Select the best block: choose shortest error_block
        best = min(chunk_summaries, key=lambda x: len(x["error_block"]))

        return best
