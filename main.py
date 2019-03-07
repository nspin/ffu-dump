import io
from ffu import *
from gpt import *

def get_final_gpt(store, f, block_data_start, lba_size):
    hdr = store.store_header
    block_size = hdr.dwBlockSizeInBytes
    index = hdr.dwFinalTableIndex
    count = hdr.dwFinalTableCount
    f.seek(block_data_start + index * block_size)
    raw = f.read(count * block_size)
    raw_gpt = raw[raw.index(b'EFI PART'):]
    return parse_gpt(io.BytesIO(raw_gpt), lba_size=lba_size)

def guess_dev_size(meta, f):
    assert len(meta.stores) == 1
    store = meta.stores[0]
    gpt = get_final_gpt(store, f, meta.block_data_start, lba_size=lba_size)
    lba_count = gpt.header.backup_lba + 1 # how robust is this?
    return lba_count * lba_size

def ffu_to_img(meta, ffu, img):
    size = guess_dev_size(meta, ffu)
    img.seek(size - 1)
    img.write(b'\0')

lba_size = 512

ffu_path = 'test.ffu'
img_path = 'test.img'
with open(ffu_path, 'rb') as ffu:
    meta = read_meta(ffu)
    size = guess_dev_size(meta, ffu)
    print('size: {} MB'.format(size / 2**20))
    with open(img_path, 'wb') as img:
        img.seek(size - 1)
        img.write(b'\0')
        execute(meta, ffu, img)
