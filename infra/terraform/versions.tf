terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # State stays local until the owner chooses a remote backend (docs/DEPLOY.md).
  # It holds no secrets: no access keys are created here.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "kitaabondemand"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
