import sys
import struct
import operator
import itertools
from collections import namedtuple

def make_struct(name, fields, check=None):
    field_names = []
    format_ = '<'
    for field_name, field_format in fields:
        field_names.append(field_name)
        format_ += field_format

    class class_(namedtuple(name, field_names)):

        _format = format_

        @classmethod
        def _read(cls, f):
            buf = f.read(struct.calcsize(format_))
            r = cls._make(struct.unpack(format_, buf))
            if check is not None and not check(r):
                raise Exception('check for', name, 'failed on', r)
            return r

    return class_

SecurityHeader = make_struct('SecurityHeader', [
    ('cbSize', 'L'),
    ('signature', '12s'),
    ('dwChunkSizeInKb', 'L'),
    ('dwAlgId', 'L'),
    ('dwCatalogSize', 'L'),
    ('dwHashTableSize', 'L'),
    ], lambda r: r.signature == b'SignedImage ')

ImageHeader = make_struct('ImageHeader', [
    ('cbSize', 'L'),
    ('signature', '12s'),
    ('ManifestLength', 'L'),
    ('dwChunkSize', 'L'),
    ], lambda r: r.signature == b'ImageFlash  ')

StoreHeader = make_struct('StoreHeader', [
    ('dwUpdateType'                  , 'L'),
    ('MajorVersion'                  , 'H'),
    ('MinorVersion'                  , 'H'),
    ('FullFlashMajorVersion'         , 'H'),
    ('FullFlashMinorVersion'         , 'H'),
    ('szPlatformId'                  , '192s'),
    ('dwBlockSizeInBytes'            , 'L'),
    ('dwWriteDescriptorCount'        , 'L'),
    ('dwWriteDescriptorLength'       , 'L'),
    ('dwValidateDescriptorCount'     , 'L'),
    ('dwValidateDescriptorLength'    , 'L'),
    ('dwInitialTableIndex'           , 'L'),
    ('dwInitialTableCount'           , 'L'),
    ('dwFlashOnlyTableIndex'         , 'L'),
    ('dwFlashOnlyTableCount'         , 'L'),
    ('dwFinalTableIndex'             , 'L'),
    ('dwFinalTableCount'             , 'L'),
    # V2
    # ('NumOfStores'                   , 'H'),
    # ('StoreIndex'                    , 'H'),
    # ('StorePayloadSize'              , 'Q'),
    # ('DevicePathLength'              , 'H'),
    ])

BlockDataEntry = make_struct('BlockDataEntry', [
    ('dwLocationCount', 'L'),
    ('dwBlockCount', 'L'),
    ])

DiskLocation = make_struct('DiskLocation', [
    ('dwDiskAccessMethod', 'L'),
    ('dwBlockIndex', 'L'),
    ])

DISK_BEGIN = 0
DISK_END = 2

class BlockDataEntry_(namedtuple('BlockDataEntry_', ['block_data_entry', 'rgDiskLocations'])):
    @classmethod
    def _read(cls, f):
        block_data_entry = BlockDataEntry._read(f)
        rgDiskLocations = []
        for _ in range(block_data_entry.dwLocationCount):
            rgDiskLocations.append(DiskLocation._read(f))
        return cls(block_data_entry, rgDiskLocations)

Meta = namedtuple('Meta', ['security_header', 'image_header', 'store_meta', 'block_data_start'])
StoreMeta = namedtuple('StoreMeta', ['store_header', 'device_path', 'block_data_entries'])

def advance_to_chunk_boundary(f, chunk_size):
    pos = f.tell()
    rem = pos % chunk_size
    if rem:
        f.seek(pos + chunk_size - rem)

def read_meta(f):

    security_header = SecurityHeader._read(f)
    f.seek(security_header.dwCatalogSize, 1)
    f.seek(security_header.dwHashTableSize, 1)
    chunk_size = security_header.dwChunkSizeInKb * 1024
    advance_to_chunk_boundary(f, chunk_size)

    image_header = ImageHeader._read(f)
    f.seek(image_header.ManifestLength, 1)
    advance_to_chunk_boundary(f, security_header.dwChunkSizeInKb * 1024)

    store_meta = []
    for i in itertools.count(1):
        store_header = StoreHeader._read(f)
        # V2
        # device_path = f.read(store_header.DevicePathLength * 2)
        device_path = None
        f.seek(store_header.dwValidateDescriptorCount * store_header.dwValidateDescriptorLength, 1)
        block_data_entries = []
        for _ in range(store_header.dwWriteDescriptorCount):
            block_data_entries.append(BlockDataEntry_._read(f))
        advance_to_chunk_boundary(f, chunk_size)
        store_meta.append(StoreMeta(store_header, device_path, block_data_entries))
        # V2
        # if i == store_header.NumOfStores:
        #     break
        break

    return Meta(security_header, image_header, store_meta, f.tell())

def image_size(meta):
    max_end = 0
    for store_meta in meta.store_meta:
        for block_data_entry in store_meta.block_data_entries:
            for location in block_data_entry.rgDiskLocations:
                print(location.dwDiskAccessMethod)
                if location.dwDiskAccessMethod == DISK_BEGIN:
                    end = (location.dwBlockIndex + block_data_entry.block_data_entry.dwBlockCount) * store_meta.store_header.dwBlockSizeInBytes
                    max_end = max(max_end, end)
    return max_end

def nearest_gb(n):
    gb = 2**30
    return (n // gb + 1) * gb

def execute(meta, f, out):
    for store_meta in meta.store_meta:
        block_size = store_meta.store_header.dwBlockSizeInBytes
        for block_data_entry in store_meta.block_data_entries:
            chunk = f.read(block_data_entry.block_data_entry.dwBlockCount * block_size)
            for location in block_data_entry.rgDiskLocations:
                if location.dwDiskAccessMethod == DISK_BEGIN:
                    pos = (location.dwBlockIndex * block_size, location.dwDiskAccessMethod)
                    out.seek(*pos)
                    out.write(chunk)

# def execute(meta, f, out):
#     for store_meta in meta.store_meta:
#         block_size = store_meta.store_header.dwBlockSizeInBytes
#         for block_data_entry in store_meta.block_data_entries:
#             chunk = f.read(block_data_entry.block_data_entry.dwBlockCount * block_size)
#             for location in block_data_entry.rgDiskLocations:
#                 pos = (location.dwBlockIndex * block_size, location.dwDiskAccessMethod)
#                 print(pos)
#                 out.seek(*pos)
#                 out.write(chunk)

# def inspect(meta):
#     for store_meta in meta.store_meta:
#         block_size = store_meta.store_header.dwBlockSizeInBytes
#         for block_data_entry in store_meta.block_data_entries:
#             for location in block_data_entry.rgDiskLocations:
#                 pos = (location.dwBlockIndex * block_size, location.dwDiskAccessMethod)
#                 print(pos)

ffu_path = '../lumia/RM1104_1078.0053.10586.13169.12745.034D72_retail_prod_signed.ffu'
# out_path = 'out.img'
out_path = 'out2.img'
with open(ffu_path, 'rb') as ffu:
    meta = read_meta(ffu)
    # inspect(meta)
    print(image_size(meta))
    # with open(out_path, 'wb') as out:
    #     out.seek(0)
    #     execute(meta, ffu, out)
    # with open(out_path, 'ab') as out:
    #     out.seek(0)
    #     execute(meta, ffu, out)
