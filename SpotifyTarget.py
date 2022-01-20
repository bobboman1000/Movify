from getpass import getpass
from typing import Tuple, List
import spotipy
import re
from tqdm import tqdm
from spotipy import SpotifyOAuth

from MusicServicSource import AlbumObject
import numpy as np
import pandas as pd
import logging

from YoutubeMusicSource import YoutubeMusicSource


class SpotifyTarget:
    min_score = 3  # Smaller than 4
    max_album_post = 50

    song_response_mapper = {"name": "title", "artists": "artists", "id": "id"}

    def __init__(self, client_id=None, client_secret=None):
        self.internal_id_to_spotify_id = dict()
        self.artists_name_to_spotify_id_map = dict()
        if client_id is None or client_secret is None:
            client_id = input("Client id:")
            client_secret = getpass()
        auth_manager = spotipy.SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        self.logger = logging.getLogger("DEBUG")

    def add_playlists_to_library(self, playlists: pd.DataFrame, client_id, client_secret, redirect_uri):

        auth_sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id, client_secret, redirect_uri, username="benno385",
                                                            scope="playlist-modify-private"))
        playlists = playlists.dropna()
        playlists.sort_values(by=["playlist_title"])
        curr_playlist = None
        start_idx = None
        for curr_idx, row in playlists.iterrows():
            if curr_playlist is None:
                curr_playlist = row["playlist_title"]
                continue
            if row["playlist_title"] != curr_playlist or curr_idx == playlists.shape[0] - 1:
                curr_playlist = row["playlist_title"]
                playlist_songs = playlists.iloc[start_idx:curr_idx, :]
                song_ids = playlist_songs["spotify_id"]
                start_idx = curr_idx
                response = auth_sp.user_playlist_create(auth_sp.current_user()["id"], curr_playlist, public=False)

                new_playlist_id = response["id"]
                auth_sp.playlist_add_items(new_playlist_id, song_ids)

    def get_spotify_song_ids(self, df: pd.DataFrame) -> List[str]:
        song_ids_add = []
        songs_not_found = []

        if df.empty:
            return []

        found, ambiguous, not_found = 0, 0, 0

        print("Looking up songs on spotify...")
        for idx, target_song in tqdm(df.iterrows(), total=df.shape[0]):
            song, score = self.search_for_song(target_song)
            if score > 0:
                song_ids_add.append(song["id"])
                found += 1
            elif score <= 0:
                not_found += 1
                songs_not_found.append(target_song)
                song_ids_add.append(pd.NA)

        for song in songs_not_found:
            print(f"Song {song['title']}, {song['artists']} in playlist {song['playlist_title']}"
                  f" was not found.")

        return song_ids_add

    def search_for_song(self, song: pd.Series):
        search_string = song["title"] + " " + str(song["artists"]).replace("[", "").replace("]", "").replace("\'", "")
        response = self.sp.search(search_string, type="track")
        candidates = pd.DataFrame(response["tracks"]["items"])

        if candidates.empty:
            return None, -1

        candidates["artists"] = YoutubeMusicSource.parse_artists(candidates["artists"])
        attr_filtered_candidates = candidates[self.song_response_mapper]
        attr_filtered_candidates = attr_filtered_candidates.rename(columns=self.song_response_mapper)

        best_candidate, score = self.select_best_candidate(song, attr_filtered_candidates)
        return best_candidate, score

    def select_best_candidate(self, target_item: pd.Series, candidates: pd.DataFrame):
        scores = [self.similarity_score_df(row, target_item) for idx, row in candidates.iterrows()]

        if len(scores) > 0:
            best_hit_index = np.argmax(scores)
            best_hit_score = scores[best_hit_index]
            best_hit = candidates.iloc[best_hit_index, :]
        else:
            best_hit = pd.Series()
            best_hit_score = 0

        return best_hit, best_hit_score

    @staticmethod
    def found_item_message(item, result_code):
        if result_code == -1:
            return f"\033[1;32;40m Found: {item['title']} by {str(item['artists'])} \033[0;37;40m"
        elif result_code == 0:
            return f"\033[1;33;40m Ambiguous result for {item['title']} by {str(item['artists'])} \033[0;37;40m"
        elif result_code == 1:
            return f"\033[1;33;40m Not found {item['title']} by {str(item['artists'])} \033[0;37;40m"

    ######### Album workflow ###########

    def add_albums_to_library(self, spotify_ids: List[AlbumObject], client_id, client_secret, redirect_uri):
        auth_sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id, client_secret, redirect_uri,
                                                            scope="user-library-modify"))
        batches = int(len(spotify_ids) / 50)
        for i in range(batches + 1):
            lower_idx = i * 50

            full_upper_idx = (i + 1) * 50
            upper_idx = full_upper_idx if full_upper_idx <= len(spotify_ids) - 1 else len(spotify_ids) - 1
            auth_sp.current_user_saved_albums_add(spotify_ids[lower_idx:upper_idx])

    def get_spotify_album_ids(self, albums: list[AlbumObject]):
        album_ids_add: list[int] = []
        review_album_list: list[Tuple[AlbumObject, AlbumObject, int]] = []

        found, ambiguous, not_found = 0, 0, 0

        print("Looking up albums on spotify...")
        for target_album in tqdm(albums):
            best_candidate, score = self.search_for_album(target_album)
            if score >= self.min_score:
                album_ids_add.append(self.internal_id_to_spotify_id[best_candidate.id])
                self.logger.debug("\033[1;32;40m Found album: " + target_album.name + " by " + str(target_album.artists)
                                  + "\033[0;37;40m")
                found += 1
            elif score > 0:
                review_album_list.append((best_candidate, target_album, score))
                self.logger.debug("\033[1;33;40m Ambiguous result for " + target_album.name + " by "
                                  + str(target_album.artists) + "\033[0;37;40m")
                ambiguous += 1
            else:
                self.logger.debug("\034[1;31;40m Not found " + target_album.name + " by " + str(target_album.artists)
                                  + "\033[0;37;40m")
                not_found += 1

        print(f"Results: \t \034[1;32;40m {found} \034[1;37;40m found, \034[1;33;40m {ambiguous} "
              f"\034[1;37;40m ambiguous, \034[1;31;40m {not_found} \034[1;37;40m not found \n")

        confirmed_albums = self.eliminate_dialogue(review_album_list)
        confirmed_albums = [self.internal_id_to_spotify_id[review_album_tuple[0].id] for review_album_tuple in
                            confirmed_albums]
        album_ids_add += confirmed_albums

        return album_ids_add

    def get_spotify_album_ids_series(self, albums: list[AlbumObject]):
        pd.Series(self.get_spotify_album_ids(albums))

    def eliminate_dialogue(self, review_album_list: list[Tuple[AlbumObject, AlbumObject, int]]):
        print("The following albums could not be matched properly. Please deselect albums you do not want to add by "
              "entering their corresponding number (multiple possible, separated by commas.")
        review_album_list = np.asarray(review_album_list)

        def print_candidates():
            cnt = 0
            for album_candidate, target_album, score in review_album_list:
                out = str(cnt) + "\t" + str(album_candidate.artists) + ": " + album_candidate.name \
                      + "\t to \t" + str(target_album.artists) + ": " + target_album.name

                if score > self.min_score / 2:
                    out = "\033[1;33;40m" + out + "\033[1;37;40m"
                else:
                    out = "\033[1;31;40m" + out + "\033[1;37;40m"

                print(out)
                cnt += 1

        while True:
            print_candidates()
            print("If nothing should be edited, please type 'nothing'.")
            i = input()
            cleaned_i = i.replace(" ", "").split(",")

            if not i.lower() == 'nothing':

                try:
                    cleaned_i = [int(x) for x in cleaned_i]
                except Exception:
                    print("Please only type in numbers separated with commas")
                    continue

                review_album_list = np.delete(review_album_list, cleaned_i, axis=0)

            while True:
                i2 = input("Continue editing? y/n \n")
                if i2 == "n":
                    print(f"Adding closest matches for the remaining {len(review_album_list)} candidates...")
                    return review_album_list
                elif i2 == "y":
                    break

    def search_for_album(self, album_info):
        query = self.generate_album_search_string(album_info)
        response = self.sp.search(query, type="album", limit=10)
        candidates = response["albums"]["items"]
        best_candidate, score = self.select_best_candidate_album(album_info, candidates)
        return best_candidate, score

    def select_best_candidate_album(self, target_album_info, candidates) -> Tuple[AlbumObject, int]:
        scores = []
        candidate_album_infos = []
        for hit in candidates:
            album_info = self.parse_album(hit)
            candidate_album_infos.append(album_info)
            scores.append(self.similarity_score(album_info, target_album_info))

        if len(scores) > 0:
            best_hit_index = np.argmax(scores)
            best_hit = candidate_album_infos[best_hit_index]
            best_hit_score = scores[best_hit_index]
        else:
            best_hit = AlbumObject("Not found", ["None"], 0, "None")
            best_hit_score = 0

        return best_hit, best_hit_score

    @staticmethod
    def generate_album_search_string(album_info: AlbumObject):
        search_string = album_info.name

        for artist in album_info.artists:
            search_string += " " + artist

        return search_string

    @staticmethod
    def similarity_score(album_1: AlbumObject, album_2: AlbumObject):
        score = 0
        album_1_dict = album_1.__dict__
        album_2_dict = album_2.__dict__

        for attr in album_1_dict:
            if album_1_dict[attr] == album_2_dict[attr]:
                score += 1
        return score

    @staticmethod
    def similarity_score_df(a: pd.Series, b: pd.Series):
        score = 0

        common_idx = a.keys().intersection(b.keys())
        for attr in common_idx:
            if a[attr] == b[attr]:
                score += 1
        return score

    def parse_album(self, spotify_album_object):
        type_ = spotify_album_object["album_type"]
        album_name = spotify_album_object["name"]
        release_date = spotify_album_object["release_date"]
        album_spotify_id = spotify_album_object["id"]

        artists = []
        for artist in spotify_album_object["artists"]:
            artist_name = artist["name"]
            artist_id = artist["id"]
            artists.append(artist_name)
            self.register_artist(artist_name, artist_id)

        year = None
        if re.match("[0-9]{4}-[0-9]{2}-[0-9]{2}", release_date):
            year = release_date.split("-")[0]

        album = AlbumObject(album_name, artists, year, type_)
        self.register_album(album.id, album_spotify_id)

        return album

    def register_artist(self, name, spotify_artist_id):
        successful = False
        if name not in self.artists_name_to_spotify_id_map:
            self.artists_name_to_spotify_id_map[name] = spotify_artist_id
            successful = True
        return successful

    def register_album(self, internal_id, spotify_album_id):
        successful = False
        if internal_id not in self.internal_id_to_spotify_id:
            self.internal_id_to_spotify_id[internal_id] = spotify_album_id
            successful = True
        return successful
