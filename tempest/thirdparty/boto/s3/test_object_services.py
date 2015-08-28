import os
import requests
import math
import boto

from tempest_lib.common.utils import data_utils
from tempest.thirdparty.boto import base
from tempest import config

CONF = config.CONF

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
        cls.object_name = data_utils.rand_name("s3object")
        cls.object_s3 = cls.bucket.new_key(cls.object_name)
        cls.data = data_utils.arbitrary_string()
        cls.object_s3.set_contents_from_string(cls.data)

    @classmethod
    def resource_cleanup(cls):
        super(S3BucketsTest, cls).resource_cleanup()
        cls.destroy_bucket(cls.client.connection_data, cls.bucket)

    def _create_bucket(self):
        bucket_name = data_utils.rand_name("s3bucket")
        bucket = self.client.create_bucket(bucket_name)
        self.addResourceCleanUp(self.destroy_bucket,
                                self.client.connection_data,
                                bucket_name)
        return bucket, bucket_name    
       
    def _create_object(self, bucket):
        object_name = data_utils.rand_name("s3object")
        object_s3 = bucket.new_key(object_name)
        self.addResourceCleanUp(bucket.delete_key,
                                object_name)
        return object_name, object_s3

    def _create_file(self, filename, filecontent):
        fp = open(filename, "w")
        fp.write(filecontent)
        fp.close()
        self.addResourceCleanUp(os.remove, filename)

    def test_create_object_with_string_data(self):
        # S3 Create object
        bucket, bucket_name = self._create_bucket()
        object_name, object_s3 = self._create_object(bucket)
        data = data_utils.arbitrary_string()
        object_s3.set_contents_from_string(data)
        readback = object_s3.get_contents_as_string()
        self.assertEqual(readback, data)

    def test_create_object_with_file_data(self):
        bucket, bucket_name = self._create_bucket()
        
        filecontent = "Testing create object with file data"
        filename = "test_file.txt"
        self._create_file(filename, filecontent)

        object_name, object_s3 = self._create_object(bucket)
        object_s3.set_contents_from_filename(filename) 
        body = object_s3.get_contents_as_string()
        self.assertEqual(body, filecontent)
        
    def test_get_object(self):
        readback = self.object_s3.get_contents_as_string()
        self.assertEqual(readback, self.data)

    def test_copy_object_in_same_bucket(self):
        dst_object_name, dst_object_s3 = self._create_object(self.bucket)
        self.bucket.copy_key(dst_object_name, self.bucket_name, self.object_name)
        body = dst_object_s3.get_contents_as_string()
        self.assertEqual(body, self.data)

    def test_copy_object_across_bucket(self):
        dst_bucket, dst_bucket_name = self._create_bucket()
        dst_object_name, dst_object_s3 = self._create_object(dst_bucket)
        dst_bucket.copy_key(dst_object_name, self.bucket_name, self.object_name)
        body = dst_object_s3.get_contents_as_string()
        self.assertEqual(body, self.data)
       

    def test_delete_object(self):
        object_name = data_utils.rand_name("s3object")
        object_s3 = self.bucket.new_key(object_name)
        data = data_utils.arbitrary_string()
        object_s3.set_contents_from_string(data)
        self.bucket.delete_key(object_name)
        self.assertBotoError(self.s3_error_code.client.NoSuchKey,
                                 object_s3.get_contents_as_string)

    def test_get_object_using_pre_signed_url(self):
        key_object = self.bucket.get_key(self.object_name)
        key_object.set_canned_acl('private')
        pre_signed_url = key_object.generate_url(120, query_auth=True)
        #temporary workaround to fix the presigned url
        l = pre_signed_url.split("/")
        pre_signed_url = CONF.boto.s3_url.strip("/") + "/" + "/".join(l[3:])
        r = requests.get(pre_signed_url)
        data = r.text
        self.assertEqual(200, r.status_code)
        self.assertEqual(data, self.data)

    def test_object_upload_in_multipart(self):
        object_size = 1024*1024*13
        filename = 'multipart_object.txt'
        chunk_size = 1024*1024*2
        filecontent = "a"*object_size
        self._create_file(filename, filecontent)

        # Create a multipart upload request
        mp = self.bucket.initiate_multipart_upload(filename)
        chunk_count = int(math.ceil(object_size / float(chunk_size)))

        for i in range(chunk_count):
            offset = chunk_size*i
            read_bytes = min(chunk_size, object_size - offset)
            with open(filename, 'r') as fp:
                fp.seek(offset)
                part = mp.upload_part_from_file(fp, part_num=i + 1, size=read_bytes)
                self.assertEqual(part.size, read_bytes, "part no %s was not "
                                                      "uploaded properly" % (i+1))
        # Finish the upload
        mp.complete_upload()
        multipart_obj = self.bucket.get_key(filename)
        self.assertEqual(multipart_obj.size, object_size)
