"""Test configuration.

Integration tests use the Postgres, Redis and MinIO started by `make deps-up`.
Environment variables are set before any kitaab module reads settings.
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://kitaab:kitaab@localhost:5432/kitaab_test"
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["S3_ENDPOINT_URL"] = os.environ.get("TEST_S3_ENDPOINT_URL", "http://localhost:9000")
os.environ["S3_PUBLIC_ENDPOINT_URL"] = os.environ["S3_ENDPOINT_URL"]
os.environ["S3_BUCKET"] = os.environ.get("TEST_S3_BUCKET", "kitaab-test")
# Always the local MinIO credentials: tests must never reach real AWS.
os.environ["AWS_ACCESS_KEY_ID"] = os.environ.get("TEST_AWS_ACCESS_KEY_ID", "kitaab-minio")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ.get(
    "TEST_AWS_SECRET_ACCESS_KEY", "kitaab-minio-secret"
)
os.environ["DEV_TOOLS_ENABLED"] = "true"
