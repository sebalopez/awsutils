__author__ = 'slopez'

import sys
import boto3
from botocore.exceptions import ClientError
import boto3_clients as clients

session = boto3.Session(profile_name='prod', region_name='us-east-1')
autoscaling = session.client('autoscaling')
ec2 = session.client('ec2')

class ASG (object):

    def __init__(self, name):
        try:
            response = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[name])['AutoScalingGroups'][0]
            self.data = response
            self.name = name
            if 'LaunchTemplate' in self.data.keys():
                self.template = self.data['LaunchTemplate']
            self.instances = self.data['Instances']
            self.tags = { t['Key']: t['Value'] for t in self.data.get('Tags', []) }
        except ClientError as e:
            print e
            return None

    def stop(self):
        print 'Stopping AutoScaling Group',self.name
        autoscaling.suspend_processes(
            AutoScalingGroupName=self.name,
            ScalingProcesses=['Launch','Terminate']
        )
        print 'Suspended launch and termination processes'
        for instance in self.instances:
            try:
                ec2.stop_instances(InstanceIds=[instance['InstanceId']])
                print 'Stopped instance',instance['InstanceId']
            except ClientError as e:
                print 'Unable to stop instance',instance['InstanceId'],e

    def start(self):
        print 'Restarting AutoScaling Group',self.name
        for instance in self.instances:
            try:
                ec2.start_instances(InstanceIds=[instance['InstanceId']])
                print 'Started instance',instance['InstanceId']
            except ClientError as e:
                print 'Unable to start instance',instance['InstanceId'],e
        
    def resume(self):
        autoscaling.resume_processes(
            AutoScalingGroupName=self.name,
            ScalingProcesses=['Launch','Terminate']
        )
        print 'Resumed launch and termination processes'

    def set_template(self, template_name):
        autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=self.name,
            LaunchTemplate={
                'LaunchTemplateName': template_name,
                'Version': '$Latest'
            }
        )
        print 'Updated Group %s with latest version of template %s' %(self.name, template_name)


def find_asg(environment):
    for group in autoscaling.describe_auto_scaling_groups()['AutoScalingGroups']:
            if filter(lambda tag: tag['Value'].lower() == environment.lower(), group['Tags']):
                ASG(group['AutoScalingGroupName']).stop()
             

if __name__ == '__main__':
    if sys.argv[1] == 'stop':
        #find_asg('dev')
        ASG('dev-rediselk-asg').stop()