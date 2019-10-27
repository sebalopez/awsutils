Utilities for AWS API
=====================

This repository will centralize scripts built by the ASPD Infrastructure team that are being reused across several AWS-related projects (AS CloudLab, AirCentre Demo environment, MM pLab Automation).

Repo can be imported as a submodule of project-specific repos. 

## Requirements
* boto3 Python library must be installed
* valid AWS credentials will be read from environment variables
* some of these scripts will import configuration values from a config Python file or folder. Configuration needs to be imported as a module to be visible from these files.


## resources.py

## apihelpers.py

## boto3_clients.py

## stacks.py

## logger.py

## amis.py

## deploy_lambda.py