"""
pathlib.PathInfo from 3.14
"""

from errno import EPERM, ENOTSUP, ENODATA, EINVAL, EACCES
import os
from stat import S_ISDIR, S_ISREG, S_ISLNK, S_IMODE


class _PathInfoBase:
    __slots__ = ("_path", "_stat_result", "_lstat_result")

    _stat_result: os.stat_result | None
    _lstat_result: os.stat_result | None

    def __init__(self, path):
        self._path = str(path)

    def __repr__(self):
        path_type = "WindowsPath" if os.name == "nt" else "PosixPath"
        return f"<{path_type}.info>"

    def _stat(self, *, follow_symlinks=True, ignore_errors=False):
        """Return the status as an os.stat_result, or None if stat() fails and
        ignore_errors is true."""
        if follow_symlinks:
            try:
                result = self._stat_result
            except AttributeError:
                pass
            else:
                if ignore_errors or result is not None:
                    return result
            try:
                self._stat_result = os.stat(self._path)
            except (OSError, ValueError):
                self._stat_result = None
                if not ignore_errors:
                    raise
            return self._stat_result
        else:
            try:
                result = self._lstat_result
            except AttributeError:
                pass
            else:
                if ignore_errors or result is not None:
                    return result
            try:
                self._lstat_result = os.lstat(self._path)
            except (OSError, ValueError):
                self._lstat_result = None
                if not ignore_errors:
                    raise
            return self._lstat_result

    def _posix_permissions(self, *, follow_symlinks=True):
        """Return the POSIX file permissions."""
        return S_IMODE(self._stat(follow_symlinks=follow_symlinks).st_mode)

    def _file_id(self, *, follow_symlinks=True):
        """Returns the identifier of the file."""
        st = self._stat(follow_symlinks=follow_symlinks)
        return st.st_dev, st.st_ino

    def _access_time_ns(self, *, follow_symlinks=True):
        """Return the access time in nanoseconds."""
        return self._stat(follow_symlinks=follow_symlinks).st_atime_ns

    def _mod_time_ns(self, *, follow_symlinks=True):
        """Return the modify time in nanoseconds."""
        return self._stat(follow_symlinks=follow_symlinks).st_mtime_ns

    if hasattr(os.stat_result, "st_flags"):

        def _bsd_flags(self, *, follow_symlinks=True):
            """Return the flags."""
            return self._stat(follow_symlinks=follow_symlinks).st_flags

    if hasattr(os, "listxattr"):

        def _xattrs(self, *, follow_symlinks=True):
            """Return the xattrs as a list of (attr, value) pairs, or an empty
            list if extended attributes aren't supported."""
            try:
                return [
                    (
                        attr,
                        os.getxattr(self._path, attr, follow_symlinks=follow_symlinks),
                    )
                    for attr in os.listxattr(
                        self._path, follow_symlinks=follow_symlinks
                    )
                ]
            except OSError as err:
                if err.errno not in (EPERM, ENOTSUP, ENODATA, EINVAL, EACCES):
                    raise
                return []


class _WindowsPathInfo(_PathInfoBase):
    """Implementation of pathlib.types.PathInfo that provides status
    information for Windows paths. Don't try to construct it yourself."""

    __slots__ = ("_exists", "_is_dir", "_is_file", "_is_symlink")

    _exists: bool
    _is_symlink: bool

    def exists(self, *, follow_symlinks=True):
        """Whether this path exists."""
        if not follow_symlinks and self.is_symlink():
            return True
        try:
            return self._exists
        except AttributeError:
            if os.path.exists(self._path):
                self._exists = True
                return True
            else:
                self._exists = self._is_dir = self._is_file = False
                return False

    def is_dir(self, *, follow_symlinks=True):
        """Whether this path is a directory."""
        if not follow_symlinks and self.is_symlink():
            return False
        try:
            return self._is_dir
        except AttributeError:
            if os.path.isdir(self._path):
                self._is_dir = self._exists = True
                return True
            else:
                self._is_dir = False
                return False

    def is_file(self, *, follow_symlinks=True):
        """Whether this path is a regular file."""
        if not follow_symlinks and self.is_symlink():
            return False
        try:
            return self._is_file
        except AttributeError:
            if os.path.isfile(self._path):
                self._is_file = self._exists = True
                return True
            else:
                self._is_file = False
                return False

    def is_symlink(self):
        """Whether this path is a symbolic link."""
        try:
            return self._is_symlink
        except AttributeError:
            self._is_symlink = os.path.islink(self._path)
            return self._is_symlink


class _PosixPathInfo(_PathInfoBase):
    """Implementation of pathlib.types.PathInfo that provides status
    information for POSIX paths. Don't try to construct it yourself."""

    __slots__ = ()

    def exists(self, *, follow_symlinks=True):
        """Whether this path exists."""
        st = self._stat(follow_symlinks=follow_symlinks, ignore_errors=True)
        if st is None:
            return False
        return True

    def is_dir(self, *, follow_symlinks=True):
        """Whether this path is a directory."""
        st = self._stat(follow_symlinks=follow_symlinks, ignore_errors=True)
        if st is None:
            return False
        return S_ISDIR(st.st_mode)

    def is_file(self, *, follow_symlinks=True):
        """Whether this path is a regular file."""
        st = self._stat(follow_symlinks=follow_symlinks, ignore_errors=True)
        if st is None:
            return False
        return S_ISREG(st.st_mode)

    def is_symlink(self):
        """Whether this path is a symbolic link."""
        st = self._stat(follow_symlinks=False, ignore_errors=True)
        if st is None:
            return False
        return S_ISLNK(st.st_mode)


PathInfo = _WindowsPathInfo if os.name == "nt" else _PosixPathInfo
