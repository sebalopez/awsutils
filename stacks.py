__author__ = 'sebalopez'

import sys
import boto3
import botocore
import boto3_clients as clients


waiter_status = {
    'CREATE_IN_PROGRESS' : 'stack_create_complete',
    'UPDATE_IN_PROGRESS' : 'stack_update_complete',
    'DELETE_IN_PROGRESS' : 'stack_delete_complete',
}

create_status = ('NEW')
update_status = ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE')
delete_status = ('ROLLBACK_COMPLETE', 'ROLLBACK_IN_PROGRESS','DELETE_IN_PROGRESS', 'DELETE_FAILED')
skip_status = ('CREATE_IN_PROGRESS', 'UPDATE_IN_PROGRESS', 'UPDATE_ROLLBACK_IN_PROGRESS')

bucket = '< ENTER TARGET S3 BUCKET FOR TEMPLATES HERE>'

class Stack (object):

    def __init__(self, name, bucket=bucket,template_file=''):
        self.id = self.name = name
        self.template = template_file
        self._exists = True
        self.bucket = bucket
        try:
            self.tags = { t['Key']: t['Value'] for t in self.data.get('Tags', []) }
            self.params = { p['ParameterKey']: p['ParameterValue'] for p in self.data.get('Parameters', []) }
        except botocore.exceptions.ClientError as ce:
            if ce.response['Error']['Code'] == 'ValidationError':
                self._exists = False

    @property
    def data(self):
        try:
            return clients.cloudformation.describe_stacks(StackName=self.name)['Stacks'][0]
        except botocore.exceptions.ClientError:
            return {}

    @property
    def creation_time(self):
        return (self.data['CreationTime'] if self._exists else None)

    @property
    def status(self):
        status = 'NEW'
        try:
            status = clients.cloudformation.describe_stacks(StackName=self.id)['Stacks'][0]['StackStatus']
        except botocore.exceptions.ClientError as ce:
            if ce.response['Error']['Code'] == 'ValidationError':
                status = 'NEW'
            else:
                raise
        return status

    @property
    def outputs(self):
        if self.status in update_status + ('DELETE_FAILED',):
            return { o['OutputKey']: o['OutputValue'] for o in self.data.get('Outputs', []) }
        else:
            return {}

    @property
    def resources(self):
        return clients.cloudformation.describe_stack_resources(StackName=self.name)['StackResources']

    def upload_template(self, validate=True):
        sys.stdout.write('Uploading local version of template to S3...')
        local_path = self.template
        print local_path
        key = self.template
        s3 = boto3.resource('s3')
        s3.meta.client.upload_file(local_path, self.bucket, key)
        print 'Done'
        template_url = 'https://s3.amazonaws.com/%s/%s' % (self.bucket, key)
        if validate:
            sys.stdout.write('Validating template...')
            clients.cloudformation.validate_template(TemplateURL=template_url)
            print 'OK'
        return template_url

    def launch(self, **kwargs):

        current = self.status
        print 'Current status: ', current

        if current in skip_status:
            print '  Stack currently being modified, no action taken'
            print '  Stack ID: ' + self.data['StackId']
            return 'OK'

        if current in delete_status:
            print ' Deleting current stack'
            self.delete(wait=True)
            response = self.launch(**kwargs)
            return response

        if current in create_status or current in update_status:
            template_url = self.upload_template()
            if current in create_status:
                try:
                    sys.stdout.write('Deploying new Stack...')
                    response = clients.cloudformation.create_stack(StackName=self.id, TemplateURL=template_url, **kwargs)
                    print 'OK'
                    print '  Stack ID: ' + response['StackId']
                    return 'OK'
                except botocore.exceptions.ClientError as error:
                    print error
                    return 'ERROR'
            if current in update_status:
                try:
                    sys.stdout.write('Checking Stack for updates...')
                    response = clients.cloudformation.update_stack(UsePreviousTemplate=False, StackName=self.id, TemplateURL=template_url, **kwargs)
                    print 'OK'
                    print '  Stack ID: ' + response['StackId']
                    return 'OK'
                except botocore.exceptions.ClientError as error:
                    if error.response['Error']['Code'] == 'ValidationError':
                        print 'No updates needed'
                        return 'NOOP'
                    else:
                        return 'ERROR'

    def delete(self, wait=False, **kwargs):
        try:
            response = clients.cloudformation.delete_stack(StackName=self.id, **kwargs)
            if wait:
                waiter = clients.cloudformation.get_waiter('stack_delete_complete')
                waiter.wait(StackName=self.id)
                return 'Stack Removed'
            else:
                return response['ResponseMetadata']
        except botocore.exceptions.WaiterError as error:
            print error
            print 'Current Stack status: ', self.status
            exit(1)

    def wait_complete(self, print_outputs=True):
        if self.status in waiter_status.keys():
            waiter = clients.cloudformation.get_waiter(waiter_status[self.status])
            print 'Waiting for %s to be ready...' % (self.id)
            try:
                waiter.wait(StackName=self.id)
                print 'Stack COMPLETE'
                print 'Stack Outputs:'
                if print_outputs:
                    for output in clients.cloudformation.describe_stacks(StackName=self.id)['Stacks'][0]['Outputs']:
                        print output['ExportName'],': ',output['OutputValue']
            except botocore.exceptions.WaiterError as error:
                print error
                print 'Current Stack status: ', self.status
                exit(1)
        else:
            print 'Current Stack status: ', self.status
            print 'No Waiter for this status'

