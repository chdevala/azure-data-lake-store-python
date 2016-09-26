import hashlib
import logging
import os
import sys
import time

from adlfs import core, multithread
from adlfs.transfer import ADLTransferClient
from tests.testing import md5sum


def benchmark(f):
    def wrapped(*args, **kwargs):
        print('[%s] starting...' % (f.__name__))
        start = time.time()
        result = f(*args, **kwargs)
        stop = time.time()
        print('[%s] finished in %2.4fs' % (f.__name__, stop - start))
        return result

    return wrapped


def mock_client(adl, nthreads):
    def transfer(adlfs, src, dst, offset, size, blocksize, retries=5,
                 shutdown_event=None):
        pass

    def merge(adlfs, outfile, files, shutdown_event=None):
        pass

    return ADLTransferClient(
        adl,
        'foo',
        transfer=transfer,
        merge=merge,
        nthreads=nthreads)


def checksum(path):
    """ Generate checksum for file/directory content """
    if os.path.isfile(path):
        return md5sum(path)
    partial_sums = []
    for root, dirs, files in os.walk(path):
        for f in files:
            partial_sums.append(str.encode(md5sum(os.path.join(root, f))))
    return hashlib.md5(b''.join(sorted(partial_sums))).hexdigest()


def du(path):
    """ Find total size of content used by path """
    if os.path.isfile(path):
        return os.path.getsize(path)
    size = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            size += os.path.getsize(os.path.join(root, f))
    return size


def verify(adl, progress, lfile, rfile):
    """ Confirm whether target file matches source file """
    print("local file      :", lfile)
    print("local file size :", du(lfile))

    print("remote file     :", rfile)
    print("remote file size:", adl.du(rfile, total=True, deep=True))

    for f in progress:
        chunks_finished = 0
        for chunk in f.chunks:
            if chunk.state == 'finished':
                chunks_finished += 1
        print("[{:4d}/{:4d} chunks] {} -> {}".format(chunks_finished,
                                                     len(f.chunks),
                                                     f.src, f.dst))


@benchmark
def bench_upload_1_50gb(adl, lpath, rpath, nthreads):
    up = multithread.ADLUploader(
        adl,
        lpath=lpath,
        rpath=rpath,
        nthreads=nthreads)

    verify(adl, up.client.progress, lpath, rpath)


@benchmark
def bench_upload_50_1gb(adl, lpath, rpath, nthreads):
    up = multithread.ADLUploader(
        adl,
        lpath=lpath,
        rpath=rpath,
        nthreads=nthreads)

    verify(adl, up.client.progress, lpath, rpath)


@benchmark
def bench_download_1_50gb(adl, lpath, rpath, nthreads):
    down = multithread.ADLDownloader(
        adl,
        lpath=lpath,
        rpath=rpath,
        nthreads=nthreads)

    verify(adl, down.client.progress, lpath, rpath)


@benchmark
def bench_download_50_1gb(adl, lpath, rpath, nthreads):
    down = multithread.ADLDownloader(
        adl,
        lpath=lpath,
        rpath=rpath,
        nthreads=nthreads)

    verify(adl, down.client.progress, lpath, rpath)


if __name__ == '__main__':
    if len(sys.argv) <= 3:
        print("Usage: benchmarks.py local_path remote_path [nthreads]")
        sys.exit(1)

    localdir = sys.argv[1]
    remoteFolderName = sys.argv[2]
    nthreads = int(sys.argv[3]) if len(sys.argv) > 3 else None

    adl = core.AzureDLFileSystem()

    # Log only Azure messages, ignoring 3rd-party libraries
    logging.basicConfig(
        format='%(asctime)s %(name)-17s %(levelname)-8s %(message)s')
    logger = logging.getLogger('adlfs')
    logger.setLevel(logging.INFO)

    # Required setup until outstanding issues are resolved
    adl.mkdir(remoteFolderName)
    if adl.exists(remoteFolderName + '/50gbfile.txt'):
        adl.rm(remoteFolderName + '/50gbfile.txt')
    if adl.exists(remoteFolderName + '/50_1GB_Files'):
        adl.rm(remoteFolderName + '/50_1GB_Files', recursive=True)

    # Upload/download 1 50GB files

    lpath_up = os.path.join(localdir, '50gbfile.txt')
    lpath_down = os.path.join(localdir, '50gbfile.txt.out')
    rpath = remoteFolderName + '/50gbfile.txt'

    bench_upload_1_50gb(adl, lpath_up, rpath, nthreads)
    bench_download_1_50gb(adl, lpath_down, rpath, nthreads)
    print(checksum(lpath_up), lpath_up)
    print(checksum(lpath_down), lpath_down)

    # Upload/download 50 1GB files

    lpath_up = os.path.join(localdir, '50_1GB_Files')
    lpath_down = os.path.join(localdir, '50_1GB_Files.out')
    rpath = remoteFolderName + '/50_1GB_Files'

    bench_upload_50_1gb(adl, lpath_up, rpath, nthreads)
    bench_download_50_1gb(adl, lpath_down, rpath, nthreads)
    print(checksum(lpath_up), lpath_up)
    print(checksum(lpath_down), lpath_down)
