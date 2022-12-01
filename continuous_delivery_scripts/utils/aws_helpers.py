#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Helpers for interacting with AWS services such as S3.

Based on the Python SDK called BOTO https://aws.amazon.com/sdk-for-python/.
"""
import boto3
import logging
import os
from pathlib import Path
import mimetypes
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration

from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def _get_aws_config() -> Tuple[str, dict]:
    s3_region = configuration.get_value("AWS_DEFAULT_REGION")
    s3_config = {
        "aws_access_key_id": configuration.get_value("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": configuration.get_value("AWS_SECRET_ACCESS_KEY"),
    }
    return s3_region, s3_config


def upload_file(file: Path, bucket_dir: Optional[str], bucket_name: str) -> None:
    """Uploads a file onto AWS S3.

    Args:
        file: path to the file to upload
        bucket_dir: name of the folder where to put the file in S3 bucket
        bucket_name: name of the bucket to target
    """
    if not bucket_name:
        bucket_name = str(configuration.get_value(ConfigurationVariable.AWS_BUCKET))
    logger.info(f"Uploading {file} to AWS")
    if not file.exists():
        raise FileNotFoundError(file)
    s3_region, s3_config = _get_aws_config()
    client = boto3.client("s3", **s3_config)
    dest_filename = file.name
    key = f"{bucket_dir}/{dest_filename}"
    extension = "".join(file.suffixes)
    bucket = bucket_name
    client.upload_file(
        str(file),
        bucket,
        key,
        ExtraArgs={"ContentType": mimetypes.types_map.get(extension, "application/octet-stream")} if extension else {},
    )
    # Ensures the file is publicly available and reachable
    # by anyone having access to the bucket.
    client.put_object_acl(ACL="public-read", Bucket=bucket, Key=key)


def _upload_directory_file_contents(bucket_name: str, files: List[str], bucket_dir: str, root: str) -> None:
    for name in files:
        upload_file(Path(root).joinpath(name), bucket_dir, bucket_name)


def _upload_directory_directories(bucket_name: str, dirs: List[str], bucket_dir: str, root: str) -> None:
    for name in dirs:
        upload_directory(Path(root).joinpath(name), bucket_dir, bucket_name)


def _determine_destination(bucket_dir: str, real_dir_path: Path, current_folder: Path) -> str:
    if current_folder != real_dir_path:
        bucket_dest = str(Path(bucket_dir).joinpath(current_folder.relative_to(real_dir_path)))
    else:
        bucket_dest = bucket_dir

    return bucket_dest.replace(os.sep, "/")


def upload_directory(dir: Path, bucket_dir: str, bucket_name: str) -> None:
    """Uploads the contents of a directory (recursively) onto AWS S3.

    Args:
        dir: folder to upload
        bucket_dir: name of the folder where to put the directory contents in S3 bucket
        bucket_name: name of the bucket to target
    """
    if not bucket_name:
        bucket_name = str(configuration.get_value(ConfigurationVariable.AWS_BUCKET))
    logger.info(f"Uploading {dir} to AWS")
    if not dir.exists():
        raise FileNotFoundError(dir)
    if dir.is_file():
        upload_file(dir, bucket_dir, bucket_name)
        return

    def onerror(exception: Exception) -> None:
        logger.error(exception)

    real_dir_path = dir.resolve()
    for root, dirs, files in os.walk(str(real_dir_path), followlinks=True, onerror=onerror):
        new_bucket_dir = _determine_destination(bucket_dir, real_dir_path, Path(root))
        _upload_directory_directories(bucket_name, dirs, new_bucket_dir, root)
        _upload_directory_file_contents(bucket_name, files, new_bucket_dir, root)
