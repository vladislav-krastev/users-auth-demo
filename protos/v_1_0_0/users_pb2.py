# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: users.proto
# Protobuf Python Version: 5.27.2
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    27,
    2,
    '',
    'users.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0busers.proto\"!\n\x10\x41uthTokenRequest\x12\r\n\x05token\x18\x01 \x01(\t\"$\n\x10\x41uthTokenIsValid\x12\x10\n\x08is_valid\x18\x01 \x01(\x08\x32?\n\x05Users\x12\x36\n\x0cIsValidToken\x12\x11.AuthTokenRequest\x1a\x11.AuthTokenIsValid\"\x00\x62\x08\x65\x64itionsp\xe8\x07')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'users_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_AUTHTOKENREQUEST']._serialized_start=15
  _globals['_AUTHTOKENREQUEST']._serialized_end=48
  _globals['_AUTHTOKENISVALID']._serialized_start=50
  _globals['_AUTHTOKENISVALID']._serialized_end=86
  _globals['_USERS']._serialized_start=88
  _globals['_USERS']._serialized_end=151
# @@protoc_insertion_point(module_scope)
