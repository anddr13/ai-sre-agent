# EC2 machines for the backtest, each with the same kind stand as the laptop (voting-infra-local), so several
# backtests run at once with the scenarios unchanged and results that compare with the local ones.
# cloud/stands.sh drives it (see cloud/README.md). Local state: a short-lived lab; `stands.sh leftovers` finds
# anything that outlived it by tag.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.70"
    }
  }
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-north-1"
}

variable "stands" {
  description = "Number of machines, one stand and one backtest each."
  type        = number
  default     = 3
}

variable "instance_type" {
  description = "On-Demand (this account's organization SCP denies Spot). The kind stand uses 7-9 GiB, the runner ~1 GiB."
  type        = string
  default     = "m6i.2xlarge"
}

variable "ssh_public_key" {
  description = "Public key for the ubuntu user (stands.sh passes ~/.ssh/ai-sre-stands.pub)."
  type        = string
}

variable "ssh_cidr" {
  description = "The only source allowed to SSH in: the laptop's public IP as /32 (stands.sh looks it up)."
  type        = string
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project    = "ai-sre-agent"
      purpose    = "backtest-stands"
      managed-by = "terraform"
    }
  }
}

locals {
  name = "ai-sre-stands"
}

data "aws_availability_zones" "available" {
  state = "available"
}

# Ubuntu 24.04: Docker, kind and the rest come from cloud-init.yaml.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# A VPC of its own with one public subnet: no NAT gateway, and nothing open but SSH from the laptop.
resource "aws_vpc" "this" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = local.name
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = local.name
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.this.id
  availability_zone       = data.aws_availability_zones.available.names[0]
  cidr_block              = cidrsubnet(aws_vpc.this.cidr_block, 8, 0)
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.name}-public"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = {
    Name = "${local.name}-public"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "stand" {
  name        = local.name
  description = "SSH from the laptop only; the stand itself listens on 127.0.0.1"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }

  egress {
    description = "Images, GitHub, the LLM API"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_key_pair" "this" {
  key_name   = local.name
  public_key = var.ssh_public_key
}

resource "aws_instance" "stand" {
  count = var.stands

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.stand.id]
  key_name               = aws_key_pair.this.key_name
  user_data              = file("${path.module}/cloud-init.yaml")

  # IMDSv2 only.
  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 80
    delete_on_termination = true
  }

  tags = {
    Name = "${local.name}-${count.index + 1}"
  }
}

output "ips" {
  description = "Public IPs, stand 1 first."
  value       = aws_instance.stand[*].public_ip
}
