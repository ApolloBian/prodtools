import io
import logging
import os
import shlex
import shutil
import subprocess
from contextlib import contextmanager

HADOOP_BIN = '/opt/tiger/yarn_deploy/hadoop/bin/hadoop'
_HADOOP_COMMAND_TEMPLATE = 'hadoop fs {command}'
_SUPPORTED_HDFS_PATH_PREFIXES = ('hdfs://', 'ufs://')




def open(filepath: str, mode: str = "r"):
    if not filepath.startswith("hdfs://"):
        return io.open(filepath, mode)
    return hopen(filepath, mode)


def mv(srcpath, tgtpath):
    if tgtpath.startswith("hdfs://"):
        os.system("hdfs dfs -put {} {}".format(srcpath, tgtpath))
    else:
        os.system("mv {} {}".format(srcpath, tgtpath))


def mkdir(filepath):
    if not filepath.startswith("hdfs://"):
        if not os.path.exists(filepath):
            os.makedirs(filepath)
    else:
        os.system('hdfs dfs -mkdir -p {}'.format(filepath))


@contextmanager
def hopen(hdfs_path: str, mode: str = "r"):
    pipe = None
    if mode.startswith("r"):
        pipe = subprocess.Popen(
            "{} fs -text {}".format(HADOOP_BIN, hdfs_path), shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        yield pipe.stdout
        pipe.stdout.close()
        pipe.wait()
        return
    if mode == "wa":
        pipe = subprocess.Popen(
            "{} fs -appendToFile - {}".format(HADOOP_BIN, hdfs_path), shell=True, stdin=subprocess.PIPE)
        yield pipe.stdin
        pipe.stdin.close()
        pipe.wait()
        return
    if mode.startswith("w"):
        pipe = subprocess.Popen(
            "{} fs -put -f - {}".format(HADOOP_BIN, hdfs_path), shell=True, stdin=subprocess.PIPE)
        yield pipe.stdin
        pipe.stdin.close()
        pipe.wait()
        return
    raise RuntimeError("unsupported io mode: {}".format(mode))


def _get_hdfs_command(command):
    """return hadoop fs command"""
    return _HADOOP_COMMAND_TEMPLATE.format(command=command)


def check_call_hdfs_command(command):
    """check call hdfs command"""
    hdfs_command = _get_hdfs_command(command)
    subprocess.check_call(shlex.split(hdfs_command))


def popen_hdfs_command(command):
    """call hdfs command with popen and return stdout result"""
    hdfs_command = _get_hdfs_command(command)
    p = subprocess.Popen(shlex.split(hdfs_command), stdout=subprocess.PIPE)
    stdout, _ = p.communicate()
    return stdout


def has_hdfs_path_prefix(filepath):
    """Check if input filepath has hdfs prefix"""
    for prefix in _SUPPORTED_HDFS_PATH_PREFIXES:
        if filepath.startswith(prefix):
            return True
    return False


def is_hdfs_file(filepath):
    """check if input filepath is hdfs file"""
    if os.path.exists(filepath):
        # is local path, return False
        return False
    cmd = '-test -f {}'.format(filepath)
    try:
        check_call_hdfs_command(cmd)
        return True
    except Exception:
        return False


def is_hdfs_dir(filepath):
    """check if input filepath is hdfs directory"""
    if os.path.exists(filepath):
        # is local path, return False
        return False
    cmd = '-test -d {}'.format(filepath)
    try:
        check_call_hdfs_command(cmd)
        return True
    except Exception:
        return False


def get_hdfs_list(filepath):
    """glob hdfs path pattern"""
    try:
        cmd = '-ls {}'.format(filepath)
        stdout = popen_hdfs_command(cmd)
        lines = stdout.splitlines()
        if lines:
            # decode bytes string in python3 runtime
            lines = [line.decode('utf-8') for line in lines]
            return [line.split(' ')[-1] for line in lines[1:]]
        else:
            return []
    except Exception:
        return []


def glob_hdfs_pattern(filepath):
    """glob hdfs path pattern"""
    try:
        cmd = '-ls -d {}'.format(filepath)
        stdout = popen_hdfs_command(cmd)
        lines = stdout.splitlines()
        if lines:
            # decode bytes string in python3 runtime
            lines = [line.decode('utf-8') for line in lines]
            return [line.split(' ')[-1] for line in lines]
        else:
            return []
    except Exception:
        return []


def get_hdfs_path_sizes(filepath):
    """get sizes of all paths by globing input filepath"""
    try:
        cmd = '-ls -d {}'.format(filepath)
        stdout = popen_hdfs_command(cmd)
        lines = stdout.splitlines()
        if lines:
            # decode bytes string in python3 runtime
            paths_to_sizes = {}
            lines = [line.decode('utf-8') for line in lines]
            for line in lines:
                ret = line.split(' ')
                path = ret[-1]
                size = int(ret[-4])
                paths_to_sizes[path] = size
            return paths_to_sizes
        else:
            return {}
    except Exception:
        return {}


def mkdir_hdfs(dirpath, raise_exception=False):
    """mkdir hdfs directory"""
    try:
        cmd = '-mkdir -p {}'.format(dirpath)
        check_call_hdfs_command(cmd)
        return True
    except Exception as e:
        msg = 'Failed to mkdir {} in HDFS: {}'.format(dirpath, e)
        if raise_exception:
            raise ValueError(msg)
        else:
            logging.error(msg)
        return False


def makedirs_local_or_hdfs(dirpath, name='dirpath'):
    """makdirs hdfs dir or local FS dir"""
    if has_hdfs_path_prefix(dirpath):
        if not is_hdfs_dir(dirpath):
            mkdir_hdfs(dirpath, raise_exception=True)
    elif not os.path.isdir(dirpath):
        os.makedirs(dirpath)


def download_from_hdfs(src_path, dst_path, raise_exception=False):
    """download src_path from hdfs to local dst_path"""
    if not has_hdfs_path_prefix(src_path):
        raise ValueError(
            'Input src_path {} is not a valid hdfs path'.format(src_path))
    if has_hdfs_path_prefix(dst_path):
        raise ValueError(
            'Input dst_path {} is a hdfs path, not a path for local FS'.format(dst_path))

    try:
        cmd = '-get {} {}'.format(src_path, dst_path)
        check_call_hdfs_command(cmd)
        return True
    except Exception as e:
        msg = 'Failed to download src {} to dst {}: {}'.format(
            src_path, dst_path, e)
        if raise_exception:
            raise ValueError(msg)
        else:
            logging.error(msg)
        return False


def upload_to_hdfs(src_path, dst_path, overwrite=False, raise_exception=False):
    """Upload src_path to hdfs dst_path"""
    if not os.path.exists(src_path):
        raise IOError(
            'Input src_path {} not found in local storage'.format(src_path))
    if not has_hdfs_path_prefix(dst_path):
        raise ValueError(
            'Input dst_path {} is not a hdfs path'.format(dst_path))

    try:
        cmd = '-put -f' if overwrite else '-put'
        cmd = '{} {} {}'.format(cmd, src_path, dst_path)
        check_call_hdfs_command(cmd)
        return True
    except Exception as e:
        msg = 'Failed to upload src {} to dst {}: {}'.format(
            src_path, dst_path, e)
        if raise_exception:
            raise ValueError(msg)
        else:
            logging.error(msg)
        return False


def copy_hdfs(src_path, dst_path, overwrite=False, raise_exception=False):
    """Copy hdfs src_path to hdfs dst_path."""
    if not has_hdfs_path_prefix(src_path):
        raise ValueError(
            'Input src_path {} is not a hdfs path'.format(src_path))
    if not has_hdfs_path_prefix(dst_path):
        raise ValueError(
            'Input dst_path {} is not a hdfs path'.format(dst_path))

    try:
        cmd = '-cp -f' if overwrite else '-cp'
        cmd = '{} {} {}'.format(cmd, src_path, dst_path)
        check_call_hdfs_command(cmd)
        return True
    except Exception as e:
        msg = 'Failed to copy src {} to dst {}: {}'.format(
            src_path, dst_path, e)
        if raise_exception:
            raise ValueError(msg)
        else:
            logging.error(msg)
        return False


def mv_hdfs(src_path, dst_path, raise_exception=False):
    """Move hdfs src_path to hdfs dst_path."""
    if not has_hdfs_path_prefix(src_path):
        raise ValueError(
            'Input src_path {} is not a hdfs path'.format(src_path))
    if not has_hdfs_path_prefix(dst_path):
        raise ValueError(
            'Input dst_path {} is not a hdfs path'.format(dst_path))

    try:
        cmd = '-mv {} {}'.format(src_path, dst_path)
        check_call_hdfs_command(cmd)
        return True
    except Exception as e:
        msg = 'Failed to copy src {} to dst {}: {}'.format(
            src_path, dst_path, e)
        if raise_exception:
            raise ValueError(msg)
        else:
            logging.error(msg)
        return False


def rm_hdfs(hdfs_path, recursive=False, raise_exception=False):
    """Remove hdfs path."""
    if not has_hdfs_path_prefix(hdfs_path):
        raise ValueError('given path {} is not a hdfs path'.format(hdfs_path))

    try:
        tag = '-rm -r' if recursive else '-rm'
        cmd = '{} {}'.format(tag, hdfs_path)
        check_call_hdfs_command(cmd)
        return True
    except Exception as e:
        msg = 'Failed to remove {}: {}'.format(hdfs_path, e)
        if raise_exception:
            raise ValueError(msg)
        else:
            logging.error(msg)
        return False
