
#Global settings
main_s3_bucket = 'cloudlab-main'
app_s3_prefix = 'ascl-'
admin_email_address = 'ascloudlab@sabre.com'
#DynamoDB
dynamo_table_prefix = 'CloudLab_'
#Lambda
lambda_function_prefix = 'CloudLab_'
lambda_zip_name = 'CloudLab_Lambda.zip'
lambda_s3_prefix = 'cloudlab-'
lambda_s3_zip_path = 'sources/'+lambda_zip_name
lambda_default_role = 'CL_Admin'
lambda_default_runtime = 'python2.7'
lambda_s3_bucket = main_s3_bucket
#Shared Services Stack
ss_vpc_name = 'SharedServices VPC'
ss_stack_name = 'SharedServices'
ss_template_file = 'SharedServicesVPC.template'
ad_password = 'Abcd1234'
#CloudLab VPC Stack
cl_vpc_name = 'CloudLab VPC'
cl_stack_name = 'CloudLab'
cl_template_file = 'CloudLabVPC.template'
#Bastion Hosts Stack
bh_stack_name = 'SharedServices-BastionHosts'
bh_template_file = 'SharedServicesVPC-BastionHosts.template'
keypair_prefix = 'cloudlab_'
#Supported Applications
app_list = set((
    'CloudLab',
    'CommunityPortal', 'SCP',
    'IX', 'IXApps',
    'PlanningScheduling', 'AVPS',
    'ProrationEngine', 'AVPE',
    'RevenueOptimizer', 'AVRO',
    'RevenueManager', 'AVRM',
    'ACCM',
    'ACMM',
    'SSW',
    'IXCA',
    'ScheduleRepository', 'SchRep',
    'CrewMobile', 'CrewAccess', 'ACCA',
    'LoadMan', 'ECLM',
    'AVIF',
    'MCT2',
    'DevTools',
    'HealthCheck',
    'CTS',
    'EFM',
    'WebMobile',
    'AVFM',
    'Airports', 'ACA',
    'ISM',
    'ASPD',
    'AWSEP',
    'FPM',
    'AsCloudDB',
    'ACCB',
    'AirCentreDemo',
    'TestDemo',
    'AVRI',
    'CommonPlat',
    'SaaSLeveraged', 'LevSys',
    'ASOR',
    'GDD'
))
#Supported Regions
region_list = ('us-east-1',)
#Validation
## The list of required tags is a dictionary where each tag name is the key, and its value the regular expression allowed for the tag values
tag_validators = {
    'Name': '.+',
    'Application': '|'.join(app_list),
    'Owner': '^(sg[0-9]{6}|cl-(?:%s)(?:-[0-9])?)$' % ('|'.join(app_list).lower())
}
required_tags = {service: tag_validators.keys() for service in (
    'ec2', 'elb', 'rds', 'autoscaling', 's3', 'securitygroup', 'efs', 'lambda')}
validate_s3 = False
validate_sg = True
delete_on_sg_validation = False
default_sg_name = 'default'
email_tag = 'owner email'
#Time window for tags to be set upon creation of a resource
resource_validation_period = 15
admin_notify = False
validation_email_subject = 'AWS CloudLab - Resource Validation Results'
resource_validation_email_text = """

  Resource Validation Results
  ---------------------------

  Resource %s does not comply with CloudLab policies, and will be
  terminated immediately.

  The following tags are required for all resources (unless not supported):

  Name
  Owner = sgxxxxxx
  Application = [valid app identifier for the environment]

  Please re-create your resource with the appropiate tags.


  Thanks,
  AS CloudLab Team

"""
sg_validation_email_text = """

  Resource Validation Results
  ---------------------------

  Resource %s it attached to at least one Security Group which does not comply with CloudLab policies.
  The invalid Security Groups have been detached from your resource and will be deleted. Be aware this might cause your resource to lose connectivity

  Please remember Security Groups should not reference explicit CIDR blocks unless used for external Load Balancers

  In addition, the following tags are required for all Security Groups:

  Name
  Application = [valid app identifier for the environment]

  Please adjust your Security Groups accordingly or use the predefined ones.


  Thanks,
  AS CloudLab Team

"""
vpccleanup_subject = 'AS CloudLab - Weekly Cleanup'
vpcshutdown_subject = 'AS CloudLab - Daily Shutdown'
ADMIN_SNS_ARN = "arn:aws:sns:%s:%s:ValidateResources"

