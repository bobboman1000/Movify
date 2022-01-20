from getpass import getpass
from typing import Tuple, List
import spotipy
import re
from tqdm import tqdm
from spotipy import SpotifyOAuth

import numpy as np
import pandas as pd
import logging

from YoutubeMusicSource import YoutubeMusicSource


class SpotifyTarget:
    min_score = 2 # Smaller than 4
    max_album_post = 50

    song_response_mapper = {"name": "title", "artists": "artists", "id": "id"}
    album_response_mapper = {"name": "title", "artists": "artists", "id": "id", "album_type": "_type",
                             "release_date": "year"}

    def __init__(self, client_id=None, client_secret=None):
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
        playlists = playlists.reset_index(drop=True)
        playlists.sort_values(by=["playlist_title"])


        curr_playlist = None
        start_idx = 0
        for curr_idx, row in playlists.iterrows():
            if curr_playlist is None:
                curr_playlist = row["playlist_title"]
                continue
            if row["playlist_title"] != curr_playlist or curr_idx == playlists.shape[0] - 1:
                playlist_songs = playlists.iloc[start_idx:curr_idx, :]
                song_ids = playlist_songs["spotify_id"]
                response = auth_sp.user_playlist_create(auth_sp.current_user()["id"], curr_playlist, public=False)
                new_playlist_id = response["id"]
                auth_sp.playlist_add_items(new_playlist_id, song_ids)
                curr_playlist = row["playlist_title"]
                start_idx = curr_idx

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
        search_string = self.generate_search_string(song)
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

    def add_albums_to_library(self, spotify_ids: List[str], client_id, client_secret, redirect_uri):
        auth_sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id, client_secret, redirect_uri,
                                                            scope="user-library-modify"))
        batches = int(len(spotify_ids) / 50)
        for i in range(batches + 1):
            lower_idx = i * 50

            full_upper_idx = (i + 1) * 50
            upper_idx = full_upper_idx if full_upper_idx <= len(spotify_ids) - 1 else len(spotify_ids) - 1
            auth_sp.current_user_saved_albums_add(spotify_ids[lower_idx:upper_idx])

    def get_spotify_album_ids(self, albums: pd.DataFrame) -> list[str]:
        review_album_indices: list[int] = []
        best_matches: list[pd.Series] = []

        found, ambiguous, not_found = 0, 0, 0

        print("Looking up albums on spotify...")
        for idx, target_album in tqdm(albums.iterrows(), total=albums.shape[0]):
            best_candidate, score = self.search_for_album(target_album)
            if score >= self.min_score:
                found += 1
            elif score > 0:
                review_album_indices.append(idx)
                ambiguous += 1
            else:
                not_found += 1
            best_matches.append(best_candidate)

        best_matches_ids = [song["id"] for song in best_matches]
        albums.insert(0, "id", best_matches_ids)

        print(f"Results: \t \034[1;32;40m {found} \034[1;37;40m found, \034[1;33;40m {ambiguous} "
              f"\034[1;37;40m ambiguous, \034[1;31;40m {not_found} \034[1;37;40m not found \n")

        drop_albums_idx = self.eliminate_dialogue(albums, review_album_indices, best_matches)
        confirmed_albums = albums.drop(drop_albums_idx, axis=0)
        confirmed_albums = confirmed_albums.dropna()

        return confirmed_albums["id"]

    def eliminate_dialogue(self, albums: pd.DataFrame, review_album_indices: list[int], best_matches: list[pd.Series]):
        print("The following albums could not be matched properly. Please deselect albums you do not want to add by "
              "entering their corresponding number (multiple possible, separated by commas.")
        review_album_list = np.asarray(review_album_indices)
        drop: set = set()

        def print_candidates(indices):
            for idx, row in albums.iloc[indices, :].iterrows():

                if idx not in drop:
                    out = str(idx) + "\t" + str(row["artists"]) + ": " + row["title"] \
                          + "\t to \t" + str(best_matches[idx]["artists"]) + ": " + best_matches[idx]["title"]

                    out = "\033[1;33;40m" + out + "\033[1;37;40m"
                    print(out)

        while True:
            print_candidates(review_album_list)
            print("If nothing should be edited, please type 'nothing'.")
            i = input()
            cleaned_i = i.replace(" ", "").split(",")

            if not i.lower() == 'nothing':

                try:
                    cleaned_i = [int(x) for x in cleaned_i]
                except Exception:
                    print("Please only type in numbers separated with commas")
                    continue

            for e in cleaned_i:
                drop.add(e)

            while True:
                i2 = input("Continue editing? y/n \n")
                if i2 == "n":
                    print(f"Adding closest matches for the remaining {len(review_album_list)} candidates...")
                    return review_album_list
                elif i2 == "y":
                    break

    def search_for_album(self, album_info) -> Tuple[pd.Series, int]:
        query = self.generate_search_string(album_info)
        response = self.sp.search(query, type="album", limit=10)
        candidates = response["albums"]["items"]
        candidates = pd.DataFrame(candidates)

        if candidates.empty:
            empty = album_info
            album_info["id"] = pd.NA
            return empty, -1

        attr_filtered_candidates = candidates[self.album_response_mapper]
        attr_filtered_candidates = attr_filtered_candidates.rename(columns=self.album_response_mapper)
        attr_filtered_candidates["year"] = self.parse_year(attr_filtered_candidates["year"])
        attr_filtered_candidates["artists"] = YoutubeMusicSource.parse_artists(attr_filtered_candidates["artists"])
        best_candidate, score = self.select_best_candidate_album(album_info, attr_filtered_candidates)
        return best_candidate, score

    def select_best_candidate_album(self, target_album: pd.Series, candidates: pd.DataFrame) -> Tuple[pd.Series, int]:
        scores = []
        candidate_album_infos = []
        for idx, hit in candidates.iterrows():
            candidate_album_infos.append(hit)
            scores.append(self.similarity_score_df(target_album, hit))

        if len(scores) > 0:
            best_hit_index = np.argmax(scores)
            best_hit = candidate_album_infos[best_hit_index]
            best_hit_score = scores[best_hit_index]
        else:
            best_hit = pd.Series(index=target_album.index)
            best_hit_score = 0

        return best_hit, best_hit_score

    @staticmethod
    def generate_search_string(obj: pd.Series):
        search_string = obj["title"] + " " + str(obj["artists"]).replace("[", "").replace("]", "").replace("\'", "")
        return search_string

    @staticmethod
    def similarity_score(album_1: pd.Series, album_2: pd.Series):
        score = 0

        for attr in album_1.index.values:
            if album_1[attr] == album_2[attr]:
                score += 1
        return score

    @staticmethod
    def similarity_score_df(a: pd.Series, b: pd.Series):
        score = 0

        common_idx = a.keys().intersection(b.keys())
        for attr in common_idx:
            if str(a[attr]).lower() == str(b[attr]).lower():
                score += 1

        return score

    @staticmethod
    def parse_year(dates):
        return [str(date)[:4] for date in list(dates)]

