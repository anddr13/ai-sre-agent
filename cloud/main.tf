# GCE machines for the backtest, each with the same kind stand as the laptop (voting-infra-local), so several
# backtests run at once with the scenarios unchanged and results that compare with the local ones.
# cloud/stands.sh drives it (see cloud/README.md). Local state: a short-lived lab; `stands.sh leftovers` finds
# anything that outlived it by label.

terraform {
  required_version = ">= 1.10"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.8"
    }
  }
}

variable "project_id" {
  description = "GCP project ID (with billing enabled)."
  type        = string
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "europe-central2"
}

variable "zone" {
  description = "Zone of the machines."
  type        = string
  default     = "europe-central2-a"
}

variable "stands" {
  description = "Number of machines, one stand and one backtest each."
  type        = number
  default     = 3
}

variable "machine_type" {
  description = "Not Spot: a reclaimed machine would lose a 3-hour backtest. The kind stand uses 7-9 GiB, the runner ~1 GiB."
  type        = string
  default     = "e2-standard-8"
}

variable "ssh_public_key" {
  description = "Public key for the ubuntu user (stands.sh passes ~/.ssh/ai-sre-stands.pub)."
  type        = string
}

variable "ssh_cidr" {
  description = "The only source allowed to SSH in: the laptop's public IP as /32 (stands.sh looks it up)."
  type        = string
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  default_labels = {
    project    = "ai-sre-agent"
    purpose    = "backtest-stands"
    managed-by = "terraform"
  }
}

locals {
  name = "ai-sre-stands"
}

# A network of its own: nothing open but SSH from the laptop. The stand listens on 127.0.0.1 of the machine.
resource "google_compute_network" "this" {
  name                    = local.name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "this" {
  name          = local.name
  network       = google_compute_network.this.id
  ip_cidr_range = "10.42.0.0/24"
}

resource "google_compute_firewall" "ssh" {
  name          = "${local.name}-ssh"
  network       = google_compute_network.this.id
  direction     = "INGRESS"
  source_ranges = [var.ssh_cidr]
  target_tags   = [local.name]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_instance" "stand" {
  count = var.stands

  name         = "${local.name}-${count.index + 1}"
  machine_type = var.machine_type
  tags         = [local.name]

  boot_disk {
    initialize_params {
      # Ubuntu 24.04: Docker, kind and the rest come from cloud-init.yaml.
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = 80
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.this.id
    # An ephemeral public IP: the machines pull images and talk to GitHub and the LLM API, no Cloud NAT needed.
    access_config {}
  }

  metadata = {
    user-data              = file("${path.module}/cloud-init.yaml")
    ssh-keys               = "ubuntu:${var.ssh_public_key}"
    block-project-ssh-keys = "true"
    enable-oslogin         = "FALSE"
  }

  # No service account: nothing on the machine needs the GCP API.
}

output "ips" {
  description = "Public IPs, stand 1 first, one per line."
  value       = join("\n", google_compute_instance.stand[*].network_interface[0].access_config[0].nat_ip)
}
