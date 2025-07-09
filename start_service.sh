#!/bin/bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required files exist
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if [[ ! -f "credentials.json" ]]; then
        print_error "credentials.json not found. Please ensure your GCP service account key is in place."
        exit 1
    fi
    
    if [[ ! -f "terraform.tfvars" ]]; then
        print_error "terraform.tfvars not found. Please create it with your project configuration."
        exit 1
    fi
    
    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed. Please install Terraform first."
        exit 1
    fi
    

    
    print_success "Prerequisites check passed!"
}

# Initialize Terraform if needed
init_terraform() {
    print_status "Initializing Terraform..."
    
    if [[ ! -d ".terraform" ]]; then
        terraform init
        print_success "Terraform initialized!"
    else
        print_status "Terraform already initialized, skipping..."
    fi
}

# Plan and apply Terraform
apply_terraform() {
    print_status "Creating Terraform plan..."
    terraform plan -out=tfplan
    
    print_status "Reviewing plan summary..."
    terraform show -no-color tfplan | grep -E "^Plan:|will be created|will be destroyed|will be updated"
    
    echo ""
    read -p "Do you want to apply this plan? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Applying Terraform configuration..."
        terraform apply tfplan
        
        # Clean up plan file
        rm -f tfplan
        
        print_success "Terraform apply completed successfully!"
    else
        print_warning "Terraform apply cancelled by user."
        rm -f tfplan
        exit 0
    fi
}

# Auto-apply without confirmation (use with caution)
auto_apply_terraform() {
    print_status "Auto-applying Terraform configuration..."
    terraform apply -auto-approve
    print_success "Terraform auto-apply completed successfully!"
}

# Generate .env file from Terraform outputs
generate_env_file() {
    print_status "Generating .env file from Terraform outputs..."
    
    # Create or clear the .env file
    > .env
    
    # Get terraform outputs in standard format
    terraform_outputs=$(terraform output)
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to get Terraform outputs"
        exit 1
    fi
    
    # Extract specific outputs and write to .env
    echo "# Generated automatically by start_service.sh on $(date)" >> .env
    echo "# Terraform outputs" >> .env
    echo "" >> .env
    
    # Parse the key = "value" format from terraform output
    vm_ip=$(echo "$terraform_outputs" | grep '^vm_ip' | sed 's/vm_ip = "\(.*\)"/\1/')
    project_id=$(echo "$terraform_outputs" | grep '^project_id' | sed 's/project_id = "\(.*\)"/\1/')
    zone=$(echo "$terraform_outputs" | grep '^zone' | sed 's/zone = "\(.*\)"/\1/')
    region=$(echo "$terraform_outputs" | grep '^region' | sed 's/region = "\(.*\)"/\1/')
    vm_name=$(echo "$terraform_outputs" | grep '^vm_name' | sed 's/vm_name = "\(.*\)"/\1/')
    
    # Write VM IP and related URLs
    if [[ -n "$vm_ip" ]]; then
        echo "vLLM_API=$vm_ip" >> .env
    fi
    
    # Write project details
    if [[ -n "$project_id" ]]; then
        echo "GCP_PROJECT_ID=$project_id" >> .env
    fi
    if [[ -n "$zone" ]]; then
        echo "ZONE=$zone" >> .env
    fi
    if [[ -n "$region" ]]; then
        echo "REGION=$region" >> .env
    fi
    if [[ -n "$vm_name" ]]; then
        echo "VM_NAME=$vm_name" >> .env
    fi
    

    
    print_success ".env file generated successfully!"
    print_status "Contents of .env file:"
    echo ""
    cat .env
    echo ""
}

# Copy .env to inference directory
copy_env_to_inference() {
    if [[ -d "infernce" ]]; then
        print_status "Copying .env to inference directory..."
        cp .env infernce/.env
        print_success ".env copied to infernce/ directory"
    fi
}

# Main execution
main() {
    print_status "Starting deployment process..."
    echo ""
    
    check_prerequisites
    echo ""
    
    init_terraform
    echo ""
    
    # Check if auto-apply flag is provided
    if [[ "$1" == "--auto" || "$1" == "-a" ]]; then
        auto_apply_terraform
    else
        apply_terraform
    fi
    echo ""
    
    generate_env_file
    echo ""
    
    copy_env_to_inference
    echo ""
    
    print_success "Deployment process completed successfully!"
    print_status "Your infrastructure is ready!"
    
    if [[ -n "$vm_ip" ]]; then
        echo ""
        print_status "You can access your VM at: $vm_ip"
        print_status "SSH command: ssh ubuntu@$vm_ip"
        print_status "Service URL: http://$vm_ip:8000"
    fi
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -a, --auto    Auto-apply terraform without confirmation"
    echo "  -h, --help    Show this help message"
    echo ""
    echo "This script will:"
    echo "  1. Check prerequisites (credentials.json, terraform.tfvars)"
    echo "  2. Initialize Terraform if needed"
    echo "  3. Plan and apply Terraform configuration"
    echo "  4. Generate .env file from Terraform outputs"
    echo "  5. Copy .env to inference directory"
}

# Parse command line arguments
case "$1" in
    -h|--help)
        show_help
        exit 0
        ;;
    -a|--auto)
        main "$1"
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac