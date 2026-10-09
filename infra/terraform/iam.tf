# What the API and worker may do with the bucket, and nothing else.
data "aws_iam_policy_document" "api_storage" {
  statement {
    sid = "Bucket"
    actions = [
      "s3:ListBucket",
      "s3:ListBucketVersions",
      "s3:ListBucketMultipartUploads",
    ]
    resources = [aws_s3_bucket.uploads.arn]
  }

  statement {
    sid = "Objects"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
    ]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }
}

resource "aws_iam_policy" "api_storage" {
  name        = "kitaabondemand-${var.environment}-storage"
  description = "KitaabOnDemand API and worker: read and write the upload bucket"
  policy      = data.aws_iam_policy_document.api_storage.json
}

# For a server outside AWS. The owner creates its access key in the console so
# the secret never enters Terraform state (docs/DEPLOY.md). On EC2, attach the
# policy to the instance role instead and delete this user.
resource "aws_iam_user" "api" {
  name = "kitaabondemand-${var.environment}-api"
}

resource "aws_iam_user_policy_attachment" "api_storage" {
  user       = aws_iam_user.api.name
  policy_arn = aws_iam_policy.api_storage.arn
}
