"""Helpers with regards to actions on the filesystem."""
import os
from contextlib import contextmanager
from typing import Iterator, Generator, Callable


@contextmanager
def cd(new_dir: str) -> Generator:
    """Context manager allowing an operation to be performed inside given directory.

    Args:
         new_dir: the directory to move into

    """
    prev_dir = os.getcwd()
    os.chdir(os.path.expanduser(new_dir))
    try:
        yield
    finally:
        os.chdir(prev_dir)


def walk_up_tree_to_root(starting_point: str) -> Iterator[str]:
    """Iterates from path to root.

    Args:
        starting_point: path from where to start.

    Returns:
        Iterator walking up the directory tree up to the root.
    """
    if not os.path.exists(starting_point):
        raise FileNotFoundError(starting_point)

    current_dir = os.path.realpath(
        starting_point if os.path.isdir(starting_point) else os.path.dirname(
            starting_point))

    previous_dir = None
    while previous_dir != current_dir:
        yield current_dir
        previous_dir = current_dir
        current_dir = os.path.dirname(current_dir)


def _get_directory_walk_method(top: bool) -> Callable[[str], Iterator[str]]:
    def walk_down_tree(start: str) -> Iterator[str]:
        for root, dirs, files in os.walk(start, followlinks=True):
            yield root

    return walk_up_tree_to_root if top else walk_down_tree


def find_file_in_tree(file_name: str,
                      starting_point: str = os.getcwd(),
                      top: bool = False) -> str:
    """Finds a file in directory tree.

    Args:
        file_name: name of the file to look for.
        starting_point: path from where to start the search
        top: search up the directory tree to root if True; down the tree otherwise.

    Returns:
            path of the file of interest.
    """
    if not file_name:
        raise ValueError('Undefined file name')

    iterator = _get_directory_walk_method(top)
    for directory in iterator(starting_point):
        file_path = os.path.join(directory, file_name)
        if os.path.exists(file_path):
            break
    else:
        raise FileNotFoundError(
            f'File [{file_name}] not found anywhere in directories {"above" if top else "under"} {starting_point}'
        )
    return file_path
