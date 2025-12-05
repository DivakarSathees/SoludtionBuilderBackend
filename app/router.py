from fastapi import APIRouter
from app.schemas import BuildRequest, BuildResponse
from graph.build_graph import execute_build_graph

router = APIRouter()


# @router.post("/build", response_model=BuildResponse)
# async def build_project(request: BuildRequest):
#     result = await execute_build_graph(
#         prompt=request.prompt,
#         clarification_answer=request.clarification_answer,
#         global_spec=request.global_spec
#     )

#     # AI needs more information → send question to client
#     if result.get("need_clarification"):
#         return BuildResponse(
#             status="need_clarification",
#             details={"question": result["question"]}
#         )

#     # Stack resolved → return full stack info
#     return BuildResponse(
#         status="stack_selected",
#         details=result["stack"]
#     )

@router.post("/build", response_model=BuildResponse)
async def build_project(request: BuildRequest):
    result = await execute_build_graph(
        prompt=request.prompt,
        clarification_answer=request.clarification_answer,
        global_spec=request.global_spec
    )

    # Need clarification
    if result.get("need_clarification"):
        return BuildResponse(
            status="need_clarification",
            details={"question": result["question"]}
        )

    # Return EVERYTHING (stack + docker + boilerplate)
    return BuildResponse(
        status="build_complete",
        details=result  # instead of result["stack"]
    )
