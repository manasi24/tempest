import boto
import requests
from tempest_lib.common.utils import data_utils
from tempest import config
from tempest_lib import decorators
from tempest import test
from tempest.thirdparty.boto import base

CONF = config.CONF

class S3BucketsACLNegativeTest(base.BotoTestCase):

    credentials = ['primary', 'alt']
    
    @classmethod
    def setup_clients(cls):
        super(S3BucketsACLNegativeTest, cls).setup_clients()
        cls.client = cls.os.s3_client
        cls.alt_client = cls.os_alt.s3_client

    @classmethod
    def resource_setup(cls):
        super(S3BucketsACLNegativeTest, cls).resource_setup()
        cls.bucket_name = data_utils.rand_name("s3bucket")
        cls.bucket = cls.client.create_bucket(cls.bucket_name)
        cls.object_name = data_utils.rand_name("s3object")
        cls.object_s3 = cls.bucket.new_key(cls.object_name)
        cls.data = data_utils.arbitrary_string()
        cls.object_s3.set_contents_from_string(cls.data)
   
    @classmethod
    def resource_cleanup(cls):
        super(S3BucketsACLNegativeTest, cls).resource_cleanup()
        cls.destroy_bucket(cls.client.connection_data, cls.bucket)

    def tearDown(self):
        super(S3BucketsACLNegativeTest, self).tearDown()
        self.bucket.set_acl('private')

    def test_read_private_bucket(self):
        self.bucket.set_acl('private')
        self.assertBotoError(self.s3_error_code.client.AccessDenied,
                             self.alt_client.get_bucket, self.bucket_name)


    def test_get_object_from_bucket_with_public_read_acl(self):
        self.bucket.set_acl('public-read')
        bucket = self.alt_client.get_bucket(self.bucket_name)
        keys = bucket.get_all_keys()
        self.assertRaises(boto.exception.S3ResponseError,
                             bucket.get_key, self.object_name)
            
    def test_get_object_from_bucket_with_public_read_write_acl(self):
        self.bucket.set_acl('public-read-write')
        bucket = self.alt_client.get_bucket(self.bucket_name)
        self.assertRaises(boto.exception.S3ResponseError,
                             bucket.get_key, self.object_name)

    def test_get_bucket_having_authenticated_read_acl_using_anonymous_user(self):
        self.bucket.set_acl('authenticated-read')
        url = self.bucket.generate_url(1200)
        l = url.split("/")
        url = CONF.boto.s3_url.strip("/") + "/"  + "".join(l[3])
        resp = requests.get(url)
        self.assertEqual(403, resp.status_code)
