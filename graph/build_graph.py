
# from langgraph.graph import StateGraph, END
# from typing import TypedDict, Optional, Dict, Any

# from agents.error_fixer import ErrorFixerAgent
# from agents.log_summarizer import LogSummarizerAgent
# from agents.stack_selector import StackSelectorAgent
# from agents.docker_agent import DockerAgent
# from agents.boilerplate_generator import BoilerplateGeneratorAgent
# from agents.file_scanner import FileScannerAgent
# from agents.file_planner import FilePlannerAgent
# from agents.code_writer_agent import CodeWriterAgent
# from agents.build_runner import BuildRunnerAgent


# from utils.docker_file_writer import write_files_in_container
# from utils.docker_zip_loader import load_zip_into_container


# # -------------------------------------------------------
# # STATE Definition (shared memory across graph nodes)
# # -------------------------------------------------------
# class BuildState(TypedDict, total=False):
#     prompt: str
#     clarification_answer: Optional[str]
#     global_spec: Optional[str]

#     # AI results
#     need_clarification: bool
#     question: Optional[str]
#     stack: Optional[Dict[str, Any]]
#     docker: Optional[Dict[str, Any]]
#     boil: Optional[Dict[str, Any]]

#     # Final
#     boilerplate_project_files: Optional[Any]
#     plan: Optional[Dict[str, Any]]
#     selected_files: Optional[Any]
#     solution: Optional[Dict[str, Any]]
#     build_result: Optional[Dict[str, Any]]
#     build_command_override: Optional[str]



# # -------------------------------------------------------
# # AGENTS
# # -------------------------------------------------------
# stack_agent = StackSelectorAgent()
# docker_agent = DockerAgent()
# boiler_agent = BoilerplateGeneratorAgent()
# scanner_agent = FileScannerAgent()
# planner_agent = FilePlannerAgent()
# writer_agent = CodeWriterAgent()
# runner_agent = BuildRunnerAgent()



# # -------------------------------------------------------
# # NODE 1: Stack Selection
# # -------------------------------------------------------
# def select_stack(state: BuildState) -> BuildState:

#     prompt = state["global_spec"] or state["prompt"]

#     result = stack_agent.analyze_prompt(
#         prompt,
#         clarification_answer=state.get("clarification_answer")
#     )

#     # If clarification needed → return early
#     if result.get("need_clarification"):
#         return {
#             **state,
#             "need_clarification": True,
#             "question": result.get("question")
#         }

#     # Otherwise stack resolved
#     stack = {
#         "language": result["language"],
#         "framework": result["framework"],
#         "docker_image": result["docker_image"],
#         "build_tool": result["build_tool"],
#         "project_type": result["project_type"],
#         "reason": result["reason"],
#         "global_spec": prompt
#     }

#     return {
#         **state,
#         "need_clarification": False,
#         "stack": stack
#     }


# # -------------------------------------------------------
# # NODE 2: Docker Setup
# # -------------------------------------------------------
# def setup_docker(state: BuildState) -> BuildState:
#     stack = state["stack"]

#     docker_env = docker_agent.create_environment(stack=stack)

#     docker_info = {
#         "container_id": docker_env["container_id"],
#         "container_name": docker_env["container_name"],
#         "workspace": docker_env["workspace"],
#         "image": docker_env["image"]
#     }

#     return {
#         **state,
#         "docker": docker_info
#     }


# # -------------------------------------------------------
# # NODE 3: Boilerplate Generation
# # -------------------------------------------------------
# def generate_boilerplate(state: BuildState) -> BuildState:

#     stack = state["stack"]
#     spec = stack["global_spec"]
#     docker = state["docker"]

#     out = boiler_agent.generate_boilerplate(stack=stack, global_spec=spec)

#     # Write files
#     if out.get("use_local"):
#         load_zip_into_container(
#             container_id=docker["container_id"],
#             zip_path=out["zip_path"]
#         )
#     else:
#         write_files_in_container(
#             container_id=docker["container_id"],
#             files=out["files"]
#         )

#     return {
#         **state,
#         "boil": {
#             "written_files": len(out["files"]),
#             "commands": out["commands"]
#         }
#     }


# # -------------------------------------------------------
# # NODE 4: Final Scan + Build Response
# # -------------------------------------------------------
# def scan_initial_files(state: BuildState) -> BuildState:
#     docker = state["docker"]
#     scan = scanner_agent.scan(container_id=docker["container_id"])

#     return {
#         **state,
#         "boilerplate_project_files": scan
#     }

# # -------------------------------------------------------
# # NODE 5: File Planner
# # -------------------------------------------------------
# def plan_files(state: BuildState) -> BuildState:
#     spec = state["stack"]["global_spec"]
#     scan = state["boilerplate_project_files"]

#     # Extract only file paths
#     file_list = [f["path"] for f in scan["files"]]

#     plan = planner_agent.plan(
#         global_spec=spec,
#         file_list=file_list
#     )

#     return {
#         **state,
#         "plan": plan
#     }

# # -------------------------------------------------------
# # NODE 6: Read only required files
# # -------------------------------------------------------
# def read_required_files(state: BuildState) -> BuildState:
#     docker = state["docker"]
#     plan = state["plan"]

#     files_to_read = plan.get("files_to_read", [])

#     selected_files = scanner_agent.read_files(
#         container_id=docker["container_id"],
#         paths=files_to_read
#     ) if files_to_read else []

#     return {
#         **state,
#         "selected_files": selected_files
#     }

# # -------------------------------------------------------
# # NODE 7: Code Writer
# # -------------------------------------------------------
# def write_solution(state: BuildState) -> BuildState:
#     spec = state["stack"]["global_spec"]
#     docker = state["docker"]
#     plan = state["plan"]

#     selected_files = state.get("selected_files", [])

#     solution = writer_agent.generate_solution(
#         global_spec=spec,
#         project_files={
#             "files_to_read": selected_files,
#             "files_to_update": plan["files_to_update"],
#             "files_to_create": plan["files_to_create"]
#         }
#     )

#     # Apply edits in Docker
#     write_files_in_container(
#         container_id=docker["container_id"],
#         files=solution["edits"]
#     )

#     return {
#         **state,
#         "solution": solution
#     }

# def run_build(state: BuildState) -> BuildState:
#     docker = state["docker"]
#     stack = state["stack"]

#     # The user may have clarified build command manually
#     override_cmd = state.get("build_command_override")

#     result = runner_agent.run_build(
#         container_id=docker["container_id"],
#         stack=stack,
#         user_override_cmd=override_cmd
#     )

#     # Ask user if build command is unknown
#     if result.get("need_clarification"):
#         return {
#             **state,
#             "need_clarification": True,
#             "question": result["question"],
#             "build_result": None
#         }

#     # Otherwise store build result
#     return {
#         **state,
#         "need_clarification": False,
#         "build_result": result
#     }

# def summarize_logs(state: BuildState) -> BuildState:
#     summarizer = LogSummarizerAgent()
    
#     build_logs = state["build_result"]["logs"]
#     summary = summarizer.summarize(build_logs)

#     return {
#         **state,
#         "error_summary": summary["error_summary"],
#         "error_block": summary["error_block"]
#     }

# def fix_errors(state: BuildState) -> BuildState:
#     fixer = ErrorFixerAgent()
#     result = fixer.fix_errors(
#         global_spec=state["stack"]["global_spec"],
#         build_logs=state["build_result"]["logs"],
#         selected_files=state["selected_files"]
#     )

#     return {
#         **state,
#         "fix_solution": result,
#         "need_clarification": False
#     }



# def finalize(state: BuildState) -> BuildState:
#     """
#     Final output after build.
#     """
#     return state



# # -------------------------------------------------------
# # BUILD LANGGRAPH
# # -------------------------------------------------------
# def create_graph():
#     graph = StateGraph(BuildState)

#     # Nodes
#     graph.add_node("select_stack", select_stack)
#     graph.add_node("setup_docker", setup_docker)
#     graph.add_node("generate_boilerplate", generate_boilerplate)
#     graph.add_node("scan_initial_files", scan_initial_files)
#     graph.add_node("plan_files", plan_files)
#     graph.add_node("read_required_files", read_required_files)
#     graph.add_node("write_solution", write_solution)
#     graph.add_node("run_build", run_build)
#     graph.add_node("summarize_logs", summarize_logs)
#     graph.add_node("fix_errors", fix_errors)
#     graph.add_node("finalize", finalize)


#     # Entry
#     graph.set_entry_point("select_stack")

#     # Branch: If clarification needed → END early
#     def ask_or_continue(state: BuildState):
#         if state.get("need_clarification"):
#             return END
#         return "setup_docker"
    
#     def build_or_fix(state: BuildState):
#         if state.get("need_clarification"):
#             return END  # ask user for command override
#         return "finalize"
    
#     def after_build(state: BuildState):
#         build = state["build_result"]

#         if build["success"]:
#             return "finalize"   # Build OK → stop here

#         return "summarize_logs" # Build failed → start fixing flow



#     # Edges
#     graph.add_conditional_edges("select_stack", ask_or_continue)
#     graph.add_edge("setup_docker", "generate_boilerplate")
#     graph.add_edge("generate_boilerplate", "scan_initial_files")
#     graph.add_edge("scan_initial_files", "plan_files")
#     graph.add_edge("plan_files", "read_required_files")
#     graph.add_edge("read_required_files", "write_solution")
#     graph.add_edge("write_solution", "run_build")
#     graph.add_conditional_edges("run_build", build_or_fix)

#     # graph.add_edge("run_build", "finalize")


#     return graph.compile()


# # -------------------------------------------------------
# # EXTERNAL FUNCTION TO CALL
# # -------------------------------------------------------
# async def execute_build_graph(prompt: str,
#                               clarification_answer: Optional[str] = None,
#                               global_spec: Optional[str] = None):
#     graph = create_graph()

#     final_state = graph.invoke({
#         "prompt": prompt,
#         "clarification_answer": clarification_answer,
#         "global_spec": global_spec
#     })

#     # RETURN EXACT SAME FORMAT AS YOUR CURRENT FUNCTION
#     if final_state.get("need_clarification"):
#         return {
#             "need_clarification": True,
#             "question": final_state["question"]
#         }

#     return {
#         "need_clarification": False,
#         "stack": final_state["stack"],
#         "docker": final_state["docker"],
#         "boilerplate": final_state["boil"],
#         "boilerplate_project_files": final_state["boilerplate_project_files"],
#         "plan": final_state["plan"],
#         "selected_files": final_state["selected_files"],
#         "solution": final_state["solution"],
#         "build_result": final_state["build_result"]
#     }


# graph/build_graph.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Dict, Any

# existing agents (assumed implemented earlier)
from agents.stack_selector import StackSelectorAgent
from agents.docker_agent import DockerAgent
from agents.boilerplate_generator import BoilerplateGeneratorAgent
from agents.file_scanner import FileScannerAgent
from agents.file_planner import FilePlannerAgent
from agents.code_writer_agent import CodeWriterAgent
from agents.error_fixer import ErrorFixerAgent
from agents.log_summarizer import LogSummarizerAgent

# new agents
from agents.build_runner import BuildRunnerAgent
from agents.runtime_runner import RuntimeRunnerAgent
from agents.testcase_generator import TestcaseGeneratorAgent

from utils.docker_file_writer import write_files_in_container
from utils.docker_zip_loader import load_zip_into_container

# ------------------------
# Shared state type
# ------------------------
class BuildState(TypedDict, total=False):
    prompt: str
    clarification_answer: Optional[str]
    global_spec: Optional[str]

    need_clarification: bool
    question: Optional[str]

    stack: Optional[Dict[str, Any]]
    docker: Optional[Dict[str, Any]]
    boil: Optional[Dict[str, Any]]

    boilerplate_project_files: Optional[Any]

    plan: Optional[Dict[str, Any]]
    selected_files: Optional[Any]
    solution: Optional[Dict[str, Any]]

    build_result: Optional[Dict[str, Any]]
    build_command_override: Optional[str]

    runtime_result: Optional[Dict[str, Any]]
    testcases: Optional[Dict[str, Any]]
    fix_solution: Optional[Dict[str, Any]]
    error_summary: Optional[str]
    error_block: Optional[str]

# ------------------------
# Initialize agents
# ------------------------
stack_agent = StackSelectorAgent()
docker_agent = DockerAgent()
boiler_agent = BoilerplateGeneratorAgent()
scanner_agent = FileScannerAgent()
planner_agent = FilePlannerAgent()
writer_agent = CodeWriterAgent()
fixer_agent = ErrorFixerAgent()
summ_agent = LogSummarizerAgent()

build_runner = BuildRunnerAgent()
runtime_runner = RuntimeRunnerAgent()
testcase_gen = TestcaseGeneratorAgent()

# ------------------------
# Nodes
# ------------------------
def select_stack(state: BuildState) -> BuildState:
    prompt = state["global_spec"] or state["prompt"]
    result = stack_agent.analyze_prompt(prompt, clarification_answer=state.get("clarification_answer"))
    if result.get("need_clarification"):
        return {**state, "need_clarification": True, "question": result.get("question")}
    stack = {
        "language": result["language"],
        "framework": result["framework"],
        "docker_image": result["docker_image"],
        "build_tool": result["build_tool"],
        "project_type": result["project_type"],
        "reason": result["reason"],
        "global_spec": prompt
    }
    return {**state, "need_clarification": False, "stack": stack}

def setup_docker(state: BuildState) -> BuildState:
    stack = state["stack"]
    docker_env = docker_agent.create_environment(stack=stack)
    docker_info = {"container_id": docker_env["container_id"], "container_name": docker_env["container_name"], "workspace": docker_env["workspace"], "image": docker_env["image"]}
    return {**state, "docker": docker_info}

def generate_boilerplate(state: BuildState) -> BuildState:
    stack = state["stack"]
    spec = stack["global_spec"]
    out = boiler_agent.generate_boilerplate(stack=stack, global_spec=spec)
    if out.get("use_local"):
        load_zip_into_container(container_id=state["docker"]["container_id"], zip_path=out["zip_path"])
    else:
        write_files_in_container(container_id=state["docker"]["container_id"], files=out["files"])
    return {**state, "boil": {"written_files": len(out.get("files", [])), "commands": out.get("commands", [])}}

def scan_initial_files(state: BuildState) -> BuildState:
    scan = scanner_agent.scan(container_id=state["docker"]["container_id"])
    return {**state, "boilerplate_project_files": scan}

def plan_files(state: BuildState) -> BuildState:
    spec = state["stack"]["global_spec"]
    scan = state.get("boilerplate_project_files", {"files":[]})
    file_list = [f["path"] for f in scan["files"]]
    plan = planner_agent.plan(global_spec=spec, file_list=file_list)
    return {**state, "plan": plan}

def read_required_files(state: BuildState) -> BuildState:
    if "plan" not in state:
        raise RuntimeError("Missing 'plan' in state.")
    docker = state["docker"]
    files_to_read = state["plan"].get("files_to_read", [])
    selected_files = scanner_agent.read_files(container_id=docker["container_id"], paths=files_to_read) if files_to_read else []
    return {**state, "selected_files": selected_files}

def write_solution(state: BuildState) -> BuildState:
    spec = state["stack"]["global_spec"]
    plan = state["plan"]
    selected_files = state.get("selected_files", [])
    solution = writer_agent.generate_solution(global_spec=spec, project_files={
        "files_to_read": selected_files,
        "files_to_update": plan.get("files_to_update", []),
        "files_to_create": plan.get("files_to_create", [])
    })
    # apply edits if any
    edits = solution.get("edits", [])
    if edits:
        write_files_in_container(container_id=state["docker"]["container_id"], files=edits)
    return {**state, "solution": solution}

def run_build(state: BuildState) -> BuildState:
    docker = state["docker"]
    stack = state["stack"]
    override = state.get("build_command_override")
    result = build_runner.run_build(container_id=docker["container_id"], stack=stack, user_override_cmd=override)
    if result.get("need_clarification"):
        return {**state, "need_clarification": True, "question": result["question"]}
    return {**state, "build_result": result, "need_clarification": False}

def after_build_branch(state: BuildState):
    br = state.get("build_result", {})
    if br.get("success"):
        return "run_runtime"
    return "summarize_logs"

def summarize_logs(state: BuildState) -> BuildState:
    logs = state["build_result"]["logs"]
    summ = summ_agent.summarize(logs)
    return {**state, "error_summary": summ.get("error_summary"), "error_block": summ.get("error_block")}

def fix_errors(state: BuildState) -> BuildState:
    spec = state["stack"]["global_spec"]
    build_logs = state["error_block"] or state.get("build_result", {}).get("logs", "")
    # choose small set of files to send (planner can be reused)
    selected_files = state.get("selected_files", [])
    fix = fixer_agent.fix_errors(global_spec=spec, build_logs=build_logs, selected_files=selected_files)
    # apply edits if present
    edits = fix.get("edits", [])
    if edits:
        write_files_in_container(container_id=state["docker"]["container_id"], files=edits)
    return {**state, "fix_solution": fix}

def run_runtime(state: BuildState) -> BuildState:
    stack = state["stack"]
    docker = state["docker"]
    # allow override runtime command if provided
    run_cmd_override = state.get("runtime_command_override")
    res = runtime_runner.start_and_check(container_id=docker["container_id"], stack=stack, user_override_cmd=run_cmd_override)
    if res.get("need_clarification"):
        return {**state, "need_clarification": True, "question": res["question"]}
    return {**state, "runtime_result": res, "need_clarification": False}

def after_runtime_branch(state: BuildState):
    rt = state.get("runtime_result", {})
    if rt.get("success"):
        return "generate_testcases"
    # runtime error -> send to fixer flow
    return "summarize_runtime_logs"

def summarize_runtime_logs(state: BuildState) -> BuildState:
    logs = state.get("runtime_result", {}).get("logs", "")
    summ = summ_agent.summarize(logs)
    return {**state, "error_summary": summ.get("error_summary"), "error_block": summ.get("error_block")}

def generate_testcases(state: BuildState) -> BuildState:
    spec = state["stack"]["global_spec"]
    stack = state["stack"]

    # Collect edited files from solution + fixer
    edits = []

    if "solution" in state and state["solution"].get("edits"):
        edits.extend(state["solution"]["edits"])

    if "fix_solution" in state and state["fix_solution"].get("edits"):
        edits.extend(state["fix_solution"]["edits"])

    # Remove duplicates by path
    unique = {}
    for f in edits:
        unique[f["path"]] = f
    edits = list(unique.values())

    # Generate automated tests
    test_result = testcase_gen.generate_tests(
        spec=spec,
        solution_files=edits,
        stack=stack
    )

    # Write tests into container
    write_files_in_container(
        container_id=state["docker"]["container_id"],
        files=test_result.get("files", [])
    )

    return {**state, "testcases": test_result}

def finalize(state: BuildState) -> BuildState:
    # final pass, return state as-is
    return state

# ------------------------
# Build graph
# ------------------------
def create_graph():
    graph = StateGraph(BuildState)

    # add nodes
    graph.add_node("select_stack", select_stack)
    graph.add_node("setup_docker", setup_docker)
    graph.add_node("generate_boilerplate", generate_boilerplate)
    graph.add_node("scan_initial_files", scan_initial_files)
    graph.add_node("plan_files", plan_files)
    graph.add_node("read_required_files", read_required_files)
    graph.add_node("write_solution", write_solution)
    graph.add_node("run_build", run_build)
    graph.add_node("summarize_logs", summarize_logs)
    graph.add_node("fix_errors", fix_errors)
    graph.add_node("run_runtime", run_runtime)
    graph.add_node("summarize_runtime_logs", summarize_runtime_logs)
    graph.add_node("generate_testcases", generate_testcases)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("select_stack")

    def ask_or_continue(state: BuildState):
        if state.get("need_clarification"):
            return END
        return "setup_docker"
    graph.add_conditional_edges("select_stack", ask_or_continue)

    # flow wiring
    graph.add_edge("setup_docker", "generate_boilerplate")
    graph.add_edge("generate_boilerplate", "scan_initial_files")
    graph.add_edge("scan_initial_files", "plan_files")
    graph.add_edge("plan_files", "read_required_files")
    graph.add_edge("read_required_files", "write_solution")
    graph.add_edge("write_solution", "run_build")

    # after build: success -> runtime; fail -> summarize_logs -> fix_errors -> write_solution -> run_build
    graph.add_conditional_edges("run_build", after_build_branch)
    graph.add_edge("summarize_logs", "fix_errors")
    graph.add_edge("fix_errors", "write_solution")

    # after runtime: success -> generate_testcases; fail -> summarize_runtime_logs -> fix_errors -> write_solution -> run_build
    graph.add_conditional_edges("run_runtime", after_runtime_branch)
    graph.add_edge("summarize_runtime_logs", "fix_errors")

    # normal success path
    graph.add_edge("run_runtime", "generate_testcases")
    graph.add_edge("generate_testcases", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()

# ------------------------
# External entry
# ------------------------
async def execute_build_graph(prompt: str, clarification_answer: Optional[str] = None, global_spec: Optional[str] = None):
    graph = create_graph()
    final_state = graph.invoke({
        "prompt": prompt,
        "clarification_answer": clarification_answer,
        "global_spec": global_spec
    })
    if final_state.get("need_clarification"):
        return {"need_clarification": True, "question": final_state["question"]}
    return {
        "need_clarification": False,
        "stack": final_state.get("stack"),
        "docker": final_state.get("docker"),
        "boilerplate": final_state.get("boil"),
        "project_files": final_state.get("boilerplate_project_files"),
        "plan": final_state.get("plan"),
        "solution": final_state.get("solution"),
        "build_result": final_state.get("build_result"),
        "runtime_result": final_state.get("runtime_result"),
        "testcases": final_state.get("testcases")
    }
