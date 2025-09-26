import boto3
import os


def set_bucket_owner_enforced(bucket_name: str):
    s3 = boto3.client("s3")

    ownership_controls = {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}

    print(f"Setting 'Bucket owner enforced' for bucket: {bucket_name} ...")

    response = s3.put_bucket_ownership_controls(
        Bucket=bucket_name, OwnershipControls=ownership_controls
    )
    print("OwnershipControls gesetzt:", response)

    # Verifizieren
    get_response = s3.get_bucket_ownership_controls(Bucket=bucket_name)
    print("Aktuelle OwnershipControls:", get_response)


if __name__ == "__main__":
    bucket_name = (
        os.environ.get("S3_BUCKET_NAME") or "agentic-intelligence-research-logs"
    )
    set_bucket_owner_enforced(bucket_name)
