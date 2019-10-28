__author__ = 'sebalopez'
import arn
import datetime
import dateutil.parser
import itertools
import logging
import boto3
import boto3_clients as clients
from botocore.exceptions import ClientError
from dateutil.tz import tzutc

logger = logging.getLogger(__name__)


class Resource(object):

    def __init__(self, obj_id, obj_data):
        self._id = obj_id
        self._data = obj_data
        self._tags = None

    @property
    def tags(self):
        if self._tags is None:
            if hasattr(self, '_describe_tags_func'):
                describe_tags_fn = getattr(getattr(clients, self._type), self._describe_tags_func)
                self._tags = {t['Key']: t['Value']
                              for t in self._get_tag_obj_from_api_response(
                                  describe_tags_fn(**self._describe_tags_params))}
            else:
                self._tags = {t['Key']: t['Value'] for t in self._data.get('Tags', [])}
        return self._tags

    @property
    def created_time(self):
        raise NotImplementedError

    @property
    def name(self):
        try:
            return self.tags['Name']
        except:
            return ''

    @property
    def type(self):
        return self._type

    @property
    def vpc(self):
        raise NotImplementedError

    @property
    def groups(self):
        return NotImplemented

    def default_sg(self):
        return clients.ec2.describe_security_groups(Filters=[
            {'Name': 'vpc-id', 'Values': [self.vpc]},
            {'Name': 'group-name', 'Values': ['default']}
        ])['SecurityGroups'][0]['GroupId']

    def terminate(self):
        terminate_fn = getattr(getattr(clients, self._type), self._terminate_func)
        return terminate_fn(**self._terminate_params)

    def __str__(self):
        obj_str = '[%s]:%s' % (self.type, self._id)
        if self.name:
            obj_str += ' (%s)' % self.name
        return obj_str


class EC2_Resource(Resource):
    _type = 'ec2'
    _default_sg = {}
    _terminate_func = 'terminate_instances'

    @classmethod
    def get_default_sg(self, vpc):
        if not EC2_Resource._default_sg:
            logger.info('Retrieving default security groups')
            groups = clients.ec2.describe_security_groups(
                Filters=[{'Name': 'group-name', 'Values': ['default']}])['SecurityGroups']
            for g in groups:
                EC2_Resource._default_sg.setdefault(g['VpcId'], g['GroupId'])

        if vpc in EC2_Resource._default_sg:
            return EC2_Resource._default_sg[vpc]
        else:
            logger.error('Could not find default security group for vpc %s', vpc)
            return None

    def __init__(self, _id, _data=None):
        self._terminate_params = {'InstanceIds': [_id], 'DryRun': False}
        super(EC2_Resource, self).__init__(_id, _data)

    @property
    def vpc(self):
        return self._data['VpcId']

    @property
    def status(self):
        return self._data['State']['Name']

    @property
    def created_time(self):
        return self._data['LaunchTime']

    @property
    def groups(self):
        return [sg['GroupId'] for sg in self._data['SecurityGroups']]

    @groups.setter
    def groups(self, sgroups, **kwargs):
        clients.ec2.modify_instance_attribute(InstanceId=self._id, Groups=sgroups)
        self._data['SecurityGroups'] = [{'GroupName': 'default', 'GroupId': g} for g in sgroups]

    def delete_tags(self, keys, **kwargs):
        return clients.ec2.delete_tags(Resources=[self._id],
                                       Tags=[{'Key': k} for k in keys],
                                       **kwargs)

    def terminate(self, clear_sg=True, DryRun=False):
        if clear_sg:
            logger.info('Setting security groups for instance %s to %s', self._id,
                        [EC2_Resource.get_default_sg(self.vpc)])
            self.groups = [EC2_Resource.get_default_sg(self.vpc)]

        # clear the Termination Protection first
        clients.ec2.modify_instance_attribute(InstanceId=self._id,
                                              DisableApiTermination={'Value': False},
                                              DryRun=DryRun)
        self._terminate_params['DryRun'] = DryRun
        super(EC2_Resource, self).terminate()

    def shutdown(self, DryRun=False):
        clients.ec2.stop_instances(InstanceIds=[self._id], DryRun=DryRun)

    @property
    def uptime(self):
        if self.status == 'running':
            try:
                return datetime.datetime.utcnow() - self.created_time.replace(tzinfo=None)
            except ValueError:
                return datetime.timedelta(0)
        else:
            return datetime.timedelta(0)

    @property
    def downtime(self):
        if self.status == 'stopped':
            try:
                shutdown_time = datetime.datetime.strptime(
                    self._data['StateTransitionReason'].split('(')[1].split(' GMT)')[0],
                    '%Y-%m-%d %H:%M:%S'
                ).replace(tzinfo=None)
                return datetime.datetime.utcnow() - shutdown_time
            except ValueError:
                return datetime.timedelta(0)
        else:
            return datetime.timedelta(0)


class RDS_Resource(Resource):

    _type = 'rds'
    _terminate_func = 'delete_db_instance'
    _describe_tags_func = 'list_tags_for_resource'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'DBInstanceIdentifier': _id, 'SkipFinalSnapshot': True}
        self._name = _id
        self._describe_tags_params = {'ResourceName': self.arn}
        super(RDS_Resource, self).__init__(self.arn, _data)

    @property
    def name(self):
        return self._data['DBInstanceIdentifier']

    @property
    def arn(self):
        return arn.rds_instance(self._name)

    @property
    def vpc(self):
        return self._data['DBSubnetGroup']['VpcId']

    @property
    def groups(self):
        return [sg['VpcSecurityGroupId'] for sg in self._data['VpcSecurityGroups']]

    @groups.setter
    def groups(self, sgroups):
        clients.rds.modify_db_instance(DBInstanceIdentifier=self._name, VpcSecurityGroupIds=sgroups)
        self._data['VpcSecurityGroups'] = [{'Status': 'active', 'VpcSecurityGroupId': g}
                                           for g in sgroups]

    @property
    def created_time(self):
        return self._data['InstanceCreateTime']

    @property
    def status(self):
        return self._data['DBInstanceStatus']

    def _get_tag_obj_from_api_response(self, obj):
        return obj['TagList']

    def delete_tags(self, keys):
        return clients.rds.remove_tags_from_resource(ResourceName=self._id, TagKeys=keys)

    def shutdown(self, DryRun=False):
        if DryRun:
            raise ClientError({'Error': {'Code': 'DryRunOperation'}}, "")
        else:
            clients.rds.stop_db_instance(DBInstanceIdentifier=self.name)

    def last_event(self):
        # RDS only tracks events for 14 days
        look_back_hours = 335
        now = datetime.datetime.utcnow()
        try:
            return clients.rds.describe_events(
                SourceIdentifier=self.name,
                SourceType='db-instance',
                StartTime=now - datetime.timedelta(hours=look_back_hours),
                EndTime=now,
                EventCategories=['creation', 'availability', 'notification', 'deletion']
            )['Events'][-1]
        except IndexError:
            return 'NA'

    @property
    def uptime(self):
        if self.status == 'available':
            if self.last_event() == 'NA':
                return datetime.timedelta(days=14)
            else:
                now = datetime.datetime.utcnow()
                return now-self.last_event()['Date'].replace(tzinfo=None)
        else:
            return datetime.timedelta(0)

    @property
    def downtime(self):
        if self.status == 'stopped':
            if self.last_event() == 'NA':
                return datetime.timedelta(days=14)
            else:
                now = datetime.datetime.utcnow()
                return now-self.last_event()['Date'].replace(tzinfo=None)
        else:
            return datetime.timedelta(0)

    def terminate(self, DryRun=False):
        if DryRun:
            raise ClientError({'Error': {'Code': 'DryRunOperation'}}, "")
        else:
            return super(RDS_Resource, self).terminate()


class RDSAurora_Resource(Resource):
    _type = 'rds'
    _terminate_func = 'delete_db_cluster'

    def __init__(self, _id, _data=None):
        super(RDSAurora_Resource, self).__init__(_id, _data)
        self._terminate_params = {'DBClusterIdentifier': _id, 'SkipFinalSnapshot': True}


class ELB_Resource(Resource):
    _type = 'elb'
    _terminate_func = 'delete_load_balancer'
    _describe_tags_func = 'describe_tags'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'LoadBalancerName': _id}
        self._describe_tags_params = {'LoadBalancerNames': [_id]}
        super(ELB_Resource, self).__init__(_id, _data)
        self._name = _id

    @property
    def vpc(self):
        return self._data['VPCId']

    @property
    def groups(self):
        return self._data['SecurityGroups']

    @groups.setter
    def groups(self, sggroups):
        clients.elb.apply_security_groups_to_load_balancer(
            LoadBalancerName=self._id, SecurityGroups=sggroups)

    @property
    def created_time(self):
        return self._data['CreatedTime']

    def _get_tag_obj_from_api_response(self, obj):
        return obj['TagDescriptions'][0]['Tags']


class ELBv2_Resource(Resource):
    _type = 'elbv2'
    _terminate_func = 'delete_load_balancer'
    _describe_tags_func = 'describe_tags'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'LoadBalancerArn': _id}
        self._describe_tags_params = {'ResourceArns': [_id]}
        super(ELBv2_Resource, self).__init__(_id, _data)

    @property
    def vpc(self):
        return self._data['VpcId']

    @property
    def groups(self):
        return self._data['SecurityGroups']

    @groups.setter
    def groups(self, sggroups):
        clients.elbv2.set_security_groups(LoadBalancerArn=self._id, SecurityGroups=sggroups)

    @property
    def created_time(self):
        return self._data['CreatedTime']

    def _get_tag_obj_from_api_response(self, obj):
        return obj['TagDescriptions'][0]['Tags']

    def terminate(self):
        # clear deletion protection first
        clients.elbv2.modify_load_balancer_attributes(
            LoadBalancerArn=self._id, Attributes=[{'Key': 'deletion_protection.enabled',
                                                   'Value': 'false'}])
        return super(ELBv2_Resource, self).terminate()


class AutoScalingGroup_Resource(Resource):
    _type = 'autoscaling'
    # NOTE: Deleting an AutoScaling Group automatically terminates all the instances under it.
    # The Group cannot be deleted otherwise
    _terminate_func = 'delete_auto_scaling_group'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'AutoScalingGroupName': _id, 'ForceDelete': True}
        super(AutoScalingGroup_Resource, self).__init__(_id, _data)
        if _data is not None:
            self.data = _data
        else:
            try:
                self.data = clients.autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[_id])['AutoScalingGroups'][0]
            except IndexError:
                logger.warn('no data found for group %s' %_id)
                self.data = {}
        self.valid_tags = []

    @property
    def name(self):
        return self._id

    @property
    def created_time(self):
        return self._data['CreatedTime']

    def suspend(self, DryRun=False):
        if DryRun:
            raise ClientError({'Error': {'Code': 'DryRunOperation'}}, "")
        else:
            return clients.autoscaling.suspend_processes(
                AutoScalingGroupName=self._id,
                ScalingProcesses=['Launch', 'Terminate', 'ReplaceUnhealthy']
            )

    def terminate(self, DryRun=False):
        if DryRun:
            raise ClientError({'Error': {'Code': 'DryRunOperation'}}, "")
        else:
            return super(RDS_Resource, self).terminate()

    # Shutdown for an AutoScaling group is taken as setting its desired capacity to 0.
    # This terminates all its instances while not deleting the group itself
    def shutdown(self, DryRun=False):
        if DryRun:
            raise ClientError({'Error': {'Code': 'DryRunOperation'}}, "")
        else:
            return clients.autoscaling.set_desired_capacity(AutoScalingGroupName=self.name, DesiredCapacity=0)

    # This returns if the group's Launch process is suspended and when.
    # It indicates whether stopping or deleting its instances would trigger a new one
    @property
    def scaling_state(self):
        for process in self._data['SuspendedProcesses']:
            if process['ProcessName'] == 'Launch':
                return {
                    'Status': 'Suspended',
                    'SuspensionTime': datetime.datetime.strptime(
                            process['SuspensionReason'].split(' at ')[1], '%Y-%m-%dT%H:%M:%SZ'
                        )
                }
        return {
            'Status': 'Active'
        }

    # Downtime for an ASG is the amount of time since it latest Terminate activity when the group size is 0
    # if none found it will be the group creation time
    @property
    def downtime(self):
        if self._data['DesiredCapacity'] == 0:
            ### TEMPORARYY SOOLUTION UNTIL WE CAN RESOLVE THE THROTTLING ISSUES
            return datetime.datetime.utcnow() - self._data['CreatedTime'].replace(tzinfo=None)
            #            activities = clients.autoscaling.describe_scaling_activities(AutoScalingGroupName=self.name)['Activities'] 
            #            if len(activities) > 0:
            #                return datetime.datetime.utcnow() - activities[0]['StartTime'].replace(tzinfo=None)
            #            else:
            #                return datetime.datetime.utcnow() - self._data['CreatedTime'].replace(tzinfo=None)
        else:
            return datetime.timedelta(0)

    # Uptime for an ASG will be the time since the last Launch activity if the group size is >0,
    # if none found it will be the group creation time
    @property
    def uptime(self):
        if self._data['DesiredCapacity'] == 0:
            return datetime.timedelta(0)
        else:
            ### TEMPORARYY SOOLUTION UNTIL WE CAN RESOLVE THE THROTTLING ISSUES
            return datetime.datetime.utcnow() - self._data['CreatedTime'].replace(tzinfo=None)
            #            activities = clients.autoscaling.describe_scaling_activities(AutoScalingGroupName=self.name)['Activities']
            #            if len(activities) > 0:
            #                return datetime.datetime.utcnow() - activities[0]['StartTime'].replace(tzinfo=None)
            #            else:
            #                return datetime.datetime.utcnow() - self._data['CreatedTime'].replace(tzinfo=None)


class S3Bucket_Resource(Resource):
    _type = 's3'
    _describe_tags_func = 'get_bucket_tagging'
    _terminate_func = 'delete_bucket'

    def __init__(self, _id, _data=None):
        self._describe_tags_params = {'Bucket': _id}
        self._terminate_params = {'Bucket': _id}
        super(S3Bucket_Resource, self).__init__(_id, _data)
        self.valid_tags = []

    @property
    def created_time(self):
        return self._data['CreationDate']

    @property
    def name(self):
        return self._id

    def _get_tag_obj_from_api_response(self, obj):
        return obj['TagSet']

    def terminate(self):
        bucket = boto3.resource('s3').Bucket(self._id)
        bucket.objects.all().delete()
        bucket.object_versions.all().delete()
        super(S3Bucket_Resource, self).terminate()


class LaunchConfiguration_Resource(Resource):
    _type = 'autoscaling'
    _terminate_func = 'delete_launch_configuration'

    def _get_tag_obj_from_api_response(self, obj):
        return []

    def __init__(self, _id, _data=None):
        self._terminate_params = {'LaunchConfigurationName': _id}
        super(LaunchConfiguration_Resource, self).__init__(_id, _data)


class SecurityGroup_Resource(Resource):
    _type = EC2_Resource._type
    _terminate_func = 'delete_security_group'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'GroupId': _id}
        super(SecurityGroup_Resource, self).__init__(_id, _data)
        self.isdefault = self.name == 'default'

    @property
    def vpc(self):
        return self._data['VpcId']

    @property
    def name(self):
        return self._data['GroupName']

    @property
    def type(self):
        return 'securitygroup'

    def terminate(self):
        if self.name == 'default':
            logger.warn("Refusing to remove default security group %s for VPC %s", self, self.vpc)
        else:
            try:
                super(SecurityGroup_Resource, self).terminate()
            except ClientError as e:
                if e.response['Error']['Code'] == 'DependencyViolation':
                    logger.error('Could not delete security group: the group is still attached to other resources.')
                else:
                    logger.exception('Failed to remove security group')


class EBSVolume_Resource(Resource):
    _type = EC2_Resource._type
    _terminate_func = 'delete_volume'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'VolumeId': _id}
        super(EBSVolume_Resource, self).__init__(_id, _data)

    def terminate(self, DryRun=False):
        self._terminate_params['DryRun'] = DryRun
        super(EBSVolume_Resource, self).terminate()


class Snapshot_Resource(Resource):
    _type = EC2_Resource._type
    _terminate_func = 'delete_snapshot'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'SnapshotId': _id}
        super(Snapshot_Resource, self).__init__(_id, _data)


class AMI_Resource(Resource):
    _type = EC2_Resource._type
    _terminate_func = 'deregister_image'

    @property
    def name(self):
        return self._data['Name']

    @property
    def created_time(self):
        return dateutil.parser.parse(self._data['CreationDate'])

    def __init__(self, _id, _data=None):
        self._terminate_params = {'ImageId': _id}
        super(AMI_Resource, self).__init__(_id, _data)


class ENI_Resource(Resource):
    _type = EC2_Resource._type
    _terminate_func = 'delete_network_interface'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'NetworkInterfaceId': _id}
        super(ENI_Resource, self).__init__(_id, _data)


class KeyPair_Resource(Resource):
    _type = EC2_Resource._type
    _terminate_func = 'delete_key_pair'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'KeyName': _id}
        super(KeyPair_Resource, self).__init__(_id, _data)

    @property
    def type(self):
        return 'key'


class EFS_Resource(Resource):
    _type = 'efs'
    _terminate_func = 'delete_file_system'
    _describe_tags_func = 'describe_tags'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'FileSystemId': _id}
        self._describe_tags_params = self._terminate_params
        super(EFS_Resource, self).__init__(_id, _data)
        self._mount_targets = self._get_mount_targets()
        self._security_groups = self._get_security_groups()
        self._vpc = None

    def _get_mount_targets(self):
        targets = []
        try:
            targets = clients.efs.describe_mount_targets(FileSystemId=self._id)['MountTargets']
        except ClientError:
            logger.exception('Failed to get mount targets for EFS %s', self._id)

        return targets

    def _get_security_groups(self):
        groups = {}
        for target in self._mount_targets:
            try:
                groups[target['MountTargetId']] = clients.efs.describe_mount_target_security_groups(
                    MountTargetId=target['MountTargetId'])['SecurityGroups']
            except ClientError:
                logger.exception('Failed to get security groups for mount target %s',
                                 target['MountTargetId'])

        return groups

    @property
    def created_time(self):
        return self._data['CreationTime']

    def _get_tag_obj_from_api_response(self, obj):
        return obj['Tags']

    @property
    def name(self):
        return self._data['Name']

    @property
    def vpc(self):
        if self._vpc is None:
            subnet_of_first_mount_target = self._mount_targets[0]['SubnetId']
            vpc = clients.ec2.describe_subnets(SubnetIds=[subnet_of_first_mount_target])
            self._vpc = vpc['Subnets'][0]['VpcId']

        return self._vpc

    @property
    def groups(self):
        return list(set(itertools.chain(*self._security_groups.values())))

    @groups.setter
    def groups(self, sggroups):
        # To simplify, this assumes all mount points should get the same security groups.
        for target in self._mount_targets:
            try:
                logger.info('Setting security groups for mount point %s', target['MountTargetId'])
                clients.efs.modify_mount_target_security_groups(
                    MountTargetId=target['MountTargetId'], SecurityGroups=sggroups)
            except ClientError:
                logger.exception('Failed to set security groups')

    def terminate(self):
        if self._mount_targets:
            for target in self._mount_targets:
                logger.info('Deleting mount target %s', target['MountTargetId'])
                try:
                    clients.efs.delete_mount_target(MountTargetId=target['MountTargetId'])
                except ClientError:
                    logger.exception('Failed to delete mount target %s for filesystem %s',
                                     target['MountTargetId'], self._id)
                    logger.error('Deletion of file system aborted, manual intervention is required')
            logger.warn('The mount targets of filesystem %s were removed, but the FS itself was not. It will be removed next time if it still exists', self._id)
        else:
            super(EFS_Resource, self).terminate()


class DBSnapshot_Resource(Resource):
    _type = RDS_Resource._type
    _terminate_func = 'delete_db_snapshot'
    _describe_tags_func = 'list_tags_for_resource'

    @property
    def created_time(self):
        return self._data.get('SnapshotCreateTime', datetime.datetime.now(tzutc()))

    @property
    def arn(self):
        return arn.rds_snapshot(self._id)

    def __init__(self, _id, _data=None):
        self._terminate_params = {'DBSnapshotIdentifier': _id}
        super(DBSnapshot_Resource, self).__init__(_id, _data)
        self._describe_tags_params = {'ResourceName': self.arn}

    def _get_tag_obj_from_api_response(self, obj):
        return obj['TagList']


class Lambda_Resource(Resource):
    _type = 'lambda'
    _terminate_func = 'delete_function'
    _describe_tags_func = 'list_tags'

    def __init__(self, _id, _data=None):
        self._terminate_params = {'FunctionName': _id}
        super(Lambda_Resource, self).__init__(_id, _data)
        self._describe_tags_params = {'Resource': self.arn}

    @property
    def arn(self):
        return arn.lambda_function(self._id)

    @property
    def name(self):
        return self._id

    @property
    def tags(self):
        if self._tags is None:
            describe_tags_func = getattr(getattr(clients, self._type), self._describe_tags_func)
            self._tags = describe_tags_func(**self._describe_tags_params)['Tags']
        return self._tags

    @property
    def created_time(self):
        return dateutil.parser.parse(self._data['LastModified'])


class CloudFormation_Resource(Resource):
    _type = 'cloudformation'
    _terminate_func = 'delete_stack'

    def __init__(self, _id, _data=None):
        super(CloudFormation_Resource, self).__init__(_id, _data)
        self._terminate_params = {'StackName': self._id}

    @property
    def name(self):
        return self._id

    @property
    def created_time(self):
        return self._data.get('CreationTime', None)

