output "vm_ip" {
  value = google_compute_instance.gemma_l4_vm.network_interface[0].access_config[0].nat_ip
  description = "Public IP of the VM"
}