import boto3
import json
import logging
from datetime import datetime
from botocore.exceptions import ClientError


class WorkflowLogManager:
    """
    Logging for complete workflows: workflow_log/{run_id}.json
    Appends log events and errors.
    """

    def __init__(self, bucket_name):
        self.s3 = boto3.client("s3")
        self.bucket = bucket_name

    def _object_key(self, run_id):
        return f"workflow_log/{run_id}.json"

    def append_log(self, run_id, step, message, event_id=None, error=None):
        """
        Append a log entry to the workflow log (including error info).
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "step": step,
            "message": message,
            "event_id": event_id,
        }
        if error:
            log_entry["error"] = str(error)

        # Load existing log, extend, write back
        try:
            try:
                response = self.s3.get_object(
                    Bucket=self.bucket, Key=self._object_key(run_id)
                )
                log_list = json.loads(response["Body"].read())
            except self.s3.exceptions.NoSuchKey:
                log_list = []

            log_list.append(log_entry)
            self.s3.put_object(
                Bucket=self.bucket,
                Key=self._object_key(run_id),
                Body=json.dumps(log_list),
            )
            logging.info(f"Workflow log updated: {run_id}, Step: {step}")
        except ClientError as e:
            logging.error(f"Error in workflow logging: {e}")
            raise


# Example:
# wlm = WorkflowLogManager("my-bucket")
# wlm.append_log("run42", "start", "Workflow started", event_id="evt123")
