

#### SCRIPT TO EDIT THE GOOGLEDRIVE DATA MANUALLY


# Import needed (?) packages
# TODO: remove unneeded packages via pipreqs
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import altair as alt
from datetime import datetime, timedelta
import time
import json
import io
import plotly.express as px
import plotly.graph_objects as go
#import matplotlib.pyplot as plt
# For syncing to GoogleDrive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload # Downloader
from googleapiclient.http import MediaIoBaseUpload

### GOOGLE DRIVE SETUP
# TODO: maybe Drive is not needed anymore as now googlesheet takes over syncing
# Setting the scope for the GoogleDrive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Load and read service account info from secrets
SERVICE_ACCOUNT_KEY = st.secrets["service_account"]["key"]
key_dict = json.loads(SERVICE_ACCOUNT_KEY)
# Authenticate with the service account
credentials = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
# Build the Google Drive API client
drive_service = build('drive', 'v3', credentials=credentials)

# Folder ID of the GoogleDrive folder used for synching
FOLDER_ID = st.secrets["google_drive"]["folder_id"]

# Dictionary of users and their PIN codes
USER_DATABASE = st.secrets["user_database"]

# Function to check if the file exists in the GoogleDrive folder - 
# used in push_file_to_drive()
def get_file_id(service, file_name, folder_id=FOLDER_ID):
    """
    Retrieves the file ID from Google Drive based on file name and folder.
    :param service: Authenticated Google Drive service instance
    :param file_name: The name of the file to retrieve
    :param folder_id: The folder ID to check for the file
    :return: File ID if found, None otherwise
    """
    query = f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
    
    try:
        results = service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        else:
            # File not found, create a new file
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            # Assuming the file should be empty initially, use an empty media body
            media = MediaIoBaseUpload(io.BytesIO(), mimetype='text/csv')  # Empty file
            new_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            st.success(f"File '{file_name}' not found. Created a new file in Google Drive.")
            return new_file['id']
    except Exception as e:
        st.error(f"Error retrieving file ID: {e}")
        return None

# Function to push a file to GoogleDrive
def push_file_to_drive(data, file_name, service=drive_service, folder_id=FOLDER_ID):
    """
    Pushes a specific data variable (e.g., a DataFrame) to Google Drive as a CSV file.
    :param data: The data (e.g., a pandas DataFrame) to push.
    :param file_name: The name of the file to push (e.g., 'pushup_log.csv').
    :param service: Authenticated Google Drive service instance.
    :param folder_id: The Google Drive folder ID where the file should be stored.
    """
    try:
        # Convert the DataFrame (or data) to CSV in-memory
        csv_data = data.to_csv(index=False)

        # Create an in-memory file-like object
        file_like = io.BytesIO(csv_data.encode('utf-8'))
        
        # Check if the file already exists in Google Drive
        file_id = get_file_id(service, file_name)
        if file_id:
            # Update the existing file with new data
            media = MediaIoBaseUpload(file_like, mimetype='text/csv')
            updated_file = service.files().update(fileId=file_id, media_body=media).execute()
            #st.success(f"Updated existing {file_name} file (File ID: {updated_file.get('id')})")
        else:
            # Create a new file if it doesn't exist
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            media = MediaIoBaseUpload(file_like, mimetype='text/csv')
            new_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            #st.success(f"Created new {file_name} file (in GoogleDrive)")

    except Exception as e:
        st.error(f"Error syncing {file_name} to Google Drive: {e}")

# Function to fetch file from GoogleDrive
def fetch_file_from_drive(file_name, service=drive_service, folder_id=FOLDER_ID):
    """
    Fetches a CSV file from Google Drive and loads it into a pandas DataFrame.
    :param file_name: The name of the file to fetch (e.g., 'pushup_log.csv')
    :param service: Authenticated Google Drive service instance
    :param folder_id: The Google Drive folder ID where the file is stored
    :return: pandas DataFrame containing the file's data
    """
    try:
        # Fetch the file ID from Google Drive using the file name and folder ID
        file_id = get_file_id(service, file_name, folder_id)

        if file_id:
            # Download the file content
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()  # Use a BytesIO object to store the file in memory
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Once downloaded, move the cursor to the start of the file content
            fh.seek(0)
            
            # Read the CSV content directly into a pandas DataFrame
            data = pd.read_csv(fh)

            # Return the DataFrame
            return data
        else:
            st.error(f"File {file_name} not found in Google Drive.")
            return None

    except Exception as e:
        st.error(f"Error fetching {file_name} from Google Drive: {e}")
        return None




data = fetch_file_from_drive("pushup_log.csv")
data = data.iloc[0:0]
push_file_to_drive(data, "pushup_log.csv")
