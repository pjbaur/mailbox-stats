"""Google Cloud Storage upload utility for gmail_stats.

Provides functions to upload local files and directories to GCS buckets.
Only imports google-cloud-storage when actually used to avoid requiring
the dependency for local-only usage.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

log = logging.getLogger("gmail_stats.gcs")

# Lazy-loaded GCS client
_gcs_client = None


def _get_gcs_client():
    """Lazy-load the GCS client to avoid import errors when not using GCS."""
    global _gcs_client
    if _gcs_client is None:
        try:
            from google.cloud import storage
            _gcs_client = storage.Client()
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS uploads. "
                "Install with: pip install google-cloud-storage"
            )
    return _gcs_client


def parse_gcs_uri(gcs_uri: str) -> tuple:
    """Parse a GCS URI into bucket name and blob prefix.

    Args:
        gcs_uri: GCS URI (e.g., gs://bucket/path/prefix)

    Returns:
        Tuple of (bucket_name, blob_prefix)

    Raises:
        ValueError: If URI doesn't start with gs://
    """
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI (must start with gs://): {gcs_uri}")

    path = gcs_uri[5:]  # Remove 'gs://'
    parts = path.split("/", 1)
    bucket_name = parts[0]
    blob_prefix = parts[1] if len(parts) > 1 else ""
    return bucket_name, blob_prefix


def upload_to_gcs(local_path: Path, gcs_uri: str) -> str:
    """Upload a local file to GCS.

    Args:
        local_path: Path to local file
        gcs_uri: Full GCS URI for the destination (e.g., gs://bucket/path/file.csv)

    Returns:
        The GCS URI of the uploaded file
    """
    bucket_name, blob_name = parse_gcs_uri(gcs_uri)

    # If blob_name is empty or ends with /, use the local filename
    if not blob_name or blob_name.endswith("/"):
        blob_name = blob_name + local_path.name

    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    log.debug("Uploading %s to gs://%s/%s", local_path, bucket_name, blob_name)
    blob.upload_from_filename(str(local_path))

    return f"gs://{bucket_name}/{blob_name}"


def upload_directory_to_gcs(local_dir: Path, gcs_base_uri: str) -> List[str]:
    """Upload all files in a directory to GCS.

    Args:
        local_dir: Local directory path
        gcs_base_uri: Base GCS URI (e.g., gs://bucket/reports/2025-01-01_1200)
                      Files will be uploaded as gs://bucket/reports/2025-01-01_1200/filename

    Returns:
        List of uploaded GCS URIs
    """
    if not local_dir.is_dir():
        raise ValueError(f"Not a directory: {local_dir}")

    bucket_name, base_prefix = parse_gcs_uri(gcs_base_uri)
    # Ensure prefix ends with / for proper path joining
    if base_prefix and not base_prefix.endswith("/"):
        base_prefix = base_prefix + "/"

    uploaded = []
    for file_path in sorted(local_dir.iterdir()):
        if file_path.is_file():
            blob_name = base_prefix + file_path.name
            gcs_uri = f"gs://{bucket_name}/{blob_name}"
            uploaded.append(upload_to_gcs(file_path, gcs_uri))

    log.info("Uploaded %d files to gs://%s/%s", len(uploaded), bucket_name, base_prefix)
    return uploaded
