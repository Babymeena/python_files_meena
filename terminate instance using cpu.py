import boto3
from datetime import datetime, timedelta, timezone

ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
low_cpu_threshold = 5.0  # percent

# Step 1: Get running Dev instances
response = ec2.describe_instances(
    Filters=[
        {'Name': 'instance-state-name', 'Values': ['running']},
        {'Name': 'tag:Environment', 'Values': ['Dev']}
    ]
)

instances_to_terminate = []

# Step 2: Loop through instances
for reservation in response['Reservations']:
    for instance in reservation['Instances']:
        instance_id = instance['InstanceId']
        launch_time = instance['LaunchTime']

        if launch_time >= cutoff_time:
            continue  # Not running for more than 2 hours

        # Step 3: Get average CPU over last 2 hours
        metric = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': instance_id}
            ],
            StartTime=datetime.now(timezone.utc) - timedelta(hours=1),
            EndTime=datetime.now(timezone.utc),
            Period=3600,
            Statistics=['Average']
        )

        datapoints = metric['Datapoints']
        if not datapoints:
            print(f"No CPU data for {instance_id}, skipping...")
            continue

        avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints)

        if avg_cpu < low_cpu_threshold:
            print(f"Instance {instance_id} is IDLE (Avg CPU: {avg_cpu:.2f}%) — marking for termination")
            instances_to_terminate.append(instance_id)
        else:
            print(f"Instance {instance_id} is ACTIVE (Avg CPU: {avg_cpu:.2f}%) — keeping it")

# Step 4: Terminate instances
if instances_to_terminate:
    print(f"Terminating unused instances: {instances_to_terminate}")
    ec2.terminate_instances(InstanceIds=instances_to_terminate)
else:
    print("No unused instances found for termination.")
