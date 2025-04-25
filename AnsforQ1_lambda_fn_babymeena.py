import boto3
import os
from datetime import datetime, timedelta, timezone

# Initialize boto3 clients OUTSIDE the handler (better performance)
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')
# ses = boto3.client('ses')  # Uncomment if using SES email notifications

# Environment Variables (configure in Lambda console)
ENVIRONMENT_TAG = os.getenv('ENVIRONMENT_TAG', 'Dev')
CPU_THRESHOLD = float(os.getenv('CPU_THRESHOLD', 5.0))  # in %
AGE_THRESHOLD_DAYS = int(os.getenv('AGE_THRESHOLD_DAYS', 7))
# SOURCE_EMAIL = os.getenv('SOURCE_EMAIL')  # For SES, if needed

def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(days=AGE_THRESHOLD_DAYS)
    instances_to_terminate = []

    print("Fetching running instances tagged as Environment =", ENVIRONMENT_TAG)

    paginator = ec2.get_paginator('describe_instances')
    page_iterator = paginator.paginate(
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['running']},
            {'Name': 'tag:Environment', 'Values': [ENVIRONMENT_TAG]}
        ]
    )

    for page in page_iterator:
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                launch_time = instance['LaunchTime']
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                # owner_email = tags.get('OwnerEmail')  # Optional for SES email

                if launch_time >= cutoff_time:
                    print(f"Instance {instance_id} is recently launched — skipping.")
                    continue

                # Check CPU Utilization
                metric = cloudwatch.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                    StartTime=now - timedelta(days=AGE_THRESHOLD_DAYS),
                    EndTime=now,
                    Period=86400,  # Daily
                    Statistics=['Average']
                )

                datapoints = metric.get('Datapoints', [])
                if not datapoints:
                    print(f"No CPU data for {instance_id}, skipping...")
                    continue

                avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints)

                if avg_cpu < CPU_THRESHOLD:
                    print(f"Instance {instance_id} is IDLE (Avg CPU: {avg_cpu:.2f}%) — marking for termination.")
                    instances_to_terminate.append(instance_id)

                    # Optional: Create AMI or send email here

                else:
                    print(f"Instance {instance_id} is ACTIVE (Avg CPU: {avg_cpu:.2f}%) — keeping it.")

    # Terminate idle instances
    if instances_to_terminate:
        print(f"Terminating instances: {instances_to_terminate}")
        ec2.terminate_instances(InstanceIds=instances_to_terminate)
    else:
        print("No idle instances found for termination.")

    return {
        'statusCode': 200,
        'body': f"Checked instances. Terminated: {instances_to_terminate if instances_to_terminate else 'None'}"
    }
