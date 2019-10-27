import arn
__author__ = 'SG0894074'

import os
import errno
import zipfile
import json
import botocore
import boto3
import boto3_clients as aws

import config

lambda_function_list = ()


def include_in_zip(path):
    return path.endswith('.py') or path.endswith('.yaml')


def zipdir(path, ziph, filter=None):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            if filter(file):
                file_path = os.path.join(root, file)
                name_inside_zip = file_path.replace(path, '', 1)
                print " Adding", name_inside_zip
                ziph.write(file_path, name_inside_zip)


# Builds a single zip file containing all local Lambda functions and their dependencies
# Assumes every subfolder contains dependencies and includes them in the zip (.pyc files are not
# included to minimize storage size)
def build_zip(folder, zip_name='lambda.zip'):
    print '### Building zip file containing all Lambda functions and dependencies'
    if os.path.isdir(folder):
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
            zipdir(folder, zf, filter=include_in_zip)
    else:
        raise ValueError("Cannot create zip file: %s is not a valid directory" % folder)
    print 'Done'
    return os.path.join(folder, zip_name)


def upload_zip(path, zip_file, bucket):
    s3_path = 's3://%s/%s/' %(bucket, path)
    print 'Uploading %s to %s' %(zip_file, s3_path)
    with open(zip_file, 'rb') as data:
        aws.s3.put_object(Body=data, Bucket=bucket, Key='%s/%s' % (path, zip_file))
    print '  Done'

# Uploads the zip file containing the Lambda code, then iterates through the provided directory and creates or updates Lambda functions with the deployment package placed into S3
# If configuration files are found, it will also update the function configuration
# Note new functions cannot be deployed without a config file
def deploy_functions(bucket=config.S3_BUCKET, region='us-east-1', function_dir=os.getcwd(), function_zip='lambda.zip', s3_path='/', function_prefix='', role=None, create=True, update=True):

    upload_zip(s3_path,function_zip,bucket)
    lambda_s3_zip_path = '%s/%s' %(s3_path,function_zip)
    print lambda_s3_zip_path
    l_client = boto3.client('lambda', region_name=region)
    for function in lambda_function_list:
        filename = function+'.py'
        if filename in os.listdir(function_dir):
            script_name = filename.split('.')[0]
            function_name = function_prefix+script_name
            print 'Deploying '+function_name
            #Reading function config
            config = {}
            print '  Looking for configuration file...'
            try:
                with open(function_name + '.json') as config_file:
                    config = json.load(config_file)
                    print 'OK'

            except IOError as ioe:
                if ioe.errno == errno.ENOENT:
                    config = {}
                    print 'Not Found'
                else:
                    print 'Caught an unexpected IOError', ioe.errno, ioe.message
                    raise
            #Looking for existing function
            print '  Looking for '+function_name+' in AWS Lambda..'
            try:
                l_client.get_function(FunctionName=function_name)
                print 'Found'
                if update:
                    print '  Updating function code from local copy...'
                    l_client.update_function_code(FunctionName=function_name, S3Bucket=bucket, S3Key=lambda_s3_zip_path, Publish=True)
                    print 'OK'
                    if config:
                        print '  Updating function configuration from local config file..'
                        l_client.update_function_configuration(**config)
                        print 'OK'
            except botocore.exceptions.ClientError as error:
                if error.response['Error']['Code'] == 'ResourceNotFoundException':
                    print 'Not Found'
                    #If function is new and create option is selected, deploy new function
                    if create:
                        print '  Creating new Function from '+function_zip+'...'
                        if not config:
                            # If not previously defined, build configuration with default values
                            config['FunctionName'] = function_name
                            if role:
                                config['Role'] = arn.role(role)
                            config['Runtime'] = 'python2.7'
                            config['Handler'] = script_name+'.lambda_handler'
                            config['Description'] = 'Function deployed from deploy_lambda.py'
                            config['MemorySize'] = 128
                            config['Timeout'] = 300
                        l_client.create_function(Code={'S3Bucket': bucket, 'S3Key': lambda_s3_zip_path}, **config)
                        print 'OK'
                else: print error.response['Error']
        else:
            print 'ERROR: %s.py was not found under %s' %(function, function_dir)
