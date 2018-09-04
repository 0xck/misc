import os
import sys
import logging
import mmap
import stat


def path_validation(path, length):
    """Validation and normalization of given path

    Args:
        path (unicode): Path to file
        length (unicode): Max possible path length

    Returns:
        str: normalized path

    Raises:
        ValueError
    """
    # For windows long name prefix `\\?\` will be added

    # normilizers for given path
    normilizers = [
        os.path.expandvars,
        os.path.expanduser,
        os.path.normpath,
        os.path.normcase]

    # empty path is not allowed
    if not path:
        raise ValueError("Empty path")

    # support of long name in windows
    # adding long name `\\?\` prefix
    if sys.platform.startswith('win') and not path.startswith(u"\\\\?\\"):
        path = u"\\\\?\\" + path

    # getting normilized path
    path = reduce(lambda a, f: f(a), normilizers, path)

    # path is too long
    if len(path) > length:
        raise ValueError(
            "Path <{}> is too long <{}>. Max path length is <{}>".format(path, len(path), length))

    # path is not regular file
    if os.path.exists(path) and not stat.S_ISREG(os.stat(path).st_mode):
        raise ValueError("Path <{}> is not a regular file".format(path))

    return path


def get_mmsrc(src):
    """Source mmap creation

    Args:
        src (str): Path to file

    Returns:
        mmap.mmap: mmap obj of source file for current platform
    """

    # win mmap is different than *nix
    if sys.platform.startswith('win') or sys.platform.startswith('cygwin'):
        return mmap.mmap(src.fileno(), 0, None, mmap.ACCESS_READ, 0)

    # *nix mmap
    return mmap.mmap(src.fileno(), 0, mmap.MAP_SHARED, mmap.PROT_READ, 0, 0)


def mmcopy(src_path, dst_path, buffer, rm_on_err=True):
    """Copy using mmap

    Args:
        src_path (str): Path to source file
        src_path (str): Path to destination file
        buffer (int): Copy buffer size
        rm_on_err (bool): If set, deleting destination file on error or interruption. Default is True.

    Returns:
        None

    Raises:
        Exception: excluding KeyboardInterrupt
    """

    # preserving UnboundLocalError
    mmsrc, err = None, None

    try:
        with open(src_path, mode="rb", buffering=0) as src, open(dst_path, mode="w+b", buffering=0) as dst:

            mmsrc = get_mmsrc(src)

            chunk = mmsrc.read(buffer)

            # writing with chunks
            while chunk:

                dst.write(chunk)

                chunk = mmsrc.read(buffer)

    except KeyboardInterrupt as err:
        logging.info("Ctrl+C interruption")

    # there are many type of errors can happened and mmap objs have to be closed in all cases
    except Exception as err:
        logging.error("An error occured during copy file")
        logging.exception(err)

    finally:
        getattr(mmsrc, "close", lambda: None)()

        # deleting dst
        if err is not None and os.path.exists(dst_path):
            logging.info("Removing destination <{}>".format(dst_path))

            os.remove(dst_path)

        # raising exceptions excluding KeyboardInterrupt
        if err is not None and err is not KeyboardInterrupt:
            raise


def user_input():
    """Simple user input function. One asks for source and destination paths.

    Returns:
        tuple(unicode, unicode): Source and destination paths
    """
    try:
        return (raw_input("Enter source file path: ").decode(sys.stdin.encoding),
                raw_input("Enter destination file path: ").decode(sys.stdin.encoding))

    # in case of interruption
    except EOFError:
        return u'', u''


def copy(src_path, dst_path, src_len=1024, dst_len=3096,
            save_perm=False, rm_on_err=True,
            buffer=(512 * mmap.PAGESIZE),
            validate=path_validation, copy_engine=mmcopy):
    """Copy file, using especial engine defined in args, default is copy by using mmap.

    Args:
        src_path (unicode): Source path to file
        dst_path (unicode): Destination Path to file
        src_len (int): Max possible source path length
        dst_len (int): Max possible destination path length
        save_perm (bool): Copy file permissions from source to destination
        rm_on_err (bool): If set, deleting destination file on copy error or interruption. Default is True
        buffer (int): Copy buffer size. Default is 2Mb, that is heuristic value, individual for each system
        validate (function): Function validates and normilizes given paths. Default is path_validation
        copy_engine (function): Funtion copies files. Default is mmcopy

    Returns:
        None

    Raises:
        ValueError: if path validation failed

    Source file permissions may be copied to destination, use `save_perm`.
    By default if copy error occured destination file is deleted, use `rm_on_err` to chenge this behavior
    """

    # buffer has to be related power 2
    # buffer has to be more or equal system mem pagesize
    if not (buffer and not (buffer & (buffer - 1))) or buffer < mmap.PAGESIZE:
        msg = "Wrong buffer size. One has to be aligned by power of 2 and more or equal <{}>".format(mmap.PAGESIZE)
        logging.error(msg)

        raise ValueError(msg)

    # validating paths
    try:
        src = validate(src_path, src_len)
        dst = validate(dst_path, dst_len)

    except ValueError as err:
        logging.error("Paths validation faled")
        logging.exception(err)

        raise

    if not os.path.exists(src):
        msg = "Source file <{}> does not exist".format(src)
        logging.error(msg)

        raise ValueError(msg)

    # checking if same file
    if os.path.exists(dst) and getattr(os.path, "samefile", lambda a, b: a == b)(src, dst):
        msg = "Source file <{}> is the same as destination file <{}>".format(src, dst)
        logging.error(msg)

        raise ValueError(msg)

    logging.info("Starting copy <{}> to <{}>".format(src, dst))

    # copy file
    copy_engine(src, dst, buffer, rm_on_err)

    logging.info("Copy done")

    # setting destination file permissions
    if save_perm:
        os.chmod(dst, stat.S_IMODE(os.stat(src).st_mode))

        logging.info("Permission on destination file changed")
