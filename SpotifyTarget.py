from getpass import getpass
from typing import Tuple
import spotipy
import re
import tqdm
from spotipy import SpotifyOAuth

from MusicServicSource import LibraryObject
import numpy as np
import pandas as pd
import logging


class SpotifyTarget:
    min_score = 3   # Smaller than 4

    def __init__(self, client_id=None, client_secret=None):
        self.internal_id_to_spotify_id = dict()
        self.artists_name_to_spotify_id_map = dict()
        if client_id is None or client_secret is None:
            client_id = input("Client id:")
            client_secret = getpass()
        auth_manager = spotipy.SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        self.logger = logging.getLogger("DEBUG")

    def add_albums_to_library(self, spotify_ids, redirect_uri):
        auth_sp = spotipy.Spotify(auth_manager=SpotifyOAuth(redirect_uri=redirect_uri))
        auth_sp.current_user_saved_albums_add(spotify_ids)

    def get_spotify_album_ids(self, albums: list[LibraryObject]):
        album_ids_add: list[int] = []
        review_album_list: list[Tuple[LibraryObject, LibraryObject, int]] = []

        found = 0
        ambiguous = 0
        not_found = 0

        albums_tqdm = tqdm.tqdm(albums)
        for target_album in albums_tqdm:
            best_candidate, score = self.search_for_medium(target_album)
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

        print(f"Results: \t \034[1;32;40m{found} found , \034[1;33;40m{ambiguous} ambiguous, + "
                         f"\034[1;31;40m{not_found} not found \034[1;37;40m \n")

        confirmed_albums = self.eliminate_dialogue(review_album_list)
        confirmed_albums = [self.internal_id_to_spotify_id[review_album_tuple[0].id] for review_album_tuple in confirmed_albums]
        album_ids_add += confirmed_albums

        return album_ids_add

    def get_spotify_album_ids_series(self, albums: list[LibraryObject]):
        pd.Series(self.get_spotify_album_ids(albums))

    def eliminate_dialogue(self, review_album_list: list[Tuple[LibraryObject, LibraryObject, int]]):
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
            i = input()
            cleaned_i = i.replace(" ", "").split(",")

            try:
                cleaned_i = [int(x) for x in cleaned_i]
            except Exception:
                print("Please only type in numbers separated with commas")
                continue

            review_album_list = np.delete(review_album_list, cleaned_i, axis=0)

            while True:
                i2 = input("Continue editing? y/n \n")
                if i2 == "y":
                    print(f"Adding closest matches for the remaining {len(review_album_list)} candidates.")
                    return review_album_list

    def search_for_medium(self, album_info):
        query = self.generate_search_string(album_info)
        response = self.sp.search(query, type="album", limit=10)
        candidates = response["albums"]["items"]
        best_candidate, score = self.select_best_candidate(album_info, candidates)
        return best_candidate, score

    def select_best_candidate(self, target_album_info, candidates) -> Tuple[LibraryObject, int]:
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
            best_hit = LibraryObject("Not found", ["None"], 0, "None")
            best_hit_score = 0

        return best_hit, best_hit_score

    @staticmethod
    def generate_search_string(album_info: LibraryObject):
        search_string = album_info.name

        for artist in album_info.artists:
            search_string += " " + artist

        return search_string

    @staticmethod
    def similarity_score(album_1: LibraryObject, album_2: LibraryObject):
        score = 0
        album_1_dict = album_1.__dict__
        album_2_dict = album_2.__dict__

        for attr in album_1_dict:
            if album_1_dict[attr] == album_2_dict[attr]:
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

        album = LibraryObject(album_name, artists, year, type_)
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
