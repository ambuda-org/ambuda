import functools

from vidyut.cheda import Chedaka


@functools.cache
def get_chedaka():
    """A lazy singleton for our word splitter."""
    return Chedaka("/Users/akp/projects/vidyut/data/build/vidyut-0.2.0")
