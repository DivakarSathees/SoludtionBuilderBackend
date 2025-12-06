# from typing import Optional
# from agents.stack_selector import StackSelectorAgent
# from agents.docker_agent import DockerAgent
# from agents.boilerplate_generator import BoilerplateGeneratorAgent
# # from utils.file_writer import write_files_to_workspace
# from utils.docker_file_writer import write_files_in_container
# from utils.docker_zip_loader import load_zip_into_container
# from agents.file_scanner import FileScannerAgent

# import os


# # -------------------------
# # Initialize agents
# # -------------------------
# stack_agent = StackSelectorAgent()
# docker_agent = DockerAgent()
# boiler_agent = BoilerplateGeneratorAgent()
# scanner_agent = FileScannerAgent()


# WORKSPACE_ROOT = "./workspace_docker"   # root workspace directory


# # -----------------------------------------------------------------------
# # MAIN PIPELINE: Stack Selection → Docker Setup → Boilerplate Generation
# # -----------------------------------------------------------------------
# async def execute_build_graph(
#     prompt: str,
#     clarification_answer: Optional[str] = None,
#     global_spec: Optional[str] = None
# ):
#     """
#     Supervisor + HITL + Full Pipeline Execution
#     1. Stack selection (AI or clarification required)
#     2. Docker environment creation for the chosen stack
#     3. AI-driven boilerplate generation + writing files into workspace
#     """

#     # Save the original problem description forever
#     spec = global_spec or prompt

#     # -----------------------------
#     # 1) STACK SELECTION STEP
#     # -----------------------------
#     result = stack_agent.analyze_prompt(spec)

#     # CASE A: AI requires clarification
#     if result.get("need_clarification"):

#         # User provided clarification → ask AI again
#         if clarification_answer:
#             result2 = stack_agent.analyze_prompt(
#                 spec,
#                 clarification_answer=clarification_answer
#             )

#             # If STILL unclear
#             if result2.get("need_clarification"):
#                 return {
#                     "need_clarification": True,
#                     "question": (
#                         result2.get("question")
#                         or "Please clarify your tech stack choice."
#                     )
#                 }

#             # Clarified successfully → this is our final stack
#             stack = {
#                 "language": result2["language"],
#                 "framework": result2["framework"],
#                 "docker_image": result2["docker_image"],
#                 "build_tool": result2["build_tool"],
#                 "project_type": result2["project_type"],
#                 "reason": result2["reason"],
#                 "global_spec": spec
#             }

#         else:
#             # FIRST CLARIFICATION REQUEST → Ask user
#             return {
#                 "need_clarification": True,
#                 "question": result["question"]
#             }

#     else:
#         # CASE B: stack was inferred immediately
#         stack = {
#             "language": result["language"],
#             "framework": result["framework"],
#             "docker_image": result["docker_image"],
#             "build_tool": result["build_tool"],
#             "project_type": result["project_type"],
#             "reason": result["reason"],
#             "global_spec": spec
#         }

#     # ---------------------------------------------
#     # 2) DOCKER SETUP AGENT
#     # ---------------------------------------------
#     # workspace_path = os.path.join(WORKSPACE_ROOT, "project")
#     # os.makedirs(workspace_path, exist_ok=True)

#     docker_env = docker_agent.create_environment(
#         stack=stack,
#         # workspace_path=workspace_path
#     )

#     # Save docker info into response
#     docker_info = {
#         "container_id": docker_env["container_id"],
#         "container_name": docker_env["container_name"],
#         "workspace": docker_env["workspace"],
#         "image": docker_env["image"]
#     }

#     # ---------------------------------------------
#     # 3) BOILERPLATE GENERATION AGENT
#     # ---------------------------------------------
#     boiler_output = boiler_agent.generate_boilerplate(
#         stack=stack,
#         global_spec=spec
#     )

#     # write_files_in_container(
#     #     container_id=docker_env["container_id"],
#     #     files=boiler_output["files"]
#     # )

#     if boiler_output.get("use_local"):
#         load_zip_into_container(
#             container_id=docker_env["container_id"],
#             zip_path=boiler_output["zip_path"]
#         )
#     else:
#         # AI fallback → write files in container
#         write_files_in_container(
#             container_id=docker_env["container_id"],
#             files=boiler_output["files"]
#         )

#     print("🔥 Boilerplate files:", len(boiler_output["files"]))
#     print("🔥 Workspace:", docker_env["workspace"])
#     scan_result = scanner_agent.scan(container_id=docker_env["container_id"])

#     # ---------------------------------------------
#     # 4) FINAL RESPONSE
#     # ---------------------------------------------
#     return {
#         "need_clarification": False,
#         "stack": stack,
#         "docker": docker_info,
#         "boilerplate": {
#             "written_files": len(boiler_output["files"]),
#             "commands": boiler_output["commands"]
#         },
#         "boilerplate_project_files": scan_result   # <-- ADD THIS

#     }


from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Dict, Any

from agents.stack_selector import StackSelectorAgent
from agents.docker_agent import DockerAgent
from agents.boilerplate_generator import BoilerplateGeneratorAgent
from agents.file_scanner import FileScannerAgent
from agents.file_planner import FilePlannerAgent
from agents.code_writer_agent import CodeWriterAgent
from agents.build_runner import BuildRunnerAgent


from utils.docker_file_writer import write_files_in_container
from utils.docker_zip_loader import load_zip_into_container


# -------------------------------------------------------
# STATE Definition (shared memory across graph nodes)
# -------------------------------------------------------
class BuildState(TypedDict, total=False):
    prompt: str
    clarification_answer: Optional[str]
    global_spec: Optional[str]

    # AI results
    need_clarification: bool
    question: Optional[str]
    stack: Optional[Dict[str, Any]]
    docker: Optional[Dict[str, Any]]
    boil: Optional[Dict[str, Any]]

    # Final
    boilerplate_project_files: Optional[Any]
    plan: Optional[Dict[str, Any]]
    selected_files: Optional[Any]
    solution: Optional[Dict[str, Any]]
    build_result: Optional[Dict[str, Any]]
    build_command_override: Optional[str]



# -------------------------------------------------------
# AGENTS
# -------------------------------------------------------
stack_agent = StackSelectorAgent()
docker_agent = DockerAgent()
boiler_agent = BoilerplateGeneratorAgent()
scanner_agent = FileScannerAgent()
planner_agent = FilePlannerAgent()
writer_agent = CodeWriterAgent()
runner_agent = BuildRunnerAgent()



# -------------------------------------------------------
# NODE 1: Stack Selection
# -------------------------------------------------------
def select_stack(state: BuildState) -> BuildState:

    prompt = state["global_spec"] or state["prompt"]

    result = stack_agent.analyze_prompt(
        prompt,
        clarification_answer=state.get("clarification_answer")
    )

    # If clarification needed → return early
    if result.get("need_clarification"):
        return {
            **state,
            "need_clarification": True,
            "question": result.get("question")
        }

    # Otherwise stack resolved
    stack = {
        "language": result["language"],
        "framework": result["framework"],
        "docker_image": result["docker_image"],
        "build_tool": result["build_tool"],
        "project_type": result["project_type"],
        "reason": result["reason"],
        "global_spec": prompt
    }

    return {
        **state,
        "need_clarification": False,
        "stack": stack
    }


# -------------------------------------------------------
# NODE 2: Docker Setup
# -------------------------------------------------------
def setup_docker(state: BuildState) -> BuildState:
    stack = state["stack"]

    docker_env = docker_agent.create_environment(stack=stack)

    docker_info = {
        "container_id": docker_env["container_id"],
        "container_name": docker_env["container_name"],
        "workspace": docker_env["workspace"],
        "image": docker_env["image"]
    }

    return {
        **state,
        "docker": docker_info
    }


# -------------------------------------------------------
# NODE 3: Boilerplate Generation
# -------------------------------------------------------
def generate_boilerplate(state: BuildState) -> BuildState:

    stack = state["stack"]
    spec = stack["global_spec"]
    docker = state["docker"]

    out = boiler_agent.generate_boilerplate(stack=stack, global_spec=spec)

    # Write files
    if out.get("use_local"):
        load_zip_into_container(
            container_id=docker["container_id"],
            zip_path=out["zip_path"]
        )
    else:
        write_files_in_container(
            container_id=docker["container_id"],
            files=out["files"]
        )

    return {
        **state,
        "boil": {
            "written_files": len(out["files"]),
            "commands": out["commands"]
        }
    }


# -------------------------------------------------------
# NODE 4: Final Scan + Build Response
# -------------------------------------------------------
def scan_initial_files(state: BuildState) -> BuildState:
    docker = state["docker"]
    scan = scanner_agent.scan(container_id=docker["container_id"])

    return {
        **state,
        "boilerplate_project_files": scan
    }

# -------------------------------------------------------
# NODE 5: File Planner
# -------------------------------------------------------
def plan_files(state: BuildState) -> BuildState:
    spec = state["stack"]["global_spec"]
    scan = state["boilerplate_project_files"]

    # Extract only file paths
    file_list = [f["path"] for f in scan["files"]]

    plan = planner_agent.plan(
        global_spec=spec,
        file_list=file_list
    )

    return {
        **state,
        "plan": plan
    }

# -------------------------------------------------------
# NODE 6: Read only required files
# -------------------------------------------------------
def read_required_files(state: BuildState) -> BuildState:
    docker = state["docker"]
    plan = state["plan"]

    files_to_read = plan.get("files_to_read", [])

    selected_files = scanner_agent.read_files(
        container_id=docker["container_id"],
        paths=files_to_read
    ) if files_to_read else []

    return {
        **state,
        "selected_files": selected_files
    }

# -------------------------------------------------------
# NODE 7: Code Writer
# -------------------------------------------------------
def write_solution(state: BuildState) -> BuildState:
    spec = state["stack"]["global_spec"]
    docker = state["docker"]
    plan = state["plan"]

    selected_files = state.get("selected_files", [])

    solution = writer_agent.generate_solution(
        global_spec=spec,
        project_files={
            "files_to_read": selected_files,
            "files_to_update": plan["files_to_update"],
            "files_to_create": plan["files_to_create"]
        }
    )

    # Apply edits in Docker
    write_files_in_container(
        container_id=docker["container_id"],
        files=solution["edits"]
    )

    return {
        **state,
        "solution": solution
    }

def run_build(state: BuildState) -> BuildState:
    docker = state["docker"]
    stack = state["stack"]

    # The user may have clarified build command manually
    override_cmd = state.get("build_command_override")

    result = runner_agent.run_build(
        container_id=docker["container_id"],
        stack=stack,
        user_override_cmd=override_cmd
    )

    # Ask user if build command is unknown
    if result.get("need_clarification"):
        return {
            **state,
            "need_clarification": True,
            "question": result["question"],
            "build_result": None
        }

    # Otherwise store build result
    return {
        **state,
        "need_clarification": False,
        "build_result": result
    }

def finalize(state: BuildState) -> BuildState:
    """
    Final output after build.
    """
    return state



# -------------------------------------------------------
# BUILD LANGGRAPH
# -------------------------------------------------------
def create_graph():
    graph = StateGraph(BuildState)

    # Nodes
    graph.add_node("select_stack", select_stack)
    graph.add_node("setup_docker", setup_docker)
    graph.add_node("generate_boilerplate", generate_boilerplate)
    graph.add_node("scan_initial_files", scan_initial_files)
    graph.add_node("plan_files", plan_files)
    graph.add_node("read_required_files", read_required_files)
    graph.add_node("write_solution", write_solution)
    graph.add_node("run_build", run_build)
    graph.add_node("finalize", finalize)


    # Entry
    graph.set_entry_point("select_stack")

    # Branch: If clarification needed → END early
    def ask_or_continue(state: BuildState):
        if state.get("need_clarification"):
            return END
        return "setup_docker"
    
    def build_or_fix(state: BuildState):
        if state.get("need_clarification"):
            return END  # ask user for command override
        return "finalize"


    # Edges
    graph.add_conditional_edges("select_stack", ask_or_continue)
    graph.add_edge("setup_docker", "generate_boilerplate")
    graph.add_edge("generate_boilerplate", "scan_initial_files")
    graph.add_edge("scan_initial_files", "plan_files")
    graph.add_edge("plan_files", "read_required_files")
    graph.add_edge("read_required_files", "write_solution")
    graph.add_edge("write_solution", "run_build")
    graph.add_conditional_edges("run_build", build_or_fix)

    # graph.add_edge("run_build", "finalize")


    return graph.compile()


# -------------------------------------------------------
# EXTERNAL FUNCTION TO CALL
# -------------------------------------------------------
async def execute_build_graph(prompt: str,
                              clarification_answer: Optional[str] = None,
                              global_spec: Optional[str] = None):
    graph = create_graph()

    final_state = graph.invoke({
        "prompt": prompt,
        "clarification_answer": clarification_answer,
        "global_spec": global_spec
    })

    # RETURN EXACT SAME FORMAT AS YOUR CURRENT FUNCTION
    if final_state.get("need_clarification"):
        return {
            "need_clarification": True,
            "question": final_state["question"]
        }

    return {
        "need_clarification": False,
        "stack": final_state["stack"],
        "docker": final_state["docker"],
        "boilerplate": final_state["boil"],
        "boilerplate_project_files": final_state["boilerplate_project_files"],
        "plan": final_state["plan"],
        "selected_files": final_state["selected_files"],
        "solution": final_state["solution"],
        "build_result": final_state["build_result"]
    }
