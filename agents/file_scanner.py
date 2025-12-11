# import docker
# import json
# from constants.protection import PROTECTED_DIRS, PROTECTED_FILES



# class FileScannerAgent:
#     """
#     Reads all files inside the Docker container workspace.
#     Returns full project structure as JSON.
#     """

#     def __init__(self):
#         self.client = docker.from_env()

#     def scan(self, container_id: str, root="/workspace") -> dict:
#         """
#         Recursively scans all files and reads their content.
#         """

#         container = self.client.containers.get(container_id)

#         # 1) Get recursive file list using `find`
#         cmd_list = f"bash -lc \"find {root} -type f\""
#         exit_code, output = container.exec_run(cmd_list)

#         if exit_code != 0:
#             return {"error": "Failed to scan container filesystem"}

#         file_paths = output.decode().strip().split("\n")
#         files_json = []

#         for file_path in file_paths:
#             if not file_path.strip():
#                 continue

#             # 2) Read file content
#             read_cmd = f"bash -lc \"cat '{file_path}'\""
#             exit_code, content = container.exec_run(read_cmd)
#             content = content.decode(errors="ignore") if isinstance(content, bytes) else content

#             # Normalize path: remove "/workspace/"
#             if file_path.startswith(root + "/"):
#                 relative_path = file_path[len(root) + 1:]
#             else:
#                 relative_path = file_path

#             files_json.append({
#                 "path": relative_path,
#                 "content": content
#             })

#         return {
#             "file_count": len(files_json),
#             "files": files_json
#         }

#  # -----------------------------------------------------------------
#     # Read ONLY a specific set of files (paths from planner)
#     # -----------------------------------------------------------------
#     def read_files(self, container_id: str, paths):
#         """
#         Reads ONLY the files requested by File Planner Agent.
#         paths: ["path1.java", "src/.../Teacher.java"]
#         """

#         container = self.client.containers.get(container_id)
#         results = []

#         for rel_path in paths:
#             full_path = f"/workspace/{rel_path}"

#             cmd = f"bash -lc \"cat '{full_path}'\""
#             ec, content = container.exec_run(cmd)

#             if ec != 0:
#                 # file not found or error
#                 results.append({
#                     "path": rel_path,
#                     "content": None,
#                     "error": "File not found in container"
#                 })
#                 continue

#             results.append({
#                 "path": rel_path,
#                 "content": content.decode(errors="ignore")
#             })

#         return results


# agents/file_scanner.py
import docker
import os
from constants.protection import PROTECTED_DIRS, PROTECTED_FILES

class FileScannerAgent:
    """
    Scan container /workspace and return list of files with protection metadata.
    """

    def __init__(self):
        self.client = docker.from_env()

    def _is_protected(self, rel_path: str) -> bool:
        # Normalize path
        p = rel_path.replace("\\", "/")
        for d in PROTECTED_DIRS:
            if p.startswith(d.rstrip("/") + "/") or p == d.rstrip("/"):
                return True
        if p in PROTECTED_FILES:
            return True
        return False

    def scan(self, container_id: str, root="/workspace") -> dict:
        container = self.client.containers.get(container_id)
        # list files
        cmd = f"bash -lc \"find {root} -type f -print\""
        ec, out = container.exec_run(cmd)
        if ec != 0:
            return {"file_count": 0, "files": [], "protected": {"dirs": PROTECTED_DIRS, "files": PROTECTED_FILES}}

        all_paths = out.decode().splitlines()
        files = []
        for full in all_paths:
            if not full.strip():
                continue
            # relative path inside workspace
            if full.startswith(root + "/"):
                rel = full[len(root) + 1:]
            elif full == root:
                rel = ""
            else:
                rel = full
            # read content
            ec2, content = container.exec_run(f"bash -lc \"cat '{full}'\"")
            content_text = content.decode(errors="ignore") if ec2 == 0 else ""
            protected = self._is_protected(rel)
            files.append({
                "path": rel,
                "content": content_text,
                "protected": protected
            })
        return {"file_count": len(files), "files": files, "protected": {"dirs": PROTECTED_DIRS, "files": PROTECTED_FILES}}
    
    def read_files(self, container_id: str, paths):
        container = self.client.containers.get(container_id)
        results = []
        for rel in paths:
            full = f"/workspace/{rel}"
            ec, out = container.exec_run(f"bash -lc \"cat '{full}'\"")
            if ec != 0:
                results.append({"path": rel, "content": None, "error": "not_found"})
            else:
                results.append({"path": rel, "content": out.decode(errors="ignore")})
        return results
