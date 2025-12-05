import io
import tarfile
import docker
import os

def write_files_in_container(container_id: str, files: list):
    """
    Writes files into Docker container using tar upload.
    100% safe for multi-line Java, XML, YAML, JSON, etc.
    """

    client = docker.from_env()
    container = client.containers.get(container_id)

    for f in files:
        path = f["path"]
        content = f["content"]

        data = content.encode("utf-8")

        tarstream = io.BytesIO()
        tar = tarfile.TarFile(fileobj=tarstream, mode="w")

        # Directory path inside container
        dir_path = os.path.dirname(path)

        # Ensure directory exists (via exec)
        container.exec_run(f"mkdir -p /workspace/{dir_path}")

        # Create tar entry
        tarinfo = tarfile.TarInfo(name=path)
        tarinfo.size = len(data)
        tarinfo.mode = 0o644

        tar.addfile(tarinfo, io.BytesIO(data))
        tar.close()
        tarstream.seek(0)

        # Send tar to container
        container.put_archive("/workspace", tarstream.getvalue())

        print(f"✔ Successfully wrote file: /workspace/{path}")
