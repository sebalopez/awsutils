# This module exists just to provide singleton boto3 clients, shared across modules.
# Clients are created on demand, and a single copy of each exists at any point in time.
# An application / module wanting its own client (maybe with different access keys or region) can still
# create its own clients using boto3 directly.

# The mechanism used here is described by Guido Van Rossum himself at
# https://mail.python.org/pipermail/python-ideas/2012-May/015069.html

# It has a downside: replacing sys.modules[__name__] first destroys the current object stored there
# (i.e. this module), and during that process Python sets to None all module-global variables
# This is described here:
# http://stackoverflow.com/questions/5365562/why-is-the-value-of-name-changing-after-assignment-to-sys-modules-name
# To prevent that, which has nasty effects like setting boto3 to None, thus breaking the __getattr__ method,
# we first save a reference to the current module in 'ref'

import boto3
import sys


class boto3_clients(object):

    def __getattr__(self, attr):
        if attr == 'account_id':
            attr_value = self.sts.get_caller_identity()['Account']
        elif attr == 'region':
            # if the default session is None, it means no client was created
            # so we force the creation of a client.
            attr_value = getattr(boto3.DEFAULT_SESSION, 'region_name', None)
            if attr_value is None:
                self.ec2
                return self.region
        else:
            attr_value = boto3.client(attr)

        setattr(self, attr, attr_value)
        return attr_value 

ref = sys.modules[__name__]
sys.modules[__name__] = boto3_clients()

