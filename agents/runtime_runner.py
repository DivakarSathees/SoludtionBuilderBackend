# agents/runtime_runner.py
import os
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

    def _exec_stream_logs(self, container_id: str, project_root: str, command: str):
        """
        Streams logs line-by-line instead of capturing huge outputs into memory.
        Returns the full log as a single string (but built incrementally).
        """

        container = self.docker.containers.get(container_id)

        # Construct command
        full_cmd = f"bash -lc \"cd {project_root} && {command}\""

        # Run process (stream=True enables incremental logs)
        exec_id = self.docker.api.exec_create(
            container_id,
            full_cmd,
            stdin=False,
            stdout=True,
            stderr=True,
        )["Id"]

        output_stream = self.docker.api.exec_start(exec_id, stream=True)

        logs = []

        for chunk in output_stream:
            line = chunk.decode(errors="ignore")
            # print(line, end="")   # optional real-time console streaming
            logs.append(line)

        # Get exit code
        exit_code = self.docker.api.exec_inspect(exec_id)["ExitCode"]

        return exit_code, "".join(logs)


    def detect_project_root(self, container_id: str):
        container = self.docker.containers.get(container_id)

        # Look for common project types
        search_patterns = [
            "pom.xml",               # Maven
            "build.gradle",          # Gradle
            "package.json",          # Node
            "pyproject.toml",        # Python
            "requirements.txt",      # Python
            "*.csproj",              # .NET
        ]

        for pattern in search_patterns:
            cmd = f"bash -lc \"find /workspace -name '{pattern}' | head -n 1\""
            ec, out = container.exec_run(cmd)
            result = out.decode().strip()

            if result:
                # Strip filename → return folder containing it
                project_root = os.path.dirname(result)
                return project_root

        # fallback → assume workspace root
        return "/workspace"

    # def start_and_check(self, container_id: str, stack: dict, user_override_cmd: str = None):
    #     container = self.docker.containers.get(container_id)
    #     project_root = self.detect_project_root(container_id)

    #     if user_override_cmd:
    #         cmd = user_override_cmd
    #     else:
    #         decision = self.detect_runtime_command(stack)
    #         if decision.get("need_clarification"):
    #             return decision
    #         cmd = decision["command"]


    #     print(f"Starting container {container_id} with command: {cmd}")
    #     print(f"bash -lc \"cd {project_root} && {cmd}")
    #     exit_code, logs = self._exec_stream_logs(container_id, project_root, cmd)

    #     # start app detached
    #     # container.exec_run(f"bash -lc \"cd {project_root} && {cmd}\"", detach=True)
        
    #     # wait a bit for startup
    #     # time.sleep(5)
    #     print(f"Runtime command exited with code {exit_code}")
    #     logs = container.logs(tail=1000).decode(errors="ignore")
    #     has_error = ("Exception" in logs) or ("Traceback" in logs) or ("ERROR" in logs and "Started" not in logs)
    #     return {"success": not has_error, "logs": logs, "command": cmd}


    def start_and_check(self, container_id: str, stack: dict, user_override_cmd: str = None):
        container = self.docker.containers.get(container_id)
        project_root = self.detect_project_root(container_id)

        # Determine runtime command
        if user_override_cmd:
            cmd = user_override_cmd
        else:
            decision = self.detect_runtime_command(stack)
            if decision.get("need_clarification"):
                return decision
            cmd = decision["command"]

        # Convert foreground → background
        bg_cmd = f"nohup {cmd} > runtime.log 2>&1 &"

        print(f"▶️ Starting application in background: {bg_cmd}")

        # Start in background (non-blocking)
        container.exec_run(
            f"bash -lc \"cd {project_root} && {bg_cmd}\"",
            detach=True
        )

        # Give app a few seconds to boot
        time.sleep(5)

        # Read recent logs
        logs_cmd = "tail -n 300 runtime.log"
        exit_code, logs = container.exec_run(
            f"bash -lc \"cd {project_root} && {logs_cmd}\""
        )

        logs = logs.decode(errors="ignore")

        # Runtime error detection heuristics
        has_error = (
            "Exception" in logs or
            "Traceback" in logs or
            ("ERROR" in logs and "Started" not in logs)
        )

        return {
            "success": not has_error,
            "logs": logs,
            "command": bg_cmd,
            "project_root": project_root
        }

    # ---------------------------------------------------------
    # STOP RUNNING APPLICATION
    # ---------------------------------------------------------
    def stop_application(self, container_id: str):
        """
        Detects & kills Java/Node/Python/Dotnet processes running the app.
        """

        container = self.docker.containers.get(container_id)

        print(f"🛑 Stopping application inside container {container_id}")

        # Find PIDs of relevant processes
        find_pids_cmd = (
            "ps aux | grep -E 'java|mvn|node|python|uvicorn|dotnet' | "
            "grep -v grep | awk '{print $2}'"
        )

        exit_code, out = container.exec_run(f"bash -lc \"{find_pids_cmd}\"")
        pids = out.decode().strip().split()

        if not pids:
            return {"stopped": False, "message": "No running app process found"}

        # Kill each PID
        for pid in pids:
            container.exec_run(f"bash -lc \"kill -9 {pid}\"")

        # Clean logs
        container.exec_run("bash -lc \"rm -f runtime.log\"")

        return {
            "stopped": True,
            "killed_pids": pids
        }