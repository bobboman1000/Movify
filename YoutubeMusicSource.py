import sys

import pandas as pd
from ytmusicapi import YTMusic
from MusicServicSource import LibraryObject


class YoutubeMusicSource:

    def __init__(self):
        self.albums = None
        self.library = pd.DataFrame(columns=["name", "artists", "type", "ytm_id"])
        try:
            self.ytmusic = YTMusic('headers_auth.json')
        except Exception:
            print("Cannot establish connection. Please check the integrity of your auth json.")
            sys.exit(1)

    def fetch_albums_library(self):
        albums_response = self.ytmusic.get_library_albums(limit=10000)
        parse_album = lambda album: LibraryObject(album["title"], [artist["name"] for artist in album["artists"]], album["year"], album["type"])
        self.albums = [parse_album(album) for album in albums_response]
        return self.albums

    def get_df(self):
        if self.albums:
            return pd.DataFrame([album.__dict__ for album in self.albums])
        else:
            raise Exception("Albums not yet retrieved")



yt = YoutubeMusicSource()
test = yt.get_playlists()