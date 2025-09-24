import boto3
import json
import logging
from botocore.exceptions import ClientError
from datetime import datetime


class EventLogManager:
    """
    Manages event logs in S3: events/{event_id}.json
    """

    def __init__(self, bucket_name):
        self.s3 = boto3.client("s3")
        self.bucket = bucket_name

    def _object_key(self, event_id):
        return f"events/{event_id}.json"

    def write_event_log(self, event_id, data):
        """
        Write or update the event log in the S3 bucket.
        """
        data["last_updated"] = datetime.utcnow().isoformat()
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=self._object_key(event_id),
                Body=json.dumps(data),
            )
            logging.info(f"Event log written: {event_id}")
        except ClientError as e:
            logging.error(f"Error writing event log: {e}")
            raise

    def read_event_log(self, event_id):
        """
        Read the event log from S3. Returns None if not found.
        """
        try:
            response = self.s3.get_object(
                Bucket=self.bucket, Key=self._object_key(event_id)
            )
            return json.loads(response["Body"].read())
        except self.s3.exceptions.NoSuchKey:
            logging.warning(f"No event log found for {event_id}.")
            return None
        except ClientError as e:
            logging.error(f"Error reading event log: {e}")
            raise

    def delete_event_log(self, event_id):
        """
        Delete the event log from S3.
        """
        try:
            self.s3.delete_object(
                Bucket=self.bucket, Key=self._object_key(event_id)
            )
            logging.info(f"Event log deleted: {event_id}")
        except ClientError as e:
            logging.error(f"Error deleting event log: {e}")
            raise


# Example:
# manager = EventLogManager("my-bucket")
# manager.write_event_log("123", {"status": "done"})
