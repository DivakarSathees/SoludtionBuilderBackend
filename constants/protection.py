# constants/protection.py
# Configure what is protected inside the workspace (relative paths).
PROTECTED_DIRS = [
    # example: Do not let AI overwrite build output, config, or resources
    "springbootproject/springapp/target",
    "springbootproject/springapp/src/main/resources",
    ".mvn",
    ".github",
    "springbootproject/springapp/mvnw",
    "springbootproject/junit"
]

PROTECTED_FILES = [
    # example: critical files that must not be edited
    "springbootproject/springapp/pom.xml",
    "springbootproject/springapp/README.md",
    "springbootproject/springapp/mvnw.cmd",
    "springbootproject/junit/junit.sh"
    # add absolute relative paths to key entrypoints
]
