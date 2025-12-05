import os


def write_files_to_workspace(base_dir: str, files: list):
    """
    Writes generated boilerplate files into the workspace.

    files = [
      {
        "path": "folder/sub/file.ext",
        "content": "file contents"
      }
    ]
    """

    for f in files:
        full_path = os.path.join(base_dir, f["path"])
        directory = os.path.dirname(full_path)

        # Create folder path
        os.makedirs(directory, exist_ok=True)

        # Write file contents
        with open(full_path, "w", encoding="utf-8") as fp:
            fp.write(f["content"])

    return True
