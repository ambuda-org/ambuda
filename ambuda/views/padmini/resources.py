import functools

from vidyut.cheda import Chedaka
from vidyut.prakriya import Ashtadhyayi, Dhatupatha


@functools.cache
def get_chedaka():
    """A lazy singleton for our word splitter."""
    return Chedaka("/Users/akp/projects/vidyut/data/build/vidyut-0.2.0")


@functools.cache
def get_ashtadhyayi():
    """A lazy singleton for an Ashtadhyayi instance."""
    return Ashtadhyayi()


@functools.cache
def get_dhatupatha():
    """A lazy singleton for an Ashtadhyayi instance."""
    return Dhatupatha(
        "/Users/akp/projects/vidyut/data/build/vidyut-0.2.0/prakriya/dhatupatha.tsv"
    )
