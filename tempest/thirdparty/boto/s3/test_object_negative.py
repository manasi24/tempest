import os
import requests
import math
import boto

from tempest_lib.common.utils import data_utils
from tempest.thirdparty.boto import base
from tempest import config

CONF = config.CONF

class S3ObjectsNegativeTest(base.BotoTestCase):

    credentials = ['primary', 'alt']

    @classmethod
    def setup_clients(cls):
        super(S3ObjectsNegativeTest, cls).setup_clients()
        cls.client = cls.os.s3_client
        cls.alt_client = cls.os_alt.s3_client

    @classmethod
    def resource_setup(cls):
        super(S3ObjectsNegativeTest, cls).resource_setup()
        cls.bucket_name = data_utils.rand_name("s3bucket")
        cls.bucket = cls.client.create_bucket(cls.bucket_name)
        cls.object_name = data_utils.rand_name("s3object")
        cls.object_s3 = cls.bucket.new_key(cls.object_name)
        cls.data = data_utils.arbitrary_string()
        cls.object_s3.set_contents_from_string(cls.data)

    @classmethod
    def resource_cleanup(cls):
        super(S3ObjectsNegativeTest, cls).resource_cleanup()
        cls.destroy_bucket(cls.client.connection_data, cls.bucket)

    def test_create_object_with_gt_1024_char(self):
        long_object_name = "a"*1025
        long_key = self.bucket.new_key(long_object_name)        
        self.assertRaises(boto.exception.S3ResponseError,
                          long_key.set_contents_from_string, "Invalid Name Length")

    def test_add_object_with_same_name_as_an_existing_one(self):
        old_data = self.data         
        new_data = "Replacing old object with new one"
        new_obj = self.bucket.new_key(self.object_name)
        new_obj.set_contents_from_string(new_data)
        text = new_obj.get_contents_as_string()
        self.assertEqual(new_data, text)

    def test_copy_object_from_private_bucket(self):
        alt_bucket_name = data_utils.rand_name("s3bucket")
        alt_bucket = self.alt_client.create_bucket(alt_bucket_name)
        self.assertBotoError(self.s3_error_code.client.AccessDenied,
                             alt_bucket.copy_key, "new_obj", self.bucket_name,
                             self.object_name)

    def test_copy_non_existing_object_to_bucket(self):
        self.bucket.set_acl('authenticated-read')
        alt_bucket_name = data_utils.rand_name("s3bucket")
        alt_bucket = self.alt_client.create_bucket(alt_bucket_name)
        self.assertBotoError(self.s3_error_code.client.NoSuchKey,
                             alt_bucket.copy_key, "new_key", 
                             self.bucket_name, "non_existing_object")

    def test_delete_object_without_permission(self):
        self.bucket.set_acl('authenticated-read')
        bucket = self.alt_client.get_bucket(self.bucket_name)
        self.assertBotoError(self.s3_error_code.client.AccessDenied,
                             bucket.delete_key, self.object_name)                    
    
    def test_get_object_without_permission(self):
        self.bucket.set_acl('authenticated-read')
        bucket = self.alt_client.get_bucket(self.bucket_name)
        self.assertRaises(boto.exception.S3ResponseError,
                          bucket.get_key, self.object_name) 

