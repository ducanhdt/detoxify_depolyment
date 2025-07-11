#!/bin/bash

# Log all output to a file for debugging
exec > >(tee -a /var/log/startup-script.log)
exec 2>&1

echo "Starting startup script at $(date)"

# Update system packages
apt-get update -y

# Install required packages
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    wget

# Add Docker's official GPG key
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index
apt-get update -y

# Install Docker Engine
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker service
systemctl start docker
systemctl enable docker

# Add ubuntu user to docker group so they can run docker without sudo
usermod -aG docker ubuntu

# Install NVIDIA Container Toolkit for GPU support
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
      && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt-get update -y
apt-get install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Install NVIDIA drivers (this might take a while)
echo "Installing NVIDIA drivers..."
/opt/deeplearning/install-driver.sh || {
    echo "Fallback: Installing NVIDIA drivers manually"
    apt-get install -y ubuntu-drivers-common
    ubuntu-drivers autoinstall
}

# Verify installations
echo "Docker version:"
docker --version

echo "Docker Compose version:"
docker compose version

echo "NVIDIA driver version:"
nvidia-smi || echo "NVIDIA driver not yet available, might need reboot"

echo "Startup script completed at $(date)"

docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --enable-lora \
    --model  unsloth/gemma-3-12b-it-bnb-4bit \
    --lora-modules seen-language=anhdtd/gemma-3-12b-textDetox-2025-seen-language \
                   unseen-language=anhdtd/gemma-3-12b-textDetox-2025-unseen-language
    