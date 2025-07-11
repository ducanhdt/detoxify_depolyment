# Introduction
This repository is a self-learning project aimed at deploying our solution for Multilingual Text Detoxification (TextDetox 2025). The goal is to create a ready-to-use production system capable of running on cloud providers like AWS, Azure, and GCP using Terraform and Docker.

For more details about TextDetox 2025, visit the [competition page](https://codalab.lisn.upsaclay.fr/competitions/22396#participate).

## Features
- **Deployment**: Uses Terraform to set up a GCP GPU instance with Docker and GPU drivers.
- **Inference Endpoint**: Implements a FastAPI service to handle inference requests using vLLM.
- **Monitoring**: Integrates Grafana and Prometheus for real-time monitoring of the deployed model.
- **Logging**: Configures logging to Google Cloud Logging and BigQuery for analysis and optimization.

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
- **Clone the repository**:
  ```bash
  git clone https://github.com/ducanhdt/detoxify_depolyment.git
  cd detoxify_depolyment
  ```
- **Set up the environment**:
  Save your Google Cloud credentials in `credentials.json` and place it in the root directory of the project. This file is used to authenticate Terraform with your GCP account.
  Run this command and wait 10 minutes for the instance to be created:
  ```bash
  bash start_service.sh
  ```

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

### 10/7/2025
- Set up logging:
  - Set up logging to Google cloud logging, auto save log to Google bigquery to optimize code and for feature analysis
  - Read vLLM system metric and API call result to log

### 11/7/2025
- Set up Grafana:
  - Create a Grafana dashboard to visualize vLLM metrics and API call results.
  - Configure Grafana to read metrics from Prometheus.
  - Create Dockerfile and docker-compose.yml file 
