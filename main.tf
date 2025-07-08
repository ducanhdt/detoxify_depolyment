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

# Output the external IP address for easy SSH access
output "vm_external_ip" {
  description = "External IP address of the VM"
  value       = google_compute_instance.gemma_l4_vm.network_interface[0].access_config[0].nat_ip
}