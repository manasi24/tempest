from tempest_lib.common.utils import data_utils

from tempest import test
from tempest.thirdparty.boto import base

class S3BucketsNameTest(base.BotoTestCase):

    @classmethod
    def setup_clients(cls):
        super(S3BucketsNameTest, cls).setup_clients()
        cls.client = cls.os.s3_client

    def test_create_bucket_with_lt_3_char(self):
        bucket_name = "a"*2
        self.assertBotoError(self.s3_error_code.client.InvalidBucketName,
                             self.client.create_bucket, bucket_name)
        
    def test_create_bucket_with_gt_255_char(self):
        bucket_name = "a"*256
        self.assertBotoError(self.s3_error_code.client.InvalidBucketName,
                             self.client.create_bucket, bucket_name)
        
    def test_create_bucket_with_name_as_ip_addr(self):
        bucket_name = "192.168.5.4"
        self.assertBotoError(self.s3_error_code.client.InvalidBucketName,
                             self.client.create_bucket, bucket_name)
        
    def test_create_bucket_name_starting_with_non_alnum(self):
        bucket_name = ".mybucket"
        self.assertBotoError(self.s3_error_code.client.InvalidBucketName,
                             self.client.create_bucket, bucket_name)

    def test_create_bucket_with_name_having_two_adjacent_hyphen_or_period(self):
        #bucket_name = "my..examplebucket"
        bucket_name = "my......"
        self.assertBotoError(self.s3_error_code.client.InvalidBucketName,
                             self.client.create_bucket, bucket_name)
