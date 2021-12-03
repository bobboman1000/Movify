import sys

import pandas as pd
from ytmusicapi import YTMusic
from MusicServicSource import LibraryObject


class YoutubeMusicSource:

    def __init__(self):
        try:
            self.ytmusic = YTMusic('headers_auth.json')
        except Exception:
            print("Cannot establish connection. Please check the integrity of your auth json.")
            sys.exit(1)

    def get_albums_library(self):
        albums_response = self.ytmusic.get_library_albums(limit=10000)
        albums = [self.parse_album(album) for album in albums_response]
        return albums

    def parse_album(self, album):
        return LibraryObject(album["title"], [artist["name"] for artist in album["artists"]],
                            album["year"], album["type"], yt_id=album["id"])

    def get_df(self, albums):
        if albums:
            return pd.DataFrame([album.__dict__ for album in albums])
        else:
            raise Exception("Albums not yet retrieved")