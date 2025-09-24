import boto3
from botocore.exceptions import BotoCoreError, ClientError


# Notes: Agent responsible for handling uploads
# (and optionally downloads) to AWS S3.
class S3StorageAgent:
    def __init__(
        self,
        aws_access_key_id,
        aws_secret_access_key,
        region_name,
        bucket_name,
        logger=None,
    ):
        """
        Notes:
        - Initializes the S3 client using provided AWS credentials and region.
        - Stores the target bucket name and optional logger.
        """
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.bucket_name = bucket_name
        self.logger = logger
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
        )

    def upload_file(self, local_path, s3_key):
        """
        Notes:
        - Uploads a local file to the configured S3 bucket under
        the given key (path in the bucket).
        - Logs success or error if a logger is provided.
        - Returns True on success, False on failure.
        """
        try:
            self.s3.upload_file(local_path, self.bucket_name, s3_key)
            if self.logger:
                self.logger.info(f"File uploaded to s3://{self.bucket_name}/{s3_key}")
            return True
        except (BotoCoreError, ClientError) as error:
            if self.logger:
                self.logger.error(f"Failed to upload file to S3: {error}")
            return False
