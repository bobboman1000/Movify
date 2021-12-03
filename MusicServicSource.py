from typing import List, Tuple


class LibraryObject:

    next_id = 0

    def __init__(self, name: str, artists: list[str], year: int, type: str, yt_id=None, sp_id=None):
        self.name = name
        self.year = year
        self.artists = artists
        self.type = type
        self.id = self.__get_new_id()
        self.yt_id = yt_id
        self.sp_id = sp_id

    @staticmethod
    def __get_new_id():
        LibraryObject.next_id += 1
        return LibraryObject.next_id - 1


class Playlist:

    next_id = 0

    def __init__(self, name: str, songs: List[Tuple[str, str]]):
        self.name = name
        self.id = self.__get_new_id()

    @staticmethod
    def __get_new_id():
        LibraryObject.next_id += 1
        return LibraryObject.next_id - 1
