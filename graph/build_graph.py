from typing import Optional
from agents.stack_selector import StackSelectorAgent
from agents.docker_agent import DockerAgent
from agents.boilerplate_generator import BoilerplateGeneratorAgent
# from utils.file_writer import write_files_to_workspace
from utils.docker_file_writer import write_files_in_container

import os


# -------------------------
# Initialize agents
# -------------------------
stack_agent = StackSelectorAgent()
docker_agent = DockerAgent()
boiler_agent = BoilerplateGeneratorAgent()

WORKSPACE_ROOT = "./workspace_docker"   # root workspace directory


# -----------------------------------------------------------------------
# MAIN PIPELINE: Stack Selection → Docker Setup → Boilerplate Generation
# -----------------------------------------------------------------------
async def execute_build_graph(
    prompt: str,
    clarification_answer: Optional[str] = None,
    global_spec: Optional[str] = None
):
    """
    Supervisor + HITL + Full Pipeline Execution
    1. Stack selection (AI or clarification required)
    2. Docker environment creation for the chosen stack
    3. AI-driven boilerplate generation + writing files into workspace
    """

    # Save the original problem description forever
    spec = global_spec or prompt

    # -----------------------------
    # 1) STACK SELECTION STEP
    # -----------------------------
    result = stack_agent.analyze_prompt(spec)

    # CASE A: AI requires clarification
    if result.get("need_clarification"):

        # User provided clarification → ask AI again
        if clarification_answer:
            result2 = stack_agent.analyze_prompt(
                spec,
                clarification_answer=clarification_answer
            )

            # If STILL unclear
            if result2.get("need_clarification"):
                return {
                    "need_clarification": True,
                    "question": (
                        result2.get("question")
                        or "Please clarify your tech stack choice."
                    )
                }

            # Clarified successfully → this is our final stack
            stack = {
                "language": result2["language"],
                "framework": result2["framework"],
                "docker_image": result2["docker_image"],
                "build_tool": result2["build_tool"],
                "project_type": result2["project_type"],
                "reason": result2["reason"],
                "global_spec": spec
            }

        else:
            # FIRST CLARIFICATION REQUEST → Ask user
            return {
                "need_clarification": True,
                "question": result["question"]
            }

    else:
        # CASE B: stack was inferred immediately
        stack = {
            "language": result["language"],
            "framework": result["framework"],
            "docker_image": result["docker_image"],
            "build_tool": result["build_tool"],
            "project_type": result["project_type"],
            "reason": result["reason"],
            "global_spec": spec
        }

    # ---------------------------------------------
    # 2) DOCKER SETUP AGENT
    # ---------------------------------------------
    workspace_path = os.path.join(WORKSPACE_ROOT, "project")
    os.makedirs(workspace_path, exist_ok=True)

    docker_env = docker_agent.create_environment(
        stack=stack,
        workspace_path=workspace_path
    )

    # Save docker info into response
    docker_info = {
        "container_id": docker_env["container_id"],
        "container_name": docker_env["container_name"],
        "workspace": docker_env["workspace"],
        "image": docker_env["image"]
    }

    # ---------------------------------------------
    # 3) BOILERPLATE GENERATION AGENT
    # ---------------------------------------------
    boiler_output = boiler_agent.generate_boilerplate(
        stack=stack,
        global_spec=spec
    )

    # Write files into workspace
    # write_files_to_workspace(
    #     base_dir=docker_env["workspace"],
    #     files=boiler_output["files"]
    # )
    write_files_in_container(
        container_id=docker_env["container_id"],
        files=boiler_output["files"]
    )
    print("🔥 Boilerplate files:", len(boiler_output["files"]))
    print("🔥 Workspace:", docker_env["workspace"])

    # ---------------------------------------------
    # 4) FINAL RESPONSE
    # ---------------------------------------------
    return {
        "need_clarification": False,
        "stack": stack,
        "docker": docker_info,
        "boilerplate": {
            "written_files": len(boiler_output["files"]),
            "commands": boiler_output["commands"]
        }
    }
