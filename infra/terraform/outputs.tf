output "bucket_name" {
  description = "Set S3_BUCKET to this."
  value       = aws_s3_bucket.uploads.bucket
}

output "region" {
  description = "Set S3_REGION to this."
  value       = var.region
}

output "api_user_name" {
  description = "Create an access key for this user in the IAM console (docs/DEPLOY.md)."
  value       = aws_iam_user.api.name
}

output "api_policy_arn" {
  description = "Attach to an EC2 instance role instead of using the user, if the server runs on AWS."
  value       = aws_iam_policy.api_storage.arn
}
