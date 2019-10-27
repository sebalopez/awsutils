""" This module contains functions to help creating ARNs """

import boto3_clients as aws

ARN_FORMAT = 'arn:aws:%(service)s:%(region)s:%(account_id)s:%(resource)s'


def arn(**kwargs):
    for arg in 'region', 'account_id':
        if arg not in kwargs:
            kwargs[arg] = getattr(aws, arg)
    return ARN_FORMAT % kwargs


def role(name):
    return arn(service='iam', resource='role/' + name, region='')


def state_machine(name):
    return arn(service='states', resource='stateMachine:' + name)


def state_machine_execution(machine, name):
    return arn(service='states', resource='execution:%s:%s' % (machine, name))


def rds_instance(name):
    return arn(service='rds', resource='db:' + name)


def rds_snapshot(name):
    return arn(service='rds', resource='snapshot:' + name)

