import requests
import boto

from tempest_lib.common.utils import data_utils
from tempest import config
from tempest_lib import decorators
from tempest import test
from tempest.thirdparty.boto import base

CONF = config.CONF

class S3ObjectsACLNegativeTest(base.BotoTestCase):

    credentials = ['primary', 'alt']
    
    @classmethod
    def setup_clients(cls):
        super(S3ObjectsACLNegativeTest, cls).setup_clients()
        cls.client = cls.os.s3_client
        cls.alt_client = cls.os_alt.s3_client

    @classmethod
    def resource_setup(cls):
        super(S3ObjectsACLNegativeTest, cls).resource_setup()
        cls.bucket_name = data_utils.rand_name("s3bucket")
        cls.bucket = cls.client.create_bucket(cls.bucket_name)
        cls.object_name = data_utils.rand_name("s3object")
        cls.object_s3 = cls.bucket.new_key(cls.object_name)
        cls.data = data_utils.arbitrary_string()
        cls.object_s3.set_contents_from_string(cls.data)
   
    @classmethod
    def resource_cleanup(cls):
        super(S3ObjectsACLNegativeTest, cls).resource_cleanup()
        cls.destroy_bucket(cls.client.connection_data, cls.bucket)

    def tearDown(self):
        super(S3ObjectsACLNegativeTest, self).tearDown()
        self.bucket.set_acl('private')
        self.object_s3.set_acl('private')

    def test_read_object_with_private_acl(self):
        self.bucket.set_acl('authenticated-read')
        bucket = self.alt_client.get_bucket(self.bucket_name)
        self.assertRaises(boto.exception.S3ResponseError,
                          bucket.get_key, self.object_name)
    
    def test_write_object_with_public_read_acl(self):
        self.bucket.set_acl('public-read')
        self.object_s3.set_acl('public-read')
        bucket = self.alt_client.get_bucket(self.bucket_name)
        key = bucket.get_key(self.object_name)
        self.assertBotoError(self.s3_error_code.client.AccessDenied,
                             key.set_contents_from_string, 
                             "testing write on object with public read acl")

    def test_get_object_having_authenticated_read_acl_using_anonymous_user(self):
        self.bucket.set_acl('authenticated-read')
        self.object_s3.set_canned_acl('authenticated-read')
        url = self.object_s3.generate_url(1200, query_auth=False)
        #temporary workaround to fix the presigned url
        l = url.split("/")
        url = CONF.boto.s3_url.strip("/") + "/" + "/".join(l[3:])
        r = requests.get(url)
        self.assertEqual(403, r.status_code)

    def test_copy_object_from_private_bucket(self):
        alt_bucket_name = data_utils.rand_name("s3bucket")
        alt_bucket = self.alt_client.create_bucket(alt_bucket_name)
        self.assertBotoError(self.s3_error_code.client.AccessDenied,
                             alt_bucket.copy_key, "new_obj", self.bucket_name,
                             self.object_name)

