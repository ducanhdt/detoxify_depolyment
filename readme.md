# Introduction
This repository is a self-learning project aimed at deploying our solution for Multilingual Text Detoxification (TextDetox 2025). The goal is to create a ready-to-use production system capable of running on cloud providers like AWS, Azure, and GCP using Terraform and Docker.

For more details about TextDetox 2025, visit the [competition page](https://codalab.lisn.upsaclay.fr/competitions/22396#participate).

---

## Plan Features

- **CI/CD pipeline**
- **Auto-retraining and auto-deployment**
- **Monitoring and alerting** for:
  - System performance
  - Data shifts
  - Versioning
  - Model drift

---

## Usage

*To be documented*

---

## Changelog

### 8/7/2025
- **Set up Terraform** to create a GCP GPU instance that:
  - Automatically installs Docker and GPU drivers
  - Runs the vLLM service with Docker Compose to host public LLMs from Hugging Face
  - Configures SSH keys for instance access

### 9/7/2025
- Develop FastAPI Inference Endpoint:
  - Configure vLLM to serve the fine-tuned model, loading both LoRA adapters.
  - Design the API call flow, including prompt construction and interaction with the deployed vLLM instance.
  - Add a foundational middleware layer for prompt security, mitigating potential leakage.