from typing import Union, List
from functools import reduce
import sys

import pandas as pd
from ytmusicapi import YTMusic
from MusicServicSource import AlbumObject


class YoutubeMusicSource:

    def __init__(self):
        try:
            self.ytmusic = YTMusic('headers_auth.json')
        except Exception as e:
            print("Cannot establish connection. Please check the integrity of your auth json. Error: \n")
            print(e)
            sys.exit(1)

    def get_albums_library_df(self) -> pd.DataFrame:
        albums_response = self.ytmusic.get_library_albums(limit=10000)
        albums = pd.DataFrame(albums_response)
        albums["artists"] = self.parse_artists(albums["artists"])
        albums = albums.drop(["browseId", "thumbnails"], axis=1)
        return albums

    def get_albums_library(self) -> List[AlbumObject]:
        albums = self.get_albums_library_df()
        album_list = []
        for idx, row in albums.iterrows():
            album = AlbumObject(row["title"], row["artists"], row["year"], row["type"])
            album_list.append(album)
        return album_list

    def get_playlists_library(self) -> pd.DataFrame:
        playlists = self._get_playlists_df()[["playlist_title", "playlist_id", "title", "artists", "duration"]]
        playlists["artists"] = self.parse_artists(playlists["artists"])
        return playlists

    def _get_playlists_df(self) -> pd.DataFrame:
        playlists_response = self.ytmusic.get_library_playlists(limit=30)

        dfs = []
        for playlist_obj in playlists_response:
            df = pd.DataFrame(self.ytmusic.get_playlist(playlist_obj["playlistId"])["tracks"])
            df.insert(0, "playlist_id", playlist_obj["playlistId"])
            df.insert(0, "playlist_title", playlist_obj["title"])
            dfs.append(df)
        return reduce(lambda a, b: a.append(b), dfs)

    def parse_album(self, album):
        return AlbumObject(album["title"], self.parse_artist(album["artists"]),
                           album["year"], album["type"], yt_id=album["browseId"])

    @staticmethod
    def parse_artist(object_artists_json) -> List[str]:
        return [object_artist["name"] for object_artist in list(object_artists_json)]

    @staticmethod
    def parse_artists(artists_json, as_str=True) -> Union[list[str], list[list[str]]]:
        if as_str:
            return [str(YoutubeMusicSource.parse_artist(object_artists)) for object_artists in list(artists_json)]
        else:
            return [YoutubeMusicSource.parse_artist(object_artists) for object_artists in list(artists_json)]
