import sys
import operator
import boto3_clients as aws
import config
from botocore.exceptions import ClientError

_IMAGES = {
    'AmazonLinux': {
        'image': None,
        'owner': 'amazon',
        'filters': {
            'description': 'Amazon Linux AMI * x86_64 HVM EBS',
            'name': 'amzn-ami-hvm*x86_64-ebs'
        }
    },
    'NetScaler11': {
        'image': None,
        'owner': 'aws-marketplace',
        'filters': {
            'description': 'Citrix NetScaler and CloudBridge Connector 11.1-53.11',
            'name': 'Citrix NetScaler and CloudBridge Connector 11.1-53.11*'
        },
        'images': {
            'Platinum10Mbps': {
                'ap-northeast-1': 'ami-a2d1e8c5',
                'ap-northeast-2': 'ami-4c4a9722',
                'ap-southeast-1': 'ami-68bf380b',
                'ap-southeast-2': 'ami-addacfce',
                'ap-south-1': 'ami-c485f8ab',
                'ca-central-1': 'ami-e665d982',
                'eu-central-1': 'ami-01ab736e',
                'eu-west-1': 'ami-3c6c665a',
                'eu-west-2': 'ami-971403f3',
                'sa-east-1': 'ami-7218761e',
                'us-east-1': 'ami-69fc877f',
                'us-east-2': 'ami-bf8fa8da',
                'us-west-1': 'ami-1cdffe7c',
                'us-west-2': 'ami-5194f231'
            },
            'Standard10Mbps': {
                'ap-northeast-1': 'ami-6963790e',
                'ap-northeast-2': 'ami-4d11cf23',
                'ap-southeast-1': 'ami-0f77e06c',
                'ap-southeast-2': 'ami-30849953',
                'ap-south-1': 'ami-fea2db91',
                'ca-central-1': 'ami-024bf466',
                'eu-central-1': 'ami-aee745c1',
                'eu-west-1': 'ami-19987560',
                'eu-west-2': 'ami-5882943c',
                'sa-east-1': 'ami-34176358',
                'us-east-1': 'ami-73626b65',
                'us-east-2': 'ami-cbae8fae',
                'us-west-1': 'ami-a4153bc4',
                'us-west-2': 'ami-7ff2ee06'
            }
        }
    },
    'RedHat7': {
        'image': None,
        'owner': '309956199498',
        'filters': {
            'description': 'Provided by Red Hat, Inc.',
            'name': 'RHEL-7.3_HVM-*-x86_64-4-Hourly2-GP2'
        }
    },
    'VDA': {
        'image': None,
        'owner': 'self',
        'filters': {
            'platform': 'windows',
            'tag:Name': config.citrix.VDA_AMI_PREFIX
        }
    },
    'Windows2012': {
        'image': None,
        'owner': 'amazon',
        'filters': {
            'description': 'Microsoft Windows Server 2012 R2 RTM 64-bit Locale English AMI provided by Amazon',
            'name': 'Windows_Server-2012-R2_RTM-English-64Bit-Base-*'
        }
    }
}


def _get_image(image_type):

    if image_type == 'NetScaler11':
        try:
            image_list = aws.ec2.describe_images(ImageIds=[_IMAGES['NetScaler11']['images']['Standard10Mbps'][aws.region]])
        except ClientError as ce:
            print 'Failed to get AMI:', ce.message
            return None
    else:
        describe_filters = [
            { 'Name': 'state', 'Values': ['available', 'pending'] },
            { 'Name': 'architecture', 'Values': ['x86_64'] },
            { 'Name': 'image-type', 'Values': ['machine'] }
        ] + [
            { 'Name': filter_name, 'Values': [filter_value] } \
                for filter_name, filter_value in _IMAGES[image_type]['filters'].items()
        ]

        try:
            image_list = aws.ec2.describe_images(Owners=[_IMAGES[image_type]['owner']], Filters=describe_filters)
        except ClientError as ce:
            print 'Failed to get AMI:', ce.message
            return None

    newlist = sorted(image_list['Images'], key=operator.itemgetter('CreationDate'), reverse=True)
    if len(newlist) == 0:
        print 'No AMIs found for',image_type
        return None
    else:
        return newlist[0]


def get_image(image_type):

    if image_type in _IMAGES:
        image = _get_image(image_type)
        _IMAGES[image_type]['image'] = image
        return _IMAGES[image_type]['image']
    else:
        raise ValueError("Unknown image requested (%s), known images are %s" % (image_type,', '.join(_IMAGES)))


if __name__ == '__main__':

    try:
        requested_img = sys.argv[1]
    except IndexError:
        print 'Please specify an image to retrieve, valid values are:'
        print '   ', ', '.join(_IMAGES)
        sys.exit(1)

    image = get_image(requested_img)
    if image is None:
        print 'No image available'
    else:
        print image['ImageId'], image['Description']

