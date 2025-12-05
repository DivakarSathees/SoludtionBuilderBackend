import os
import json
from typing import Optional, Dict
from groq import Groq
from dotenv import load_dotenv
load_dotenv()



class StackSelectorAgent:
    """
    AI-powered stack selector agent.
    It reads a natural-language project description and returns:

    {
        "need_clarification": boolean,
        "question": "...",
        "language": "...",
        "framework": "...",
        "docker_image": "...",
        "build_tool": "...",
        "project_type": "...",
        "reason": "..."
    }

    If ambiguous → AI will ask a question.
    """

    def __init__(self):
        # Initialize Groq client using GROQ_API_KEY env variable
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        # Instructions to the AI on what to output
        self.system_prompt = """
You are an expert software architect.

Your job:
1. Read the user's full project description.
2. Infer the correct tech stack.
3. If stack cannot be inferred, ask a clarification question.
4. Always output JSON in this exact format:

{
  "need_clarification": true/false,
  "question": "string or null",
  "language": "string or null",
  "framework": "string or null",
  "docker_image": "string or null",
  "build_tool": "string or null",
  "project_type": "string or null",
  "reason": "Explain why you chose this stack"
}

Rules:
- DO NOT add text outside of the JSON.
- If ambiguous, set need_clarification=true and ask a short question.
- If enough info is present, fill all fields and set need_clarification=false.
"""

    # ------------------------------------------------------------------
    # JSON Extraction Logic (no recursive regex — safe for Python 3.13)
    # ------------------------------------------------------------------
    def _extract_json(self, text: str) -> Optional[Dict]:
        """
        Extract the first valid JSON object from the model's response.
        This works even if the model returns extra text around it.
        """
        text = text.strip()

        # 1. Try direct JSON
        try:
            return json.loads(text)
        except:
            pass

        # 2. Try substring between first '{' and last '}'
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and end > start:
            possible_json = text[start:end + 1]
            try:
                return json.loads(possible_json)
            except:
                pass

        # 3. Give up → let system ask a clarifying question
        return None

    # ------------------------------------------------------------------
    # LLM Call Wrapper
    # ------------------------------------------------------------------
    def _call_model(self, content: str) -> str:
        """
        Calls Groq ChatCompletion API.
        Returns raw string output from the AI.
        """

        resp = self.client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": content}
            ],
            temperature=0.0,
            max_completion_tokens=800,
            top_p=1,
            reasoning_effort="medium"
        )

        # Most Groq models respond with:
        # resp.choices[0].message["content"]
        print("Raw model response:", resp.choices[0].message.content)
        try:
            return resp.choices[0].message.content
        except:
            return str(resp)

    # ------------------------------------------------------------------
    # Public Method: Analyze Project Prompt
    # ------------------------------------------------------------------
    def analyze_prompt(self, prompt: str, clarification_answer: Optional[str] = None) -> Dict:
        """
        Main entry point:
        - If AI needs more info → ask question.
        - If AI can infer stack → return stack JSON.
        """

        final_prompt = prompt
        if clarification_answer:
            final_prompt += f"\n\nUser Clarification Answer: {clarification_answer}"

        raw_output = self._call_model(final_prompt)
        parsed = self._extract_json(raw_output)

        # If AI output is not valid JSON → fallback to clarification question
        if parsed is None:
            return {
                "need_clarification": True,
                "question": "I could not determine the stack. Do you prefer Java Spring Boot, Python FastAPI, Node Express, or .NET?",
                "language": None,
                "framework": None,
                "docker_image": None,
                "build_tool": None,
                "project_type": None,
                "reason": "Model output could not be parsed"
            }

        # Ensure all expected keys exist
        required_keys = [
            "need_clarification", "question",
            "language", "framework", "docker_image",
            "build_tool", "project_type", "reason"
        ]

        for key in required_keys:
            parsed.setdefault(key, None)

        # If question exists but need_clarification not set
        if parsed.get("question") and parsed.get("need_clarification") is None:
            parsed["need_clarification"] = True
        
        # here if language is java the set the docker_image to use solution-builder-java:latest
        # lang = parsed.get("language")
        # print("Detected language:", lang)
        # if isinstance(lang, str) and lang.lower() == "java":
        #     parsed["docker_image"] = "solution-builder-java:latest"

        STATIC_IMAGE_MAP = {
            "java": "solution-builder-java:latest",
            "python": "solution-builder-python:latest",
            "node": "solution-builder-node:latest",
            "dotnet": "solution-builder-dotnet:latest"
        }

        lang = parsed.get("language")
        if lang in STATIC_IMAGE_MAP:
            parsed["docker_image"] = STATIC_IMAGE_MAP[lang]


        return parsed
