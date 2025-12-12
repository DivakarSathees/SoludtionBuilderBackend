import datetime
import os
from groq import Groq

class GroqModelClient:
    def __init__(self, model: str = None):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        # default model can be overridden via env
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    def chat(self, prompt: str, max_tokens: int = 1500) -> str:
        # log the prompt into code write prompt.txt
        with open("code_write_prompt.txt", "a") as f:
                # Add a separator and timestamp for clarity in the log file
                f.write("--- Start Prompt ---\n")
                # Log the prompt itself
                f.write(f"Prompt: {prompt}\n")
                f.write(f"Max Tokens: {max_tokens}\n")
                f.write("--- End Prompt ---\n\n")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens,
            temperature=0
        )
        return response.choices[0].message.content