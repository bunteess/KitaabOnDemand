# Nightly database dumps, copied off the server by the backup-ship service
# (infra/backup/ship.sh). A separate bucket and user from the API's: the
# backup user can add dumps but never read or delete them, so a compromised
# server cannot destroy its own backups.
resource "aws_s3_bucket" "backups" {
  bucket = var.backup_bucket_name
}

resource "aws_s3_bucket_ownership_controls" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Versioning keeps the original if a dump is ever overwritten.
resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-old-dumps"
    status = "Enabled"

    filter {}

    expiration {
      days = var.backup_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.backup_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_upload_days
    }
  }

  rule {
    id     = "remove-expired-delete-markers"
    status = "Enabled"

    filter {}

    expiration {
      expired_object_delete_marker = true
    }
  }

  depends_on = [aws_s3_bucket_versioning.backups]
}

data "aws_iam_policy_document" "backups_tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.backups.arn,
      "${aws_s3_bucket.backups.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "backups" {
  bucket = aws_s3_bucket.backups.id
  policy = data.aws_iam_policy_document.backups_tls_only.json

  depends_on = [aws_s3_bucket_public_access_block.backups]
}

# `aws s3 sync` lists the bucket to find dumps it has not uploaded yet.
data "aws_iam_policy_document" "backup_upload" {
  statement {
    sid       = "List"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.backups.arn]
  }

  statement {
    sid = "AddDumps"
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${aws_s3_bucket.backups.arn}/postgres/*"]
  }
}

resource "aws_iam_policy" "backup_upload" {
  name        = "kitaabondemand-${var.environment}-backup-upload"
  description = "KitaabOnDemand backup-ship: add database dumps, nothing else"
  policy      = data.aws_iam_policy_document.backup_upload.json
}

# Its access key is created in the console, like the API user's (docs/DEPLOY.md).
resource "aws_iam_user" "backup" {
  name = "kitaabondemand-${var.environment}-backup"
}

resource "aws_iam_user_policy_attachment" "backup_upload" {
  user       = aws_iam_user.backup.name
  policy_arn = aws_iam_policy.backup_upload.arn
}
