"""
Retrieve Google search results and organize them for analysis.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

import requests
import random
import csv
import datetime
import urllib.parse
from pathlib import Path, PosixPath

from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from emerald.config.queries import QUERIES
from .emeraldconfig import EmeraldConfig


class Emerald(toga.App):
    def startup(self):

        """ Read in the configuration file"""

        config_path = Path(self.app.paths.app) / "config/config.ini"
        self.config = EmeraldConfig(config_path)
        print( self.config.sections())

        self.API_KEY = self.config.get("GoogleAPI", "API_KEY")
        self.CX = self.config.get("GoogleAPI", "CX")
        self.SERVICE_ACCOUNT_FILE = self.config.get("GoogleAPI", "SERVICE_ACCOUNT_FILE")
        self.FOLDER_ID = self.config.get("GoogleAPI", "FOLDER_ID")  
        self.SCOPES = self.config.get("GoogleAPI", "SCOPES").split(",")
        if __debug__:
            print(f"API_KEY: {self.API_KEY}")
            print(f"CX: {self.CX}")
            print(f"SERVICE_ACCOUNT_FILE: {self.SERVICE_ACCOUNT_FILE}")
            print(f"FOLDER_ID: {self.FOLDER_ID}")
            print(f"SCOPES: {self.SCOPES}")
    
        """Construct and show the Toga application.

        Usually, you would add your application to a main content box.
        We then create a main window (with a name matching the app), and
        show the main window.
        """
        main_box = toga.Box(style=Pack(direction=COLUMN))

        app_label = toga.Label(
            f"App: {self.app.paths.app}",
            style=Pack(margin=(0, 5)),
        )
        main_box.add(app_label)

        cache_label = toga.Label(
            f"Cache: {self.app.paths.cache}",
            style=Pack(margin=(0, 5)),
        )
        main_box.add(cache_label)

        config_label = toga.Label(
            f"Config: {self.app.paths.config}",
            style=Pack(margin=(0, 5)),
        )
        main_box.add(config_label)

        data_label = toga.Label(
            f"Data: {self.app.paths.data}",
            style=Pack(margin=(0, 5)),
        )
        main_box.add(data_label)

        log_label = toga.Label(
            f"Cache: {self.app.paths.logs}",
            style=Pack(margin=(0, 5)),
        )
        main_box.add(log_label)

        toga_label = toga.Label(
            f"Config: {self.app.paths.toga}",
            style=Pack(margin=(0, 5)),
        )
        main_box.add(toga_label)

        get_google_results_button = toga.Button(
            "Get Google results now!",
            on_press=self.retrieve_google_results,
            style=Pack(margin=5),
        )
#        print( f"Path for app: {self.app.paths.app}")
#        print( f"Path for cache: {self.app.paths.cache}")
#        print( f"Path for config: {self.app.paths.config}")
#        print( f"Path for data: {self.app.paths.data}")
#        print( f"Path for logs: {self.app.paths.logs}")
#        print( f"Path for toga: {self.app.paths.toga}")
        main_box.add( get_google_results_button)
        
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()
 

    async def retrieve_google_results(self, widget):
        query = random.choice(QUERIES)
        query_id = QUERIES.index(query)  
        await self.main_window.dialog(
            toga.InfoDialog( "Starting search...", f"Getting results for query, {query}")
        )

        results = self.google_search(query)
        if results:
            filename = self.save_to_csv(query_id, results)
            self.upload_to_drive(filename)
            toga.InfoDialog(
                f"Results saved and uploaded.",
                "Success...",
            )
        else:
            toga.InfoDialog(
                f"No results found for this query.",
                "Uh oh...",
            )


    def google_search(self, query):
        print(f"Performing Google search for query: {query}")
        encoded_query = urllib.parse.quote(query)  
        url = f"https://www.googleapis.com/customsearch/v1?q={encoded_query}&key={self.API_KEY}&cx={self.CX}"

        if __debug__:
            print(f"Google search URL: {url}")
            print(f"API_KEY: {self.API_KEY}")
            print(f"CX: {self.CX}")    
            print( f"Encoded query: {encoded_query}")

        response = requests.get(url)
        if response.status_code == 200:
            print("Search successful. Parsing results...")
            return response.json().get("items", [])[:10]  # return top 10 results
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")  
            return []

    def save_to_csv(self, query_id, results, user_id=1234):
        filename = f"search_results_{query_id}_{user_id}.csv"
        filepath = Path( self.app.paths.cache) / filename
        print(f"Saving results to CSV file: {filepath}")
        with open(filepath, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["query_id", "date", "time", "user_id", "result_number", "result_title", "result_url"])
            for i, result in enumerate(results):
                writer.writerow([
                    query_id,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                    datetime.datetime.now().strftime("%H:%M:%S"),
                    user_id,
                    i + 1,
                    result.get("title"),
                    result.get("link")
                ])
        print(f"CSV file saved: {filepath}")
        return filename

    def upload_to_drive(self, filename):
        print(f"Attempting to upload {filename} to Google Drive...")
        try:
            service_file_path = Path(self.app.paths.app) / "config" / self.SERVICE_ACCOUNT_FILE
            print( f"Service account file path original: {service_file_path}")
            print( f"Service account file path as posix: {service_file_path.as_posix()}")

            if not service_file_path.exists():
                print(f"Service account file not found: {service_file_path}")
                return
            credentials = service_account.Credentials.from_service_account_file(
                service_file_path, scopes=self.SCOPES
            )
            print("Service account credentials loaded successfully.")

            service = build("drive", "v3", credentials=credentials)
            print("Google Drive service built successfully.")

            posix_filepath = (Path(self.app.paths.cache) / filename).as_posix()
            file_metadata = {"name": filename, "parents": [self.FOLDER_ID]}
            media = MediaFileUpload(posix_filepath, mimetype="text/csv")
            print(f"Uploading file: {posix_filepath}")

            file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
            print(f"File uploaded to Google Drive with ID: {file.get('id')}")
            service.close()
        except HttpError as error:
            print(f"Google Drive API error: {error}")
        except Exception as e:
            print(f"Error uploading to Google Drive: {e}")


def main():
    return Emerald()
