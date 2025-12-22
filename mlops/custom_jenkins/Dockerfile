# Ref: https://hackmamba.io/blog/2022/04/running-docker-in-a-jenkins-container/
FROM jenkins/jenkins:lts-jdk17

USER root

# Install common prerequisites and Python
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg2 lsb-release apt-transport-https \
        python3 python3-pip; \
    rm -rf /var/lib/apt/lists/*;

# Install uv (astral.sh). The installer places binaries in $HOME/.local/bin
RUN curl -LsSf https://astral.sh/uv/install.sh | sh; \
    ln -sf /root/.local/bin/uv /usr/local/bin/uv || true; \
    ln -sf /root/.local/bin/uvx /usr/local/bin/uvx || true

# Install Docker CLI (installer) - this installs the docker engine/cli package.
# In CI it's recommended to either mount the host Docker socket or use a DinD approach.
RUN curl -fsSL https://get.docker.com -o /tmp/get-docker.sh; \
    sh /tmp/get-docker.sh; \
    rm -f /tmp/get-docker.sh

# Install kubectl
RUN set -eux; \
    KUBECTL_URL="https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl"; \
    curl -fsSL -o /usr/local/bin/kubectl "$KUBECTL_URL"; \
    chmod +x /usr/local/bin/kubectl

# Install Helm
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

USER jenkins