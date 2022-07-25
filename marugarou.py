#!/usr/bin/env python3
# libmarugarou (lib丸刈ろう) — a reader for CLIP STUDIO PAINT files
# This library is still very unstable!

# (c) 2022 Fredrick R. Brennan
# Based on code (c) 2019 Rasen Suihei (MIT-licensed)
# ###############################################################################
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use
# this software or any of the provided source code files except in compliance
# with the License.  You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations under the License.

import sys
import struct
import os
import logging
import zlib

CSF_CHUNK = b'CSFCHUNK'
CHUNK_HEADER = b'CHNKHead'
CHUNK_EXTERNAL = b'CHNKExta'
CHUNK_SQLITE = b'CHNKSQLi'
CHUNK_FOOTER = b'CHNKFoot'

BLOCK_DATA_BEGIN_CHUNK = 'BlockDataBeginChunk'.encode('utf-16be')
BLOCK_DATA_END_CHUNK = 'BlockDataEndChunk'.encode('utf-16be')
BLOCK_STATUS = 'BlockStatus'.encode('utf-16be')
BLOCK_CHECK_SUM = 'BlockCheckSum'.encode('utf-16be')

clip_header_spec = struct.Struct('>8sQQ')
chunk_header_spec = struct.Struct('>8sQ')
external_header_spec = struct.Struct('>Q40sQ')
block_test_spec = struct.Struct('>II')
uint_spec = struct.Struct('>I')
uint_spec2 = struct.Struct('<I')
block_header_spec = struct.Struct('>I12xI')

def __read(struct, infile, pos):
    buff = infile.read(struct.size)
    data = struct.unpack_from(buff)
    return (data, pos + struct.size)

def __pipe_file(outdir, filename, infile, length):
    outfile = open(os.path.join(outdir, filename), 'wb')
    inp = infile.read(length)
    try:
        inp = zlib.decompress(inp)
    except:
        pass
    outfile.write(inp)
    outfile.close()

def split_clip(path, outdir, options):
    basedir, filename = os.path.split(path)
    ext_index = filename.rfind('.')
    if ext_index < 0:
        return
    without_ext = filename[:ext_index]
    outdir = os.path.join(basedir, without_ext)
    os.makedirs(outdir, exist_ok=True)
    infile = open(path, 'rb')
    pos = 0
    data, pos = __read(clip_header_spec, infile, pos)
    _, filesize, _ = data
    while pos < filesize:
        oldpos = pos
        data, pos = __read(chunk_header_spec, infile, pos)
        chunk_type, length = data
        logging.debug('{0:X}: {1} ({2} = {2:X})'.format(oldpos, chunk_type.decode('UTF-8'), length))
        if chunk_type == CHUNK_HEADER:
            __pipe_file(outdir, 'header', infile, length)
        if chunk_type == CHUNK_SQLITE:
            __pipe_file(outdir, without_ext + '.sqlite3', infile, length)
        elif chunk_type == CHUNK_EXTERNAL:
            data, pos2 = __read(external_header_spec, infile, pos)
            _, external_id, data_size = data
            external_id_str = external_id.decode('UTF-8')
            logging.debug('  {0} ({1} = {1:X})'.format(external_id_str, data_size))
            if options.blockdata:
                __read_blockdata(infile, pos2, length, external_id_str, outdir, options)
                infile.seek(pos2)
            else:
                __pipe_file(outdir, external_id_str, infile, data_size)
        pos = infile.seek(pos + length)
    infile.close()

def __read_blockdata(infile, pos, length, external_id, outdir, options):
    end_pos = pos + length
    while pos < end_pos:
        test_data, pos = __read(block_test_spec, infile, pos)
        a, b = test_data
        if b == uint_spec.unpack(BLOCK_DATA_BEGIN_CHUNK[:uint_spec.size])[0]:
            str_length = a
            pos = infile.seek(pos - uint_spec.size)
        else:
            str_length = b
            data_length = a
        bd_id = infile.read(str_length * 2)
        pos += str_length * 2
        if bd_id == BLOCK_DATA_BEGIN_CHUNK:
            logging.debug('  {0}'.format(infile.peek(block_header_spec.size)[:block_header_spec.size].hex()))
            data, pos = __read(block_header_spec, infile, pos)
            block_index, not_empty = data
            if not_empty > 0:
                data, pos = __read(uint_spec, infile, pos)
                block_length = data[0]
                logging.debug('  BlockDataBeginChunk {0} ({1} = {1:X})'.format(block_index, block_length))
                (data_length,), pos = __read(uint_spec2, infile, pos)
                __pipe_file(outdir, '{0}.{1:04}'.format(external_id, block_index), infile, data_length)
                pos += data_length
            else:
                logging.debug('  BlockDataBeginChunk {0} (empty)'.format(block_index))
        elif bd_id == BLOCK_DATA_END_CHUNK:
            logging.debug('  BlockDataEndChunk')
        elif bd_id == BLOCK_STATUS:
            logging.debug('  BlockStatus')
            pos = infile.seek(pos + 28)
        elif bd_id == BLOCK_CHECK_SUM:
            logging.debug('  BlockCheckSum')
            pos = infile.seek(pos + 28)
            return
        else:
            logging.error('Unknown block of length {0} skipped'.format(str_length))
            return

def __main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', help='print verbose log')
    parser.add_argument('--blockdata', action='store_true', help='split blockdata')
    targets = parser.add_argument_group('targets')
    targets.add_argument('-c', '--clip', type=str, help='clip file')
    targets.add_argument('-d', '--dir', type=str, help='splitted data direcotry')
    args = parser.parse_args()
    logging.basicConfig(format='%(message)s', level=logging.DEBUG if args.verbose else logging.ERROR)
    def err(msg):
        print(msg)
        parser.print_usage()
    if not args.clip:
        err('You have to specify -c|--clip.')
        return
    split_clip(args.clip, args.dir, args)

if __name__ == '__main__':
    __main()

