import os
import logging
import boto3
from datetime import datetime
import sys


# Note: This function sets up the logger to write both to a file (with timestamp in /tmp)
# and to stdout for real-time feedback in CI environments.
def setup_logger():
    log_filename = f'polling_trigger_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    log_filepath = os.path.join("/tmp", log_filename)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_filepath), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger(__name__), log_filepath


# Note: This function uploads the logfile to an AWS S3 bucket using credentials
# and bucket name provided via environment variables (set in the GitHub Actions workflow).
def upload_log_to_s3(log_filepath):
    try:
        aws_key = os.environ["AWS_ACCESS_KEY_ID"]
        aws_secret = os.environ["AWS_SECRET_ACCESS_KEY"]
        aws_region = os.environ["AWS_DEFAULT_REGION"]
        bucket_name = os.environ["S3_BUCKET_NAME"]
    except KeyError as e:
        print(f"Missing AWS config or bucket env var: {e}")
        return

    s3_key = f"logs/{os.path.basename(log_filepath)}"
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region,
        )
        s3.upload_file(log_filepath, bucket_name, s3_key)
        print(f"Log uploaded to s3://{bucket_name}/{s3_key}")
    except Exception as ex:
        print(f"Log upload to S3 failed: {ex}")


# Note: This is the main entry point for the polling script.
# It reads configuration from environment variables, runs the job logic, and handles logging and cleanup.
def main():
    logger, log_filepath = setup_logger()
    logger.info("Polling Trigger started.")

    # Note: Read lookahead and lookback parameters from environment variables.
    lookahead_days = int(os.environ.get("CAL_LOOKAHEAD_DAYS", 14))
    lookback_days = int(os.environ.get("CAL_LOOKBACK_DAYS", 1))
    logger.info(f"Lookback: {lookback_days} days, Lookahead: {lookahead_days} days")

    # Note: Place your actual polling/data processing logic here.
    # This is where you would implement the main functionality of your polling job.
    try:
        logger.info("Start polling job.")
        # --- Begin custom business logic ---
        # Example: simulate a data fetch or operation
        # result = fetch_data(lookback_days, lookahead_days)
        logger.info("Polling job finished successfully.")
        # --- End custom business logic ---
    except Exception as e:
        logger.error(f"Error during polling job: {e}", exc_info=True)
        raise
    finally:
        # Note: Always upload the log file to S3 at the end of the script, even if exceptions occur.
        upload_log_to_s3(log_filepath)
        logger.info("Logfile uploaded to S3 (if configured).")


# Note: Standard Python entry point. Calls the main() function.
if __name__ == "__main__":
    main()
