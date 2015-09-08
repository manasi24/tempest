from tempest_lib.common.utils import data_utils

from tempest import test
from tempest.thirdparty.boto import base

class S3BucketsNegativeTest(base.BotoTestCase):

    credentials = ['primary', 'alt']
    
    @classmethod
    def setup_clients(cls):
        super(S3BucketsNegativeTest, cls).setup_clients()
        cls.client = cls.os.s3_client
        cls.alt_client = cls.os_alt.s3_client

    @classmethod
    def resource_setup(cls):
        super(S3BucketsNegativeTest, cls).resource_setup()
        cls.bucket_name = data_utils.rand_name("s3bucket")
        cls.bucket = cls.client.create_bucket(cls.bucket_name)

    def test_create_bucket_with_existing_name_from_diff_tenant(self):
        self.assertBotoError(self.s3_error_code.client.BucketAlreadyExists,
                             self.alt_client.create_bucket, self.bucket_name)

    def test_delete_non_empty_bucket(self):
        object_name = data_utils.rand_name("s3object")
        object_s3 = self.bucket.new_key(object_name)
        data = data_utils.arbitrary_string()
        object_s3.set_contents_from_string(data)
        self.addResourceCleanUp(self.bucket.delete_key, object_name)
        self.assertBotoError(self.s3_error_code.client.BucketNotEmpty,
                             self.client.delete_bucket, self.bucket_name)
