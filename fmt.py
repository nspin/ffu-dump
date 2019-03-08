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

    base = namedtuple(name, field_names)):

    class class_(base):

        __name__ = base.__name__
        __qualname = base.__qualname__

        @classmethod
        def _read(cls, f):
            n = struct.calcsize(format_)
            buf = f.read(n)
            if len(buf) < n:
                raise Exception('not enough bytes')
            unpacked = iter(struct.unpack(format_, buf))
            field_values = {}
            for field_name, field_format in fields:
                if field_format is None:
                    value = None
                else:
                    value = next(unpacked)
                if field_name is not None:
                    field_values[field_name] = value
            return cls(**field_values)._after(f)

        def _after(self, f):
            if self._check():
                return self._modify(f)
            else:
                raise Exception('check failed')

        def _check(self):
            return True

        def _modify(self, f):
            return self

    return class_
