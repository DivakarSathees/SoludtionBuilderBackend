import uuid
import docker

STATIC_IMAGE_MAP = {
    "java": "solution-builder-java:latest",
    "python": "solution-builder-python:latest",
    "node": "solution-builder-node:latest",
    "dotnet": "solution-builder-dotnet:latest"
}


class DockerAgent:
    """
    Runs everything INSIDE Docker.
    No local paths. No volume mounts.
    """

    def __init__(self):
        self.client = docker.from_env()

    def create_environment(self, stack: dict):
        language = stack["language"].lower()

        if language not in STATIC_IMAGE_MAP:
            raise RuntimeError(f"❌ No static Dockerfile registered for language: {language}")

        image = STATIC_IMAGE_MAP[language]
        container_name = f"env_{uuid.uuid4().hex[:10]}"

        # Ensure the local static image exists
        try:
            self.client.images.get(image)
            print(f"🐳 Using local Docker image: {image}")
        except docker.errors.ImageNotFound:
            raise RuntimeError(
                f"❌ Docker image '{image}' not found locally.\n"
                f"Build it first using:\n"
                f"docker build -t {image} dockerfiles/{language}\n"
            )

        # Start container WITHOUT VOLUMES
        container = self.client.containers.run(
            image=image,
            name=container_name,
            command="tail -f /dev/null",
            detach=True,
            tty=True,
            working_dir="/workspace"  # persistent inside container only
        )

        return {
            "container_id": container.id,
            "container_name": container_name,
            "workspace": "/workspace",   # always internal path
            "image": image
        }

    def exec(self, container_id: str, command: str):
        container = self.client.containers.get(container_id)
        exit_code, output = container.exec_run(command)

        return {
            "exit_code": exit_code,
            "output": output.decode() if isinstance(output, bytes) else output
        }

    def stop(self, container_id: str):
        try:
            self.client.containers.get(container_id).stop()
        except:
            pass

    def remove(self, container_id: str):
        try:
            self.client.containers.get(container_id).remove(force=True)
        except:
            pass
