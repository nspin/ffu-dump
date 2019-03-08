import itertools
from collections import namedtuple

from fmt import make_struct
from gpt import *

class SecurityHeader(make_struct('SecurityHeader', [
    ('cbSize', 'L'),
    ('signature', '12s'),
    ('dwChunkSizeInKb', 'L'),
    ('dwAlgId', 'L'),
    ('dwCatalogSize', 'L'),
    ('dwHashTableSize', 'L'),
    ])):

    def _check(self):
        return self.signature == b'SignedImage '

class ImageHeader(make_struct('ImageHeader', [
    ('cbSize', 'L'),
    ('signature', '12s'),
    ('ManifestLength', 'L'),
    ('dwChunkSize', 'L'),
    ])):
    
    def _check(self):
        return self.signature == b'ImageFlash  '

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
    # ('DevicePath'                    , None),
    ])

DiskLocation = make_struct('DiskLocation', [
    ('dwDiskAccessMethod', 'L'),
    ('dwBlockIndex', 'L'),
    ])

DISK_BEGIN = 0
DISK_END = 2

class BlockDataEntry(make_struct('BlockDataEntry', [
    ('dwLocationCount', 'L'),
    ('dwBlockCount', 'L'),
    ('rgDiskLocations', None),
    ])):

    def _after(self, f):
        rgDiskLocations = []
        for _ in range(self.dwLocationCount):
            rgDiskLocations.append(DiskLocation._read(f))
        return self._replace(rgDiskLocations=rgDiskLocations)

Meta = namedtuple('Meta', ['security_header', 'image_header', 'stores', 'block_data_start'])
Store = namedtuple('Store', ['store_header', 'block_data_entries'])

def read_meta(f):

    security_header = SecurityHeader._read(f)
    f.seek(security_header.dwCatalogSize, 1)
    f.seek(security_header.dwHashTableSize, 1)
    chunk_size = security_header.dwChunkSizeInKb * 1024
    advance_to_chunk_boundary(f, chunk_size)

    image_header = ImageHeader._read(f)
    f.seek(image_header.ManifestLength, 1)
    advance_to_chunk_boundary(f, security_header.dwChunkSizeInKb * 1024)

    stores = []
    for i in itertools.count(1):
        store_header = StoreHeader._read(f)
        f.seek(store_header.dwValidateDescriptorCount * store_header.dwValidateDescriptorLength, 1)
        block_data_entries = []
        for _ in range(store_header.dwWriteDescriptorCount):
            block_data_entries.append(BlockDataEntry._read(f))
        advance_to_chunk_boundary(f, chunk_size)
        stores.append(Store(store_header, block_data_entries))
        # V2
        # if i == store_header.NumOfStores:
        #     break
        break

    return Meta(security_header, image_header, stores, f.tell())

def advance_to_chunk_boundary(f, chunk_size):
    pos = f.tell()
    rem = pos % chunk_size
    if rem:
        f.seek(pos + chunk_size - rem)

def execute(meta, ffu, img):
    ffu.seek(meta.block_data_start)
    for store in meta.stores:
        block_size = store.store_header.dwBlockSizeInBytes
        for block_data_entry in store.block_data_entries:
            chunk = ffu.read(block_data_entry.dwBlockCount * block_size)
            for location in block_data_entry.rgDiskLocations:
                img.seek(location.dwBlockIndex * block_size, location.dwDiskAccessMethod)
                img.write(chunk)
