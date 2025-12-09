FROM ubuntu:22.04

# --- Core OS Packages ---
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk \
    curl \
    bash \
    git \
    unzip \
    maven \
    mariadb-server \
    ca-certificates \
    gnupg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- Install GitHub CLI ---
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | gpg --dearmor -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) \
      signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] \
      https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh

# --- Install NVM + Node 22 (Copilot requirement) ---
ENV NVM_DIR=/usr/local/nvm
ENV NODE_VERSION=22.11.0
ENV PATH=$NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH

RUN mkdir -p $NVM_DIR \
    && curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh \
    -o /tmp/install_nvm.sh \
    && bash /tmp/install_nvm.sh \
    && bash -lc "export NVM_DIR=$NVM_DIR && . $NVM_DIR/nvm.sh && \
       nvm install $NODE_VERSION && \
       nvm alias default $NODE_VERSION && \
       nvm use default"

# -----------------------------------------------------------
# Install NVM + Node 14 + Node 18
# -----------------------------------------------------------
ENV NVM_DIR=/usr/local/nvm
ENV NODE_VERSION=18.20.4
ENV NODE_VERSION_14=14.17.1
ENV PATH=$NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH
ENV PATH=$NVM_DIR/versions/node/v$NODE_VERSION_14/bin:$PATH

RUN mkdir -p $NVM_DIR && \
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh \
        -o /tmp/install_nvm.sh && \
    bash /tmp/install_nvm.sh && \
    bash -lc "export NVM_DIR=$NVM_DIR && . $NVM_DIR/nvm.sh && \
        nvm install $NODE_VERSION && \
        nvm install $NODE_VERSION_14 && \
        nvm alias default $NODE_VERSION_14 && \
        nvm use default" && \
    ln -sf $NVM_DIR/versions/node/v$NODE_VERSION/bin/node /usr/local/bin/node18 && \
    ln -sf $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm /usr/local/bin/npm18 && \
    ln -sf $NVM_DIR/versions/node/v$NODE_VERSION/bin/npx /usr/local/bin/npx18 && \
    ln -sf $NVM_DIR/versions/node/v$NODE_VERSION_14/bin/node /usr/local/bin/node14 && \
    ln -sf $NVM_DIR/versions/node/v$NODE_VERSION_14/bin/npm /usr/local/bin/npm14 && \
    ln -sf $NVM_DIR/versions/node/v$NODE_VERSION_14/bin/npx /usr/local/bin/npx14

# --- Install GitHub Copilot CLI ---

# --- Verify ---
RUN java -version && mvn -version && bash -lc "node -v" && gh --version

# --- Workspace ---
WORKDIR /home/coder/project/workspace
COPY . .

# --- Expose ---
EXPOSE 8080 3306

# --- Initialize MariaDB ---
RUN mkdir -p /run/mysqld && \
    mkdir -p /var/lib/mysql && \
    chown -R mysql:mysql /run/mysqld /var/lib/mysql && \
    mariadb-install-db --user=mysql --ldata=/var/lib/mysql

# --- Set root password ---
RUN mysqld --user=mysql & sleep 10 && \
    mariadb -u root -pexamly -e "CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY 'examly';" && \
    mariadb -u root -pexamly -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;" && \
    mariadb -u root -pexamly -e "FLUSH PRIVILEGES;"

COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]

# --- Start MariaDB + Spring Boot ---
# CMD ["bash", "-c", "mysqld --user=mysql & sleep 10"]

