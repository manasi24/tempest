# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import contextlib
import logging as orig_logging
import re

import boto
from boto import exception
from boto import s3
from oslo_log import log as logging
import six
from six.moves.urllib import parse as urlparse
from tempest_lib import exceptions as lib_exc

import tempest.clients
from tempest.common.utils import file_utils
from tempest import config
from tempest import exceptions
import tempest.test

CONF = config.CONF
LOG = logging.getLogger(__name__)


def decision_maker():
    S3_CAN_CONNECT_ERROR = None
    secret_matcher = re.compile("[A-Za-z0-9+/]{32,}")  # 40 in other system
    id_matcher = re.compile("[A-Za-z0-9]{20,}")

    def all_read(*args):
        return all(map(file_utils.have_effective_read_access, args))


    boto_logger = logging.getLogger('boto')
    level = boto_logger.logger.level
    # suppress logging for boto
    boto_logger.logger.setLevel(orig_logging.CRITICAL)

    def _cred_sub_check(connection_data):
        if not id_matcher.match(connection_data["aws_access_key_id"]):
            raise Exception("Invalid AWS access Key")
        if not secret_matcher.match(connection_data["aws_secret_access_key"]):
            raise Exception("Invalid AWS secret Key")
        raise Exception("Unknown (Authentication?) Error")
    # NOTE(andreaf) Setting up an extra manager here is redundant,
    # and should be removed.
    openstack = tempest.clients.Manager()
    try:
        if urlparse.urlparse(CONF.boto.s3_url).hostname is None:
            raise Exception("Failed to get hostname from the s3_url")
        s3client = openstack.s3_client
        try:
            s3client.get_bucket("^INVALID*#()@INVALID.")
        except exception.BotoServerError as exc:
            if exc.status == 403:
                _cred_sub_check(s3client.connection_data)
    except Exception as exc:
        S3_CAN_CONNECT_ERROR = str(exc)
    except lib_exc.Unauthorized:
        S3_CAN_CONNECT_ERROR = "AWS credentials not set," +\
                               " failed to get them even by keystoneclient"
    boto_logger.logger.setLevel(level)
    return {'S3_CAN_CONNECT_ERROR': S3_CAN_CONNECT_ERROR}


class BotoExceptionMatcher(object):
    STATUS_RE = r'[45]\d\d'
    CODE_RE = '.*'  # regexp makes sense in group match

    def match(self, exc):
        """:returns: Returns with an error string if it does not match,
               returns with None when it matches.
        """
        if not isinstance(exc, exception.BotoServerError):
            return "%r not an BotoServerError instance" % exc
        LOG.info("Status: %s , error_code: %s", exc.status, exc.error_code)
        if re.match(self.STATUS_RE, str(exc.status)) is None:
            return ("Status code (%s) does not match"
                    "the expected re pattern \"%s\""
                    % (exc.status, self.STATUS_RE))
        if re.match(self.CODE_RE, str(exc.error_code)) is None:
            return ("Error code (%s) does not match" +
                    "the expected re pattern \"%s\"") %\
                   (exc.error_code, self.CODE_RE)
        return None


class ClientError(BotoExceptionMatcher):
    STATUS_RE = r'4\d\d'


class ServerError(BotoExceptionMatcher):
    STATUS_RE = r'5\d\d'


def _add_matcher_class(error_cls, error_data, base=BotoExceptionMatcher):
    """
        Usable for adding an ExceptionMatcher(s) into the exception tree.
        The not leaf elements does wildcard match
    """
    # in error_code just literal and '.' characters expected
    if not isinstance(error_data, six.string_types):
        (error_code, status_code) = map(str, error_data)
    else:
        status_code = None
        error_code = error_data
    parts = error_code.split('.')
    basematch = ""
    num_parts = len(parts)
    max_index = num_parts - 1
    add_cls = error_cls
    for i_part in six.moves.xrange(num_parts):
        part = parts[i_part]
        leaf = i_part == max_index
        if not leaf:
            match = basematch + part + "[.].*"
        else:
            match = basematch + part

        basematch += part + "[.]"
        if not hasattr(add_cls, part):
            cls_dict = {"CODE_RE": match}
            if leaf and status_code is not None:
                cls_dict["STATUS_RE"] = status_code
            cls = type(part, (base, ), cls_dict)
            setattr(add_cls, part, cls())
            add_cls = cls
        elif leaf:
            raise LookupError("Tries to redefine an error code \"%s\"" % part)
        else:
            add_cls = getattr(add_cls, part)


# TODO(afazekas): classmethod handling
def friendly_function_name_simple(call_able):
    name = ""
    if hasattr(call_able, "im_class"):
        name += call_able.im_class.__name__ + "."
    name += call_able.__name__
    return name


def friendly_function_call_str(call_able, *args, **kwargs):
    string = friendly_function_name_simple(call_able)
    string += "(" + ", ".join(map(str, args))
    if len(kwargs):
        if len(args):
            string += ", "
    string += ", ".join("=".join(map(str, (key, value)))
                        for (key, value) in kwargs.items())
    return string + ")"


class BotoTestCase(tempest.test.BaseTestCase):
    """Recommended to use as base class for boto related test."""

    credentials = ['primary']

    @classmethod
    def skip_checks(cls):
        super(BotoTestCase, cls).skip_checks()
        if not CONF.compute_feature_enabled.ec2_api:
            raise cls.skipException("The EC2 API is not available")
        if not CONF.identity_feature_enabled.api_v2 or \
                not CONF.identity.auth_version == 'v2':
            raise cls.skipException("Identity v2 is not available")

    @classmethod
    def resource_setup(cls):
        super(BotoTestCase, cls).resource_setup()
        cls.conclusion = decision_maker()
        # The trash contains cleanup functions and paramaters in tuples
        # (function, *args, **kwargs)
        cls._resource_trash_bin = {}
        cls._sequence = -1
        if (hasattr(cls, "S3") and
            cls.conclusion['S3_CAN_CONNECT_ERROR'] is not None):
            raise cls.skipException("S3 " + cls.__name__ + ": " +
                                    cls.conclusion['S3_CAN_CONNECT_ERROR'])

    @classmethod
    def addResourceCleanUp(cls, function, *args, **kwargs):
        """Adds CleanUp callable, used by tearDownClass.
        Recommended to a use (deep)copy on the mutable args.
        """
        cls._sequence = cls._sequence + 1
        cls._resource_trash_bin[cls._sequence] = (function, args, kwargs)
        return cls._sequence

    @classmethod
    def cancelResourceCleanUp(cls, key):
        """Cancel Clean up request."""
        del cls._resource_trash_bin[key]

    # TODO(afazekas): Add "with" context handling
    def assertBotoError(self, excMatcher, callableObj,
                        *args, **kwargs):
        """Example usage:
            self.assertBotoError(self.ec2_error_code.client.
                                 InvalidKeyPair.Duplicate,
                                 self.client.create_keypair,
                                 key_name)
        """
        try:
            callableObj(*args, **kwargs)
        except exception.BotoServerError as exc:
            error_msg = excMatcher.match(exc)
            if error_msg is not None:
                raise self.failureException(error_msg)
        else:
            raise self.failureException("BotoServerError not raised")

    @classmethod
    def resource_cleanup(cls):
        """Calls the callables added by addResourceCleanUp,
        when you overwrite this function don't forget to call this too.
        """
        fail_count = 0
        trash_keys = sorted(cls._resource_trash_bin, reverse=True)
        for key in trash_keys:
            (function, pos_args, kw_args) = cls._resource_trash_bin[key]
            try:
                func_name = friendly_function_call_str(function, *pos_args,
                                                       **kw_args)
                LOG.debug("Cleaning up: %s" % func_name)
                function(*pos_args, **kw_args)
            except BaseException:
                fail_count += 1
                LOG.exception("Cleanup failed %s" % func_name)
            finally:
                del cls._resource_trash_bin[key]
        super(BotoTestCase, cls).resource_cleanup()
        # NOTE(afazekas): let the super called even on exceptions
        # The real exceptions already logged, if the super throws another,
        # does not causes hidden issues
        if fail_count:
            raise exceptions.TearDownException(num=fail_count)

    s3_error_code = BotoExceptionMatcher()
    s3_error_code.server = ServerError()
    s3_error_code.client = ClientError()

    gone_set = set(('_GONE',))

    def assertReSearch(self, regexp, string):
        if re.search(regexp, string) is None:
            raise self.failureException("regexp: '%s' not found in '%s'" %
                                        (regexp, string))

    def assertNotReSearch(self, regexp, string):
        if re.search(regexp, string) is not None:
            raise self.failureException("regexp: '%s' found in '%s'" %
                                        (regexp, string))

    def assertReMatch(self, regexp, string):
        if re.match(regexp, string) is None:
            raise self.failureException("regexp: '%s' not matches on '%s'" %
                                        (regexp, string))

    def assertNotReMatch(self, regexp, string):
        if re.match(regexp, string) is not None:
            raise self.failureException("regexp: '%s' matches on '%s'" %
                                        (regexp, string))

    @classmethod
    def destroy_bucket(cls, connection_data, bucket):
        """Destroys the bucket and its content, just for teardown."""
        exc_num = 0
        try:
            with contextlib.closing(
                    boto.connect_s3(**connection_data)) as conn:
                if isinstance(bucket, basestring):
                    bucket = conn.lookup(bucket)
                    assert isinstance(bucket, s3.bucket.Bucket)
                for obj in bucket.list():
                    try:
                        bucket.delete_key(obj.key)
                        obj.close()
                    except BaseException:
                        LOG.exception("Failed to delete key %s " % obj.key)
                        exc_num += 1
            conn.delete_bucket(bucket)
        except BaseException:
            LOG.exception("Failed to destroy bucket %s " % bucket)
            exc_num += 1
        if exc_num:
            raise exceptions.TearDownException(num=exc_num)

# you can specify tuples if you want to specify the status pattern
for code in (('AccessDenied', 403),
             ('AccountProblem', 403),
             ('AmbiguousGrantByEmailAddress', 400),
             ('BadDigest', 400),
             ('BucketAlreadyExists', 409),
             ('BucketAlreadyOwnedByYou', 409),
             ('BucketNotEmpty', 409),
             ('CredentialsNotSupported', 400),
             ('CrossLocationLoggingProhibited', 403),
             ('EntityTooSmall', 400),
             ('EntityTooLarge', 400),
             ('ExpiredToken', 400),
             ('IllegalVersioningConfigurationException', 400),
             ('IncompleteBody', 400),
             ('IncorrectNumberOfFilesInPostRequest', 400),
             ('InlineDataTooLarge', 400),
             ('InvalidAccessKeyId', 403),
             'InvalidAddressingHeader',
             ('InvalidArgument', 400),
             ('InvalidBucketName', 400),
             ('InvalidBucketState', 409),
             ('InvalidDigest', 400),
             ('InvalidLocationConstraint', 400),
             ('InvalidPart', 400),
             ('InvalidPartOrder', 400),
             ('InvalidPayer', 403),
             ('InvalidPolicyDocument', 400),
             ('InvalidRange', 416),
             ('InvalidRequest', 400),
             ('InvalidSecurity', 403),
             ('InvalidSOAPRequest', 400),
             ('InvalidStorageClass', 400),
             ('InvalidTargetBucketForLogging', 400),
             ('InvalidToken', 400),
             ('InvalidURI', 400),
             ('KeyTooLong', 400),
             ('MalformedACLError', 400),
             ('MalformedPOSTRequest', 400),
             ('MalformedXML', 400),
             ('MaxMessageLengthExceeded', 400),
             ('MaxPostPreDataLengthExceededError', 400),
             ('MetadataTooLarge', 400),
             ('MethodNotAllowed', 405),
             ('MissingAttachment'),
             ('MissingContentLength', 411),
             ('MissingRequestBodyError', 400),
             ('MissingSecurityElement', 400),
             ('MissingSecurityHeader', 400),
             ('NoLoggingStatusForKey', 400),
             ('NoSuchBucket', 404),
             ('NoSuchKey', 404),
             ('NoSuchLifecycleConfiguration', 404),
             ('NoSuchUpload', 404),
             ('NoSuchVersion', 404),
             ('NotSignedUp', 403),
             ('NotSuchBucketPolicy', 404),
             ('OperationAborted', 409),
             ('PermanentRedirect', 301),
             ('PreconditionFailed', 412),
             ('Redirect', 307),
             ('RequestIsNotMultiPartContent', 400),
             ('RequestTimeout', 400),
             ('RequestTimeTooSkewed', 403),
             ('RequestTorrentOfBucketError', 400),
             ('SignatureDoesNotMatch', 403),
             ('TemporaryRedirect', 307),
             ('TokenRefreshRequired', 400),
             ('TooManyBuckets', 400),
             ('UnexpectedContent', 400),
             ('UnresolvableGrantByEmailAddress', 400),
             ('UserKeyMustBeSpecified', 400)):
    _add_matcher_class(BotoTestCase.s3_error_code.client,
                       code, base=ClientError)


for code in (('InternalError', 500),
             ('NotImplemented', 501),
             ('ServiceUnavailable', 503),
             ('SlowDown', 503)):
    _add_matcher_class(BotoTestCase.s3_error_code.server,
                       code, base=ServerError)
