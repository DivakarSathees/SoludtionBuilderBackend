import os
from agents.docker_agent import DockerAgent

docker_agent = DockerAgent()

def write_files_in_container(container_id: str, files: list):
    """
    Writes files inside Docker container at /workspace.
    """

    for f in files:
        file_path = f["path"]
        content = f["content"]

        # Ensure directories exist inside container
        create_dir = f"mkdir -p /workspace/{os.path.dirname(file_path)}"
        docker_agent.exec(container_id, create_dir)

        # Write content using tee
        escaped = content.replace("'", "'\"'\"'")  # handle quotes safely

        write_cmd = f"bash -lc \"echo '{escaped}' > /workspace/{file_path}\""
        docker_agent.exec(container_id, write_cmd)
