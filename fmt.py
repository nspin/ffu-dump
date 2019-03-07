import struct
from collections import namedtuple

def make_struct(name, fields, byte_order='<'):
    field_names = []
    format_ = byte_order
    for field_name, field_format in fields:
        if field_name is not None:
            field_names.append(field_name)
        if field_format is not None:
            format_ += field_format

    class class_(namedtuple(name, field_names)):

        @classmethod
        def _read(cls, f):
            n = struct.calcsize(format_)
            buf = f.read(n)
            if len(buf) < n:
                raise Exception('not enough bytes')
            unpacked = struct.unpack(format_, buf)
            i = 0
            d = {}
            for field_name, field_format in fields:
                if field_format is None:
                    d[field_name] = None
                    continue
                if field_name is not None:
                    d[field_name] = unpacked[i]
                i += 1
            return cls(**d)._after(f)

        def _after(self, f):
            if self._check():
                return self
            else:
                raise Exception('check failed')

        def _check(self):
            return True

    return class_
