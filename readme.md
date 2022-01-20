# Migrate Youtube Music Library to Spotify



## Step 1: Obtain YoutubeMusic Cookie

Log in to your Youtube Music account in your browser (if not already done). Now you need to obtain the cookie sent with authorized.

- Create a file named headers_auth.json. 
- Copy the json object below to that file and insert a raw text version of the request cookie to the auth_json.

<code>

{
  "User-Agent": "Browser",
  "Accept": "*/*",
  "Accept-Language": "en-US,en;q=0.5",
  "Content-Type": "application/json",
  "X-Goog-AuthUser": "0",
  "x-origin": "https://music.youtube.com",
  "Cookie": "Insert your cookie here"
}

</code>



## Step 2: Create Spotify Developer App and extract client id and secret

- Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/login) and log in
- Create an app with an arbitrary name.
- Go to "Edit Settings" and enter the following URL as Redirect URL "https://mysite.com/callback".
- Select "Show client secret" and save both, Client ID and Client Secret somewhere. It will be used as arguments in the script.


## Step 3: Migrate

Now that you obtained your login credentials for both sites, proceed and prepare your migration script.


To migrate playlists
<code>
client_id="SOME_CLIENT_ID"
client_secret="SOME_CLIENT_SECRET"
redirect_uri = "https://mysite.com/callback"

sp = SpotifyTarget(client_id, client_id)
yt = YoutubeMusicSource()


# Migrating albums 
album_lib = yt.get_albums_library()
sp_album_ids = sp.get_spotify_album_ids(album_lib)

sp.add_albums_to_library(sp_album_ids, client_id, client_secret, redirect_uri)


# Migrating Playlists
pl_lib = yt.get_playlists_library()
sp_ids = sp.get_spotify_song_ids(pl_lib)
pl_lib.insert(0, "spotify_id", sp_ids)

sp.add_playlists_to_library(pl_lib, client_id, client_secret, redirect_uri)
</code>