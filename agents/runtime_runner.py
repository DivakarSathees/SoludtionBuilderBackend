# agents/runtime_runner.py
import time
from groq import Groq
from docker import from_env


class RuntimeRunnerAgent:
    """
    Starts the application inside Docker and checks runtime logs for errors.
    Uses hybrid runtime command selection: static for known languages, AI fallback otherwise.
    """

    def __init__(self):
        self.docker = from_env()
        self.ai = Groq(api_key=None)  # will be set via env when used

    def _static_runtime_cmd(self, stack):
        lang = stack.get("language", "").lower()
        # Common static commands (safe defaults)
        if lang == "java":
            return "mvn spring-boot:run"
        if lang == "node":
            return "npm start"
        if lang == "python":
            # assume uvicorn if FastAPI else python main
            return "uvicorn main:app --host 0.0.0.0 --port 8000"
        if lang == "dotnet":
            return "dotnet run"
        return None

    def _ai_runtime_cmd(self, stack):
        ai = Groq(api_key=__import__("os").environ.get("GROQ_API_KEY"))
        prompt = f"Given this stack, return the single shell command to start the app in foreground:\n\n{stack}\n\nReturn only the command string."
        resp = ai.chat.completions.create(
            model=__import__("os").environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role":"system","content":"You are an expert runtime engineer."},{"role":"user","content":prompt}],
            temperature=0
        )
        return resp.choices[0].message.content.strip()

    def detect_runtime_command(self, stack):
        cmd = self._static_runtime_cmd(stack)
        if cmd:
            return {"command": cmd, "need_clarification": False}
        cmd = self._ai_runtime_cmd(stack)
        if cmd:
            return {"command": cmd, "need_clarification": False}
        return {"need_clarification": True, "question": f"Cannot determine runtime command for stack: {stack}. Please provide it."}

    def start_and_check(self, container_id: str, stack: dict, user_override_cmd: str = None):
        container = self.docker.containers.get(container_id)
        if user_override_cmd:
            cmd = user_override_cmd
        else:
            decision = self.detect_runtime_command(stack)
            if decision.get("need_clarification"):
                return decision
            cmd = decision["command"]
        # start app detached
        container.exec_run(f"bash -lc \"{cmd}\"", detach=True)
        # wait a bit for startup
        time.sleep(5)
        logs = container.logs(tail=1000).decode(errors="ignore")
        has_error = ("Exception" in logs) or ("Traceback" in logs) or ("ERROR" in logs and "Started" not in logs)
        return {"success": not has_error, "logs": logs, "command": cmd}
