Utilities for AWS API
=====================

This repository collects scripts built to simplify interaction with the multiple AWS APIs during provisioning and maintenance operations.

Repo can be imported as a submodule of project-specific repos. 

## Pre-Requirements
* Python 2.6+
* [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#installation)
* Valid AWS credentials will be read from environment variables


## boto3_clients.py

Singleton client objects for each specific API. Clients are created on demand as needed.

## resources.py

Wrapper classes for manipulating AWS resources and encapsulate equivalent operations (retrieve, tag, update security groups, stop, delete/terminate in a consistent manner wherever applicable.

Uses *boto3_clients*.

Currently supports:
* EC2 instance
* EC2 security group
* EC2 AMI
* EC2 KeyPair
* EBS Volume
* Elastic LB 
* ELBv2 (network- or application-load balancer)
* AutoScaling Group
* RDS instance
* RDS snapshot
* RDS Aurora instance (clustered)
* S3 Bucket
* Lambda script
* Elastic File System

## apihelpers.py

Class to retrieve all instances of the desited API resource. Useful to perform bulk operations (eg. tag validation, stop/start)

Supports all resource types defined in *resources.py*.

## stacks.py

Dedicated  wrapper for operations with CloudFormation Stacks. 

Includes waiter for stacks in progress, template upload to S3, template online validation.

## logger.py

Auxiliary function to setup logging in a consistent manner using the Python logging module.


## deploy_lambda.py

Deploys scripts located in specified input folder against Lambda. All contents of the folder are zipped together and uploaded once. From the common zipfile one function is created/updated per name defined in input list.

## arn.py

Function to build ARN names for resource types.

Currently supported:

* IAM role
* RDS instance
* RDS snapshot
* State Machine
* State Machine Execution


## jenkins_client.py

(Non-AWS specific) Wrapper class for connecting to and triggering Jenkins jobs, uses [Python Jenkins](https://python-jenkins.readthedocs.io/en/latest/install.html) module