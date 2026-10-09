variable "region" {
  description = "AWS region for the upload bucket. Mumbai is the closest to Pakistan."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "staging or production"
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "bucket_name" {
  description = "Globally unique bucket name, for example kitaabondemand-uploads-prod."
  type        = string
}

variable "portal_origins" {
  description = "Portal origins allowed to read files from the browser, for example [\"https://portal.example.pk\"]."
  type        = list(string)
}

variable "abort_incomplete_upload_days" {
  description = "Abandoned multipart uploads are removed after this many days (matches the API's development setting)."
  type        = number
  default     = 2
}

variable "noncurrent_version_days" {
  description = "Old versions of overwritten objects are removed after this many days. The purge job deletes every version itself; this is the safety net."
  type        = number
  default     = 7
}

variable "backup_bucket_name" {
  description = "Globally unique bucket name for database dumps, for example kitaabondemand-backups-prod."
  type        = string
}

variable "backup_retention_days" {
  description = "Database dumps in S3 are deleted after this many days."
  type        = number
  default     = 35
}
