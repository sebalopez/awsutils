# -*- coding: utf8 -*-

from time import sleep
import botocore
import functools
import logging
from . import boto3_clients as clients
from .resources import EC2_Resource, RDS_Resource, RDSAurora_Resource, ELB_Resource, \
    ELBv2_Resource, AutoScalingGroup_Resource, S3Bucket_Resource, LaunchConfiguration_Resource, \
    SecurityGroup_Resource, EBSVolume_Resource, Snapshot_Resource, DBSnapshot_Resource, \
    AMI_Resource, ENI_Resource, EFS_Resource, KeyPair_Resource, Lambda_Resource, \
    CloudFormation_Resource


logger = logging.getLogger(__name__)


# This metaclass defines functions used by the specialized classes.
# We define some of the functions here just to avoid having to de-reference them from the string
# variables every time.
class APIHelperMeta(type):

    def __new__(cls, clsname, bases, dct):
        """ This constructor creates a _describe function for the class, based on the string properties
            defined on it. """
        if clsname != 'APIHelper':  # APIHelper does not need this
            client = getattr(clients, dct['_type'])
            api_function = getattr(client, dct['_describe_function'])
            api_function_params = dct.get('_describe_params', {})
            dct['_describe'] = functools.partial(api_function, **api_function_params)
        return super(APIHelperMeta, cls).__new__(cls, clsname, bases, dct)


# This is the generic API class. Methods are defined here as generically as possible, based on
# string properties from each subclass.
class APIHelper(object):

    __metaclass__ = APIHelperMeta

    @classmethod
    def describe(cls, params):
        "Retrieves all objects of this type, returns pure JSON"
        try:
            r = cls._describe(**params)
        except botocore.exceptions.ClientError as ce:
            if ce.response['Error']['Code'] == 'Throttling':
                print 'Request throttled, waiting one second to retry'
                sleep(1)
                try:
                    r = cls._describe(**params)
                except botocore.exceptions.ClientError:
                    logger.exception("Failed to get %s resources", cls._type)
                    return []
        # Handle pagination
        # For some resources, the name of the token property is different in the request and
        # the response.
        # If _describe_token_property is defined in a class, use it for the request.
        # If _describe_token_property_response is defined, use it for the response.
        # If _describe_token_property is defined but _describe_token_property_response is not,
        # use _describe_token_property for both request and response.
        # if none is defined, don't try to request more items.
        token_property = getattr(cls, '_describe_token_property', None)
        token_property_response = getattr(cls, '_describe_token_property_response', token_property)
        token = r.get(token_property_response, None)
        if token:
            params[token_property] = token
            return [r] + cls.describe(params)
        else:
            return [r]

    @classmethod
    def get(cls, **params):
        """Retrieves all objects of this type, returns a list of objects of the corresponding
           'Resource' class"""
        resources = []
        for result_set in cls.describe(params):
            resources += cls._get_resources_from_result_set(result_set)
        return resources

    @classmethod
    def _get_resources_from_result_set(cls, result_set):
        """ Given a response JSON, extract each resource and return a 'Resource' object for it """
        resource_class = getattr(cls, '_resource_class')
        resource_id_property = getattr(cls, '_describe_resource_id_property')
        resource_list_property = getattr(cls, '_describe_resource_list_property')

        return [resource_class(resource[resource_id_property], resource)
                for resource in result_set[resource_list_property]]


# The following are specialized classes, one for each AWS Service.
# Currently they are only used to get the list of existing resources.
#
# In order to allow for the APIHelper class to define generic methods, the differences between each
# service API are described in class properties. The available properties are:
#
# * _type: REQUIRED. The client name to be passed to Boto3 for this service, i.e., the first
#   parameter to boto3.client().
#
# * _describe_function: REQUIRED. The name of the function used to retrieve all resources of this
#   type.
#
# * _describe_params: OPTIONAL. Parameters required by the _describe_function. These are parameters
#   which are always needed to get the right results.
#
# * _describe_token_property: OPTIONAL. If the API paginates results, the name of the "token" or
#   "marker" property used in the request to get the next page of results.
#
# * _describe_token_property_response: OPTIONAL. If the API paginates results, the name of the
#   "token" or "marker" property which comes with the API response. Define it only if the property
#   names in the request and the response are not the same.
#
# * _describe_resource_list_property: REQUIRED. In the JSON response from the Describe function,
#   the name of the property which contains the list of resources. API classes must either define
#   this property or override the method _get_resources_from_result_set from APIHelper.
#
# * _describe_resource_id_property: REQUIRED. In the JSON description of the resource, the name of
#   the property which stores the resource ID. API classes must either define this property or
#   override the method _get_resources_from_result_set from APIHelper.
#
# * _resource_class: REQUIRED. The Resource class for resources retrieved by this API. API classes
#   must either define this property or override the method _get_resources_from_result_set from
#   APIHelper.

class EC2API(APIHelper):
    """ Class used to retrieve EC2 Instances """
    _type = 'ec2'
    _resource_class = EC2_Resource
    _describe_function = 'describe_instances'
    _describe_params = {'MaxResults': 1000}
    _describe_token_property = 'NextToken'
    _describe_resource_list_property = 'Instances'
    _describe_resource_id_property = 'InstanceId'

    @classmethod
    def _get_resources_from_result_set(cls, result_set):
        instances = []
        for reservation in result_set.get('Reservations', []):
            instances += super(EC2API, cls)._get_resources_from_result_set(reservation)
        return instances


class RDSAPI(APIHelper):
    _type = 'rds'
    _resource_class = RDS_Resource
    _describe_function = 'describe_db_instances'
    _describe_params = {'MaxRecords': 100}
    _describe_token_property = 'Marker'
    _describe_resource_list_property = 'DBInstances'
    _describe_resource_id_property = 'DBInstanceIdentifier'

    @classmethod
    def get(cls, **params):
        try:
            vpc = params['vpc']
            del params['vpc']
        except KeyError:
            vpc = None
        instances = super(RDSAPI, cls).get(**params)
        if vpc is None:
            return instances
        else:
            return [inst for inst in instances if inst.vpc == vpc]

    @classmethod
    def _get_resources_from_result_set(cls, result_set):
        return [db for db in super(RDSAPI, cls)._get_resources_from_result_set(result_set)
                if db._data['DBInstanceStatus'] not in ('creating', 'deleting')]


class RDSAuroraAPI(RDSAPI):
    _type = RDSAPI._type
    _resource_class = RDSAurora_Resource
    _describe_function = 'describe_db_clusters'
    _describe_params = RDSAPI._describe_params
    _describe_token_property = RDSAPI._describe_token_property
    _describe_resource_list_property = 'DBClusters'
    _describe_resource_id_property = 'DBClusterIdentifier'

    @classmethod
    def _get_resources_from_result_set(cls, result_set):
        return super(RDSAPI, cls)._get_resources_from_result_set(result_set)


class ELBAPI(APIHelper):
    _type = 'elb'
    _resource_class = ELB_Resource
    _describe_function = 'describe_load_balancers'
    _describe_params = {'PageSize': 400}
    _describe_token_property = 'Marker'
    _describe_token_property_response = 'NextMarker'
    _describe_resource_list_property = 'LoadBalancerDescriptions'
    _describe_resource_id_property = 'LoadBalancerName'

    @classmethod
    def get(cls, **params):
        try:
            vpc = params['vpc']
            del params['vpc']
        except KeyError:
            vpc = None

        elbs = super(ELBAPI, cls).get(**params)
        if vpc is None:
            return elbs
        else:
            return [elb for elb in elbs if elb.vpc == vpc]


class ELBv2API(ELBAPI):
    _type = 'elbv2'
    _resource_class = ELBv2_Resource
    _describe_function = ELBAPI._describe_function
    _describe_params = ELBAPI._describe_params
    _describe_token_property = ELBAPI._describe_token_property
    _describe_token_property_response = ELBAPI._describe_token_property_response
    _describe_resource_list_property = 'LoadBalancers'
    _describe_resource_id_property = 'LoadBalancerArn'


class ASGAPI(APIHelper):
    _type = 'autoscaling'
    _resource_class = AutoScalingGroup_Resource
    _describe_function = 'describe_auto_scaling_groups'
    _describe_params = {'MaxRecords': 100}
    _describe_token_property = 'NextToken'
    _describe_resource_list_property = 'AutoScalingGroups'
    _describe_resource_id_property = 'AutoScalingGroupName'



class S3API(APIHelper):
    _type = 's3'
    _resource_class = S3Bucket_Resource
    _describe_function = 'list_buckets'
    _describe_resource_list_property = 'Buckets'
    _describe_resource_id_property = 'Name'


class LaunchConfigurationAPI(APIHelper):
    _type = 'autoscaling'
    _resource_class = LaunchConfiguration_Resource
    _describe_function = 'describe_launch_configurations'
    _describe_token_property = 'NextToken'
    _describe_resource_list_property = 'LaunchConfigurations'
    _describe_resource_id_property = 'LaunchConfigurationName'


class SecurityGroupAPI(APIHelper):
    _type = EC2API._type
    _resource_class = SecurityGroup_Resource
    _describe_function = 'describe_security_groups'
    _describe_resource_list_property = 'SecurityGroups'
    _describe_resource_id_property = 'GroupId'


class EBSVolumeAPI(APIHelper):
    _type = EC2API._type
    _resource_class = EBSVolume_Resource
    _describe_function = 'describe_volumes'
    _describe_token_property = 'NextToken'
    _describe_resource_list_property = 'Volumes'
    _describe_resource_id_property = 'VolumeId'


class SnapshotAPI(APIHelper):
    _type = EC2API._type
    _resource_class = Snapshot_Resource
    _describe_function = 'describe_snapshots'
    _describe_token_property = 'NextToken'
    _describe_resource_list_property = 'Snapshots'
    _describe_resource_id_property = 'SnapshotId'


class AMIAPI(APIHelper):
    _type = EC2API._type
    _resource_class = AMI_Resource
    _describe_function = 'describe_images'
    _describe_params = {'Owners': ['self']}
    _describe_resource_list_property = 'Images'
    _describe_resource_id_property = 'ImageId'


class ENIAPI(APIHelper):
    _type = EC2API._type
    _resource_class = ENI_Resource
    _describe_function = 'describe_network_interfaces'
    _describe_resource_list_property = 'NetworkInterfaces'
    _describe_resource_id_property = 'NetworkInterfaceId'


class KeyPairAPI(APIHelper):
    _type = EC2API._type
    _resource_class = KeyPair_Resource
    _describe_function = 'describe_key_pairs'
    _describe_resource_list_property = 'KeyPairs'
    _describe_resource_id_property = 'KeyName'


class EFSAPI(APIHelper):
    _type = 'efs'
    _resource_class = EFS_Resource
    _describe_function = 'describe_file_systems'
    _describe_token_property = 'Marker'
    _describe_token_property_response = 'NextMarker'
    _describe_resource_list_property = 'FileSystems'
    _describe_resource_id_property = 'FileSystemId'


class DBSnapshotAPI(APIHelper):
    _type = RDSAPI._type
    _resource_class = DBSnapshot_Resource
    _describe_function = 'describe_db_snapshots'
    _describe_token_property = 'Marker'
    _describe_resource_list_property = 'DBSnapshots'
    _describe_resource_id_property = 'DBSnapshotIdentifier'


class LambdaAPI(APIHelper):
    _type = 'lambda'
    _resource_class = Lambda_Resource
    _describe_function = 'list_functions'
    _describe_token_property = 'Marker'
    _describe_token_property_response = 'NextMarker'
    _describe_resource_list_property = 'Functions'
    _describe_resource_id_property = 'FunctionName'


class CloudFormationAPI(APIHelper):
    _type = 'cloudformation'
    _resource_class = CloudFormation_Resource
    _describe_function = 'describe_stacks'
    _describe_token_property = 'NextToken'
    _describe_resource_list_property = 'Stacks'
    _describe_resource_id_property = 'StackName'

