import boto3
from datetime import datetime, timezone, timedelta

# Create an EC2 client
ec2 = boto3.client('ec2')

# Define the cutoff time (2 hours ago)
cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)

# Filter instances that are running and tagged with Environment=Dev
response = ec2.describe_instances(
    Filters=[
        {'Name': 'tag:Environment', 'Values': ['Dev']},
        {'Name': 'instance-state-name', 'Values': ['running']}
    ]
)

# Store instances to terminate
instances_to_terminate = []

# Loop through instances
for reservation in response['Reservations']:
    for instance in reservation['Instances']:
        launch_time = instance['LaunchTime']
        instance_id = instance['InstanceId']
        name_tag = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), 'Unnamed')

        # Check if instance is older than 2 hours
        if launch_time < cutoff_time:
            print(f"Instance {instance_id} ({name_tag}) launched at {launch_time} is older than 2 hours.")
            instances_to_terminate.append(instance_id)
        else:
            print(f"Instance {instance_id} ({name_tag}) is NOT older than 2 hours.")

# Terminate if any found
if instances_to_terminate:
    print(f"Terminating instances: {instances_to_terminate}")
    ec2.terminate_instances(InstanceIds=instances_to_terminate)
else:
    print("No instances found that are older than 2 hours.")
