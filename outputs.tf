output "vm_ip" {
  value = google_compute_instance.gemma_l4_vm.network_interface[0].access_config[0].nat_ip
  description = "Public IP of the VM"
}
output "project_id" {
  value = var.project_id
  description = "GCP Project ID"
}
output "region" {
  value = var.region
  description = "GCP Region"
}
output "zone" {
  value = var.zone
  description = "GCP Zone"
}