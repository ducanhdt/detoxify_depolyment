provider "google" {
  credentials = file("credentials.json") # Use service account credentials
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_compute_instance" "gemma_l4_vm" {
  name         = "gemma-l4-vm"
  machine_type = "g2-standard-4"
  zone         = var.zone

  tags = ["gemma-server"]

  boot_disk {
    initialize_params {
      # Use a standard operating system image
      image = "ubuntu-os-cloud/ubuntu-2204-lts" # Or another preferred OS like Debian
      size  = 100
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"

    access_config {
      // Needed for external IP
    }
  }

  guest_accelerator {
    type  = "nvidia-l4"
    count = 1
  }
  
  # Enable the startup script
  metadata_startup_script = file("startup.sh")
    
  metadata = {
    # enable-oslogin = "TRUE"
    install-nvidia-driver = "TRUE"
    ssh-keys = "ubuntu:${file("~/.ssh/id_rsa.pub")}"
  }

  scheduling {
    on_host_maintenance = "TERMINATE"
    automatic_restart   = false
    provisioning_model  = "STANDARD"
  }

  service_account {
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

resource "google_compute_firewall" "allow-ssh-http" {
  name    = "allow-ssh-http"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22", "80", "8080", "5000", "8000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["gemma-server"]
}


# --- Google Cloud Logging Setup ---

# 1. Enable the Cloud Logging API
resource "google_project_service" "logging_api" {
  project = var.project_id
  service = "logging.googleapis.com"
  disable_on_destroy = false # Set to true if you want to disable the API on `terraform destroy`
}

# 2. Create a BigQuery Dataset for analytical logs (for batch processing)
resource "google_bigquery_dataset" "llm_logs_dataset" {
  dataset_id = "llm_detox_logs_dataset"
  project    = var.project_id
  location   = var.region # Or choose a multi-region like "US" or "EU"
  description = "Dataset for LLM detoxification inference and vLLM metrics logs."
  depends_on = [google_project_service.logging_api]
}

# 3. Create a Cloud Storage bucket for long-term log archival
resource "google_storage_bucket" "llm_logs_archive_bucket" {
  name          = "${var.project_id}-llm-detox-logs-archive" # Bucket names must be globally unique
  project       = var.project_id
  location      = var.region
  storage_class = "ARCHIVE" # Cheaper for long-term storage
  force_destroy = false # Set to true to allow deletion of non-empty buckets on `terraform destroy`
  depends_on    = [google_project_service.logging_api]
}

# 4. Create Log Sinks to route specific logs

# Sink for llm-detox-inference-logs to BigQuery
resource "google_logging_project_sink" "inference_logs_to_bigquery" {
  name        = "llm-detox-inference-to-bigquery"
  project     = var.project_id
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.llm_logs_dataset.dataset_id}"
  filter      = "logName=\"projects/${var.project_id}/logs/llm-detox-inference-logs\""

  # Ensure BigQuery dataset exists before creating the sink
  depends_on = [google_bigquery_dataset.llm_logs_dataset]

  # Grant BigQuery data editor role to the sink's writer identity
  # This is crucial for the sink to write logs to BigQuery
  lifecycle {
    create_before_destroy = true
  }
}

resource "google_project_iam_member" "inference_logs_bigquery_writer" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = google_logging_project_sink.inference_logs_to_bigquery.writer_identity
  depends_on = [google_logging_project_sink.inference_logs_to_bigquery]
}


# Sink for vllm-metrics-snapshot-logs to BigQuery
resource "google_logging_project_sink" "metrics_logs_to_bigquery" {
  name        = "vllm-metrics-snapshot-to-bigquery"
  project     = var.project_id
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.llm_logs_dataset.dataset_id}"
  filter      = "logName=\"projects/${var.project_id}/logs/vllm-metrics-snapshot-logs\""

  depends_on = [google_bigquery_dataset.llm_logs_dataset]

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_project_iam_member" "metrics_logs_bigquery_writer" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = google_logging_project_sink.metrics_logs_to_bigquery.writer_identity
  depends_on = [google_logging_project_sink.metrics_logs_to_bigquery]
}

# Sink for llm-detox-inference-logs to Cloud Storage (for archival)
resource "google_logging_project_sink" "inference_logs_to_gcs" {
  name        = "llm-detox-inference-to-gcs"
  project     = var.project_id
  destination = "storage.googleapis.com/${google_storage_bucket.llm_logs_archive_bucket.name}"
  filter      = "logName=\"projects/${var.project_id}/logs/llm-detox-inference-logs\""

  depends_on = [google_storage_bucket.llm_logs_archive_bucket]

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_project_iam_member" "inference_logs_gcs_writer" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = google_logging_project_sink.inference_logs_to_gcs.writer_identity
  depends_on = [google_logging_project_sink.inference_logs_to_gcs]
}

# Sink for vllm-metrics-snapshot-logs to Cloud Storage (for archival)
resource "google_logging_project_sink" "metrics_logs_to_gcs" {
  name        = "vllm-metrics-snapshot-to-gcs"
  project     = var.project_id
  destination = "storage.googleapis.com/${google_storage_bucket.llm_logs_archive_bucket.name}"
  filter      = "logName=\"projects/${var.project_id}/logs/vllm-metrics-snapshot-logs\""

  depends_on = [google_storage_bucket.llm_logs_archive_bucket]

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_project_iam_member" "metrics_logs_gcs_writer" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = google_logging_project_sink.metrics_logs_to_gcs.writer_identity
  depends_on = [google_logging_project_sink.metrics_logs_to_gcs]
}
