import boto3
from datetime import datetime, timezone, timedelta

ec2 = boto3.client('ec2')

seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

response = ec2.describe_instances(
    Filters=[
        {"Name": "tag:Environment", "Values": ["Dev"]},
        {"Name": "instance-state-name", "Values": ["running"]}
    ]
)

old_instances = []

for reservation in response["Reservations"]:
    for instance in reservation["Instances"]:
        launch_time = instance["LaunchTime"]
        if launch_time < seven_days_ago:
            old_instances.append(instance["InstanceId"])

if old_instances:
    print(f"Terminating instances: {old_instances}")
    ec2.terminate_instances(InstanceIds=old_instances)
else:
    print("No instances found older than 7 days.")
