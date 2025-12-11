# import docker
# import os
# import io
# import tarfile
# import zipfile


# def load_zip_into_container(container_id: str, zip_path: str):
#     """
#     Safely loads a ZIP template into the Docker container.
#     Handles conflicts where ZIP might contain both a file and a directory
#     with the same name.
#     """

#     client = docker.from_env()

#     if not os.path.exists(zip_path):
#         raise FileNotFoundError(f"ZIP not found: {zip_path}")

#     container = client.containers.get(container_id)

#     tar_stream = io.BytesIO()

#     # Create tar safely
#     with tarfile.open(fileobj=tar_stream, mode="w") as tar:
#         with zipfile.ZipFile(zip_path, "r") as zip_ref:
#             for zip_info in zip_ref.infolist():

#                 # Normalize path and skip invalid entries
#                 path = zip_info.filename.strip("/")

#                 if not path or path.endswith("/"):
#                     # Create directory
#                     dir_info = tarfile.TarInfo(name=path)
#                     dir_info.type = tarfile.DIRTYPE
#                     dir_info.mode = 0o755
#                     tar.addfile(dir_info)
#                     continue

#                 file_data = zip_ref.read(zip_info.filename)

#                 # Force-create folder structure before adding file
#                 folder = os.path.dirname(path)
#                 if folder:
#                     dir_info = tarfile.TarInfo(name=folder)
#                     dir_info.type = tarfile.DIRTYPE
#                     dir_info.mode = 0o755
#                     try:
#                         tar.addfile(dir_info)
#                     except:
#                         pass  # folder already added

#                 # Add file
#                 file_info = tarfile.TarInfo(name=path)
#                 file_info.size = len(file_data)
#                 tar.addfile(file_info, io.BytesIO(file_data))

#     tar_stream.seek(0)

#     # Upload to container
#     container.put_archive("/workspace", tar_stream.getvalue())

#     return True


import docker
import os
import io
import tarfile
import zipfile


def load_zip_into_container(container_id: str, zip_path: str):
    client = docker.from_env()

    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP not found: {zip_path}")

    container = client.containers.get(container_id)

    tar_stream = io.BytesIO()

    # Create tar safely
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for zip_info in zip_ref.infolist():
                path = zip_info.filename.strip("/")

                if not path or path.endswith("/"):
                    dir_info = tarfile.TarInfo(name=path)
                    dir_info.type = tarfile.DIRTYPE
                    dir_info.mode = 0o755
                    tar.addfile(dir_info)
                    continue

                file_data = zip_ref.read(zip_info.filename)

                folder = os.path.dirname(path)
                if folder:
                    dir_info = tarfile.TarInfo(name=folder)
                    dir_info.type = tarfile.DIRTYPE
                    dir_info.mode = 0o755
                    try:
                        tar.addfile(dir_info)
                    except:
                        pass

                file_info = tarfile.TarInfo(name=path)
                file_info.size = len(file_data)
                tar.addfile(file_info, io.BytesIO(file_data))

        # -----------------------------------
        # ADD dbshell.sh FILE
        # -----------------------------------
        script_content = b"""#!/bin/bash

echo "=== Fixing MariaDB directories ==="
mkdir -p /run/mysqld
chown -R mysql:mysql /run/mysqld

echo "=== Starting MariaDB ==="
mysqld --user=mysql --skip-log-error &
sleep 5

echo "=== Waiting for MariaDB socket ==="
for i in {1..20}; do
    if mysqladmin ping -u root -pexamly --silent; then
        echo "MariaDB is ready!"
        break
    fi
    echo "Waiting..."
    sleep 2
done

echo "=== Starting Spring Boot ==="
"""

        script_info = tarfile.TarInfo(name="dbshell.sh")
        script_info.mode = 0o755  # executable
        script_info.size = len(script_content)

        tar.addfile(script_info, io.BytesIO(script_content))

    tar_stream.seek(0)

    # Upload files to the container
    container.put_archive("/workspace", tar_stream.getvalue())

    # -----------------------------------
    # RUN dbshell.sh inside container
    # -----------------------------------
    exec_result = container.exec_run("bash /workspace/dbshell.sh")

    print("Script Output:")
    print(exec_result.output.decode())

    return True
