from tempest_lib.common.utils import data_utils

from tempest import test
from tempest.thirdparty.boto import base

class S3BucketsTest(base.BotoTestCase):

    @classmethod
    def setup_clients(cls):
        super(S3BucketsTest, cls).setup_clients()
        cls.client = cls.os.s3_client

    @classmethod
    def resource_setup(cls):
        super(S3BucketsTest, cls).resource_setup()
        cls.bucket_name = data_utils.rand_name("s3bucket")
        cls.bucket = cls.client.create_bucket(cls.bucket_name)

    def test_create_bucket(self):
        bucket_name = data_utils.rand_name("s3bucket")
        bucket = self.client.create_bucket(bucket_name)
        self.addResourceCleanUp(self.client.delete_bucket,
                                              bucket_name)
        self.assertTrue(bucket.name == bucket_name)

    def test_get_bucket(self):
        bucket_get = self.client.get_bucket(self.bucket_name)
        self.assertTrue(bucket_get.name == self.bucket_name)

    def test_delete_empty_bucket(self):
        bucket_name = data_utils.rand_name("s3bucket")
        self.client.create_bucket(bucket_name)
        cleanup_key = self.addResourceCleanUp(self.client.delete_bucket,
                                              bucket_name)
        self.client.delete_bucket(bucket_name)
        self.assertBotoError(self.s3_error_code.client.NoSuchBucket,
                             self.client.get_bucket, bucket_name)
        self.cancelResourceCleanUp(cleanup_key)
