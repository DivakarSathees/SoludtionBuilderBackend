# import docker
# import os
# import json
# from groq import Groq


# class BuildRunnerAgent:
#     """
#     Runs project builds in Docker.
#     Chooses build commands via:
#       1. Static rules for known languages
#       2. AI fallback for unknown languages or exotic toolchains
#       3. Human clarification if AI also can't determine
#     """

#     def __init__(self):
#         self.client = docker.from_env()
#         self.ai = Groq(api_key=os.getenv("GROQ_API_KEY"))

#         self.system_prompt = """
# You are an expert build system engineer.

# Your job: Given a project stack (language, framework, build tool),
# determine the SINGLE correct shell command to build + run tests.

# Output strictly in this JSON format:

# {
#   "command": "bash command here"
# }

# Rules:
# - MUST return exactly one command.
# - No explanations.
# - No markdown.
# - No comments.
# """

#     # ---------------------------------------------------
#     # 🚀 1) Static rules for known languages
#     # ---------------------------------------------------
#     def _static_build_command(self, stack):
#         lang = stack.get("language", "").lower()
#         tool = stack.get("build_tool", "").lower()

#         # Java
#         if lang == "java":
#             if "maven" in tool:
#                 # build command only
#                 return "mvn clean install"
#             if "gradle" in tool:
#                 return "gradle test --stacktrace"
#             return "mvn test"

#         # Node
#         if lang == "node":
#             return "npm install && npm test"

#         # Python
#         if lang == "python":
#             return "pytest -q"

#         # .NET
#         if lang == "dotnet":
#             return "dotnet test"

#         return None  # unknown → fallback to AI

#     # ---------------------------------------------------
#     # 🚀 2) Ask AI to determine correct build command
#     # ---------------------------------------------------
#     def _ask_ai_for_command(self, stack):
#         prompt = f"""
# STACK INFORMATION:
# {json.dumps(stack, indent=2)}

# TASK:
# Determine correct build + test command.
# Respond only with JSON.
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

#         # Parse JSON
#         try:
#             # Extract JSON even if messy
#             start = text.find("{")
#             end = text.rfind("}")
#             if start != -1 and end != -1:
#                 parsed = json.loads(text[start:end+1])
#                 return parsed.get("command")
#         except:
#             return None

#     # ---------------------------------------------------
#     # 🚀 3) Detect build command (static → AI → user)
#     # ---------------------------------------------------
#     def detect_build_command(self, stack):
#         # 1) Try static known toolchains
#         cmd = self._static_build_command(stack)
#         if cmd:
#             return {"command": cmd, "need_clarification": False}

#         # 2) AI fallback
#         cmd = self._ask_ai_for_command(stack)
#         if cmd:
#             return {"command": cmd, "need_clarification": False}

#         # 3) Ask user
#         return {
#             "need_clarification": True,
#             "question": f"I cannot determine the build command for this stack: {stack}. What command should be used to build & test the project?"
#         }

#     # ---------------------------------------------------
#     # 🔧 Run command inside Docker
#     # ---------------------------------------------------
#     def _exec(self, container_id: str, command: str):
#         container = self.client.containers.get(container_id)
#         exit_code, output = container.exec_run(
#             f"bash -lc \"{command}\"",
#             stdout=True,
#             stderr=True
#         )
#         text = output.decode(errors="ignore")
#         return exit_code, text

#     # ---------------------------------------------------
#     # 🚀 MAIN METHOD: Run build
#     # ---------------------------------------------------
#     def run_build(self, container_id: str, stack: dict, user_override_cmd=None):
#         """
#         Returns:
#         {
#           "success": bool,
#           "exit_code": int,
#           "logs": str,
#           "command": str,
#           "need_clarification": bool,
#           "question": str | None
#         }
#         """

#         # If user manually provided a command → use it
#         if user_override_cmd:
#             cmd = user_override_cmd
#             need_user = False
#         else:
#             detect = self.detect_build_command(stack)

#             if detect.get("need_clarification"):
#                 return detect  # Ask user for input

#             cmd = detect["command"]

#         print(f"\n🚀 Running inside Docker: {cmd}\n")

#         exit_code, logs = self._exec(container_id, cmd)

#         return {
#             "success": exit_code == 0,
#             "exit_code": exit_code,
#             "logs": logs,
#             "command": cmd,
#             "need_clarification": False
#         }


import docker
import os
import json
from groq import Groq

class BuildRunnerAgent:
    """
    Runs project builds inside Docker.
    Automatically detects build directory and executes commands inside it.
    """

    def __init__(self):
        self.client = docker.from_env()
        self.ai = Groq(api_key=os.getenv("GROQ_API_KEY"))

        self.system_prompt = """
# You are an expert build system engineer.

# Your job: Given a project stack (language, framework, build tool),
# determine the SINGLE correct shell command to build + run tests.

# Output strictly in this JSON format:

# {
#   "command": "bash command here"
# }

# Rules:
# - MUST return exactly one command.
# - No explanations.
# - No markdown.
# - No comments.
# """

    # ---------------------------------------------------------
    # Detect where the actual project root is
    # ---------------------------------------------------------
    def detect_project_root(self, container_id: str):
        container = self.client.containers.get(container_id)

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

    # ---------------------------------------------------------
    # Execute a command inside project directory
    # ---------------------------------------------------------
    def _exec_in_dir(self, container_id: str, project_root: str, command: str):
        container = self.client.containers.get(container_id)

        full_cmd = f"bash -lc \"cd {project_root} && {command}\""

        exit_code, output = container.exec_run(
            full_cmd,
            stdout=True,
            stderr=True
        )

        return exit_code, output.decode(errors="ignore")
    
    def _exec_stream_logs(self, container_id: str, project_root: str, command: str):
        """
        Streams logs line-by-line instead of capturing huge outputs into memory.
        Returns the full log as a single string (but built incrementally).
        """

        container = self.client.containers.get(container_id)

        # Construct command
        full_cmd = f"bash -lc \"cd {project_root} && {command}\""

        # Run process (stream=True enables incremental logs)
        exec_id = self.client.api.exec_create(
            container_id,
            full_cmd,
            stdin=False,
            stdout=True,
            stderr=True,
        )["Id"]

        output_stream = self.client.api.exec_start(exec_id, stream=True)

        logs = []

        for chunk in output_stream:
            line = chunk.decode(errors="ignore")
            print(line, end="")   # optional real-time console streaming
            logs.append(line)

        # Get exit code
        exit_code = self.client.api.exec_inspect(exec_id)["ExitCode"]

        return exit_code, "".join(logs)


    # ---------------------------------------------------------
    # Static known build commands
    # ---------------------------------------------------------
    def _static_build_command(self, stack):
        lang = stack.get("language", "").lower()
        tool = stack.get("build_tool", "").lower()

        if lang == "java":
            if "maven" in tool:
                return "mvn clean install"
            if "gradle" in tool:
                return "gradle test --stacktrace"
            return "mvn test"

        if lang == "node":
            return "npm install && npm test"

        if lang == "python":
            return "pytest -q"

        if lang == "dotnet":
            return "dotnet build"

        return None  # unknown → use AI

    # ---------------------------------------------------------
    # AI fallback for unusual stacks
    # ---------------------------------------------------------
    def _ask_ai_for_command(self, stack):
        prompt = f"""
STACK INFORMATION:
{json.dumps(stack, indent=2)}

Determine the exact build + test command.
Output only JSON.
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
            parsed = json.loads(text[start:end+1])
            return parsed.get("command")
        except:
            return None

    # ---------------------------------------------------------
    # Choose the correct build command (static → AI → user)
    # ---------------------------------------------------------
    def detect_build_command(self, stack):
        cmd = self._static_build_command(stack)
        if cmd:
            return {"command": cmd, "need_clarification": False}

        cmd = self._ask_ai_for_command(stack)
        if cmd:
            return {"command": cmd, "need_clarification": False}

        return {
            "need_clarification": True,
            "question": f"Cannot determine build command for stack: {stack}. Please provide it."
        }

    # ---------------------------------------------------------
    # MAIN: Run the build
    # ---------------------------------------------------------
    def run_build(self, container_id: str, stack: dict, user_override_cmd=None):
        project_root = self.detect_project_root(container_id)

        if user_override_cmd:
            cmd = user_override_cmd
        else:
            decision = self.detect_build_command(stack)

            if decision.get("need_clarification"):
                return decision

            cmd = decision["command"]

        print(f"\n🚀 Running build in: {project_root}\n➡️ {cmd}")

        # exit_code, logs = self._exec_in_dir(container_id, project_root, cmd)
        exit_code, logs = self._exec_stream_logs(container_id, project_root, cmd)


        return {
            "success": exit_code == 0,
            "exit_code": exit_code,
            "logs": logs,
            "command": cmd,
            "project_root": project_root,
            "need_clarification": False
        }
