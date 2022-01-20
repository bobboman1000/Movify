from typing import Union, List
from functools import reduce
import sys

import pandas as pd
from ytmusicapi import YTMusic
from MusicServicSource import LibraryObject


class YoutubeMusicSource:

    def __init__(self):
        try:
            self.ytmusic = YTMusic('headers_auth.json')
        except Exception as e:
            print("Cannot establish connection. Please check the integrity of your auth json. Error: \n")
            print(e)
            sys.exit(1)

    def get_albums_library(self) -> List[LibraryObject]:
        albums_response = self.ytmusic.get_library_albums(limit=10000)
        albums = [self.parse_album(album) for album in albums_response]
        return albums

    def get_playlists_library(self) -> pd.DataFrame:
        playlists = self._get_playlists_df()[["playlist_title", "playlist_id", "title", "artists", "duration"]]
        playlists["artists"] = self.parse_artists(playlists["artists"])
        return playlists

    def _get_playlists_df(self) -> pd.DataFrame:
        playlists_response = self.ytmusic.get_library_playlists(limit=50)

        dfs = []
        for playlist_obj in playlists_response:
            df = pd.DataFrame(self.ytmusic.get_playlist(playlist_obj["playlistId"])["tracks"])
            df.insert(0, "playlist_id", playlist_obj["playlistId"])
            df.insert(0, "playlist_title", playlist_obj["title"])
            dfs.append(df)

        return reduce(lambda a, b: a.append(b), dfs)

    def parse_album(self, album):
        return LibraryObject(album["title"], self.parse_artist(album["artists"]),
                            album["year"], album["type"], yt_id=album["browseId"])

    def parse_artist(self, object_artists_json) -> List[str]:
        return [object_artist["name"] for object_artist in list(object_artists_json)]

    def parse_artists(self, artists_json) -> List[List[str]]:
        return [self.parse_artist(object_artists) for object_artists in artists_json]

    def get_albums_df(self, albums):
        if albums:
            return pd.DataFrame([album.__dict__ for album in albums])
        else:
            raise Exception("Albums not yet retrieved")

