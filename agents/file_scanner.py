import docker
import json


class FileScannerAgent:
    """
    Reads all files inside the Docker container workspace.
    Returns full project structure as JSON.
    """

    def __init__(self):
        self.client = docker.from_env()

    def scan(self, container_id: str, root="/workspace") -> dict:
        """
        Recursively scans all files and reads their content.
        """

        container = self.client.containers.get(container_id)

        # 1) Get recursive file list using `find`
        cmd_list = f"bash -lc \"find {root} -type f\""
        exit_code, output = container.exec_run(cmd_list)

        if exit_code != 0:
            return {"error": "Failed to scan container filesystem"}

        file_paths = output.decode().strip().split("\n")
        files_json = []

        for file_path in file_paths:
            if not file_path.strip():
                continue

            # 2) Read file content
            read_cmd = f"bash -lc \"cat '{file_path}'\""
            exit_code, content = container.exec_run(read_cmd)
            content = content.decode(errors="ignore") if isinstance(content, bytes) else content

            # Normalize path: remove "/workspace/"
            if file_path.startswith(root + "/"):
                relative_path = file_path[len(root) + 1:]
            else:
                relative_path = file_path

            files_json.append({
                "path": relative_path,
                "content": content
            })

        return {
            "file_count": len(files_json),
            "files": files_json
        }

 # -----------------------------------------------------------------
    # Read ONLY a specific set of files (paths from planner)
    # -----------------------------------------------------------------
    def read_files(self, container_id: str, paths):
        """
        Reads ONLY the files requested by File Planner Agent.
        paths: ["path1.java", "src/.../Teacher.java"]
        """

        container = self.client.containers.get(container_id)
        results = []

        for rel_path in paths:
            full_path = f"/workspace/{rel_path}"

            cmd = f"bash -lc \"cat '{full_path}'\""
            ec, content = container.exec_run(cmd)

            if ec != 0:
                # file not found or error
                results.append({
                    "path": rel_path,
                    "content": None,
                    "error": "File not found in container"
                })
                continue

            results.append({
                "path": rel_path,
                "content": content.decode(errors="ignore")
            })

        return results