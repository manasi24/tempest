import requests
import re;

from tempest_lib.common.utils import data_utils
from tempest import config
from tempest_lib import decorators
from tempest import test
from tempest.thirdparty.boto import base

CONF = config.CONF

class S3BucketsACLTest(base.BotoTestCase):

    credentials = ['primary', 'alt']
    
    @classmethod
    def setup_clients(cls):
        super(S3BucketsACLTest, cls).setup_clients()
        cls.client = cls.os.s3_client
        cls.alt_client = cls.os_alt.s3_client

    @classmethod
    def resource_setup(cls):
        super(S3BucketsACLTest, cls).resource_setup()
        cls.bucket_name = data_utils.rand_name("s3bucket")
        cls.bucket = cls.client.create_bucket(cls.bucket_name)
        cls.object_name = data_utils.rand_name("s3object")
        cls.object_s3 = cls.bucket.new_key(cls.object_name)
        cls.data = data_utils.arbitrary_string()
        cls.object_s3.set_contents_from_string(cls.data)
        cls.cleanup_list = []
   
    @classmethod
    def resource_cleanup(cls):
        super(S3BucketsACLTest, cls).resource_cleanup()
        cls.destroy_bucket(cls.client.connection_data, cls.bucket)

    def tearDown(self):
        super(S3BucketsACLTest, self).tearDown()
        for item in self.cleanup_list[:]:
            item[0](item[1])
            self.cleanup_list.remove(item)
        self.bucket.set_acl('private')

    def test_bucket_acl_public_read(self):
        self.bucket.set_acl('public-read')
        url = self.bucket.generate_url(1200)
        #temporary workaround to fix the presigned url
        l = url.split("/")
        url = CONF.boto.s3_url.strip("/") + "/"  + "".join(l[3])
        resp = requests.get(url)
        self.assertEqual(200, resp.status_code) 
            
    def test_bucket_acl_public_read_write(self):
        self.bucket.set_acl('public-read-write')
        bucket = self.alt_client.get_bucket(self.bucket_name)
        object_name = data_utils.rand_name("s3object")
        object_s3 = bucket.new_key(object_name)
        data = data_utils.arbitrary_string()
        object_s3.set_contents_from_string(data)
        self.cleanup_list.append((bucket.delete_key, object_name))
        resp = object_s3.get_contents_as_string()
        self.assertEqual(data, resp)

    def test_bucket_acl_authenticated_read(self):
        self.bucket.set_acl('authenticated-read')
        bucket = self.alt_client.get_bucket(self.bucket_name)
        keys = bucket.get_all_keys()
        self.assertEqual(len(keys),1) 
