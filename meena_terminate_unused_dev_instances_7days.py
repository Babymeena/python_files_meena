import boto3
from datetime import datetime, timedelta, timezone

# Initialize clients
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')
#ses = boto3.client('ses')  # For sending email (optional)

# Set time thresholds
cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
low_cpu_threshold = 5.0  # percentage

# Step 1: Get running instances with tag Environment=Dev
response = ec2.describe_instances(
    Filters=[
        {'Name': 'instance-state-name', 'Values': ['running']},
        {'Name': 'tag:Environment', 'Values': ['Dev']}
    ]
)

instances_to_terminate = []

# Step 2: Evaluate each instance
for reservation in response['Reservations']:
    for instance in reservation['Instances']:
        instance_id = instance['InstanceId']
        launch_time = instance['LaunchTime']

        '''

        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        owner_email = tags.get('OwnerEmail') #optionl tag for sending email

        '''
        if launch_time >= cutoff_time:
            continue  # Instance is not old enough

        # Step 3: Get CloudWatch CPU Utilization (last 7 days)
        metric = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': instance_id}
            ],
            StartTime=datetime.now(timezone.utc) - timedelta(days=7),
            EndTime=datetime.now(timezone.utc),
            Period=86400,  # One data point per day
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

            '''

            # Create AMI snapshot before terminating (Optional)

            ami_name = f"Backup-{instance_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            try:
                ami_response = ec2.create_image(
                    InstanceId=instance_id,
                    Name=ami_name,
                    NoReboot=True,
                    Description=f"Snapshot before terminating instance {instance_id}"
                )
                print(f"AMI {ami_response['ImageId']} created for instance {instance_id}")
            except Exception as e:
                print(f"Failed to create AMI for {instance_id}: {str(e)}")
                continue  # skip termination if AMI creation fails
                

            # Send email before termination (if owner email is tagged) this is also optional
            if owner_email:
                try:
                    ses.send_email(
                        Source='your-verified-email@example.com',
                        Destination={'ToAddresses': [owner_email]},
                        Message={
                            'Subject': {'Data': f'AWS Notification: Termination of Instance {instance_id}'},
                            'Body': {
                                'Text': {
                                    'Data': (
                                        f"Hello,\n\n"
                                        f"The EC2 instance {instance_id} (tagged as 'Dev') has been running idle "
                                        f"for over 7 days with low CPU usage.\n\n"
                                        f"An AMI snapshot has been taken: {ami_name}.\n"
                                        f"This instance is now being terminated to reduce cost.\n\n"
                                        f"Regards,\nAWS Automation Script"
                                    )
                                }
                            }
                        }
                    )
                    print(f"Email sent to {owner_email} regarding termination of {instance_id}")
                except Exception as e:
                    print(f"Failed to send email to {owner_email} for {instance_id}: {str(e)}")

                
            '''

            instances_to_terminate.append(instance_id)


        else:
            print(f"Instance {instance_id} is ACTIVE (Avg CPU: {avg_cpu:.2f}%) — keeping it")



# Step 4: Terminate unused instances
if instances_to_terminate:
    print(f"Terminating unused instances: {instances_to_terminate}")
    ec2.terminate_instances(InstanceIds=instances_to_terminate)
else:
    print("No unused Dev instances found to terminate.")
