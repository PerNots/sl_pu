# Import needed (?) packages
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import altair as alt
from datetime import datetime, timedelta
import time
import json
import io
# For syncing to GoogleDrive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload # Uploader
from googleapiclient.http import MediaIoBaseDownload # Downloader

### GOOGLE DRIVE SETUP
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

### OVERVIEW LOG FILES
log_files = {
    "pushup_log.csv": "data/pushup_log.csv",
    "pushup_log_2022.csv": "data/pushup_log_2022.csv",
    "suggestions.csv": "data/suggestions.csv"
}

# Dictionary of users and their PIN codes
USER_DATABASE = st.secrets["user_database"]

# TODO: remove this?!?, it is now stored in the log_files dictionary
LOG_FILE = "data/pushup_log.csv" # local file that will be synced to GoogleDrive via ServiceAccount

# Function to check if the file exists in the folder - used in push_file_to_drive()
# TODO: Not yet used
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
            st.error(f"File '{file_name}' not found in the specified GoogleDrive folder.")
            return None
    except Exception as e:
        st.error(f"Error retrieving file ID: {e}")
        return None

# Function to sync a file to Google Drive
# TODO: not yet employed but will allow easy synching of log-files after they were changed
# TODO: local_file_path and file_name are tmi as the dict above links them together!
def push_file_to_drive(file_name, service=drive_service, folder_id=FOLDER_ID):
    """
    Pushes a specific local file to Google Drive. If the file exists, it updates it; otherwise, it creates a new file.
    :param file_name: The name of the file to push (e.g., 'pushup_log.csv')
    :param service: Authenticated Google Drive service instance
    :param folder_id: The Google Drive folder ID where the file should be stored
    """
    # Check if the file exists in the log_files dictionary
    if file_name not in log_files:
        st.error(f"File {file_name} not found in the log_files dictionary.")
        return
    # Get the local file path from the dictionary
    local_file_path = log_files[file_name]
    
    try:
        # Check if the file already exists in Google Drive
        file_id = get_file_id(service, file_name)
        if file_id:
            # Update the existing file
            media = MediaFileUpload(local_file_path, mimetype='text/csv')
            updated_file = service.files().update(fileId=file_id, media_body=media).execute()
            #st.success(f"Updated existing {file_name} file (File ID: {updated_file.get('id')})")
        else:
            # Create a new file if it doesn't exist
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(local_file_path, mimetype='text/csv')
            new_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            #st.success(f"Created new {file_name} file (in GoogleDrive)")

    except Exception as e:
        st.error(f"Error syncing {file_name} to Google Drive: {e}")

def fetch_file_from_drive(file_name, service=drive_service, folder_id=FOLDER_ID):
    """
    Fetches a file from Google Drive and saves it locally.
    :param file_name: The name of the file to fetch (e.g., 'pushup_log.csv')
    :param log_files: Dictionary with file names as keys and local paths as values
    :param service: Authenticated Google Drive service instance
    :param folder_id: The Google Drive folder ID where the file is stored
    """
    # Check if the file exists in the log_files dictionary
    if file_name not in log_files:
        st.error(f"File {file_name} not found in the log_files dictionary.")
        return

    # Get the local file path from the dictionary
    local_file_path = log_files[file_name]

    try:
        # Fetch the file ID from Google Drive using the file name and folder ID
        file_id = get_file_id(service, file_name, folder_id)

        if file_id:
            # Download the file content
            request = service.files().get_media(fileId=file_id)
            fh = io.FileIO(local_file_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                #st.write(f"Download {int(status.progress() * 100)}%.")
            
            #st.success(f"Downloaded {file_name} to {local_file_path}")
        else:
            st.error(f"File {file_name} not found in Google Drive.")

    except Exception as e:
        st.error(f"Error fetching {file_name} from Google Drive: {e}")

# git add .
# git commit -m "Added Table with last 5 entries"
# git push origin main

# File to store push-up logs
# TODO: This probably needs to be changed so that the files from the google drive are read in
if os.path.exists(LOG_FILE):
    log_data = pd.read_csv(LOG_FILE)
else:
    st.write("No data file.")
log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])

# graph for accum pushups
def display_accumulated_pushups(log_data, user_selection):
        try:
            # Sort the data by Timestamp to ensure proper accumulation
            log_data = log_data.sort_values(by="Timestamp")
            # Create a new column with the accumulated sum of push-ups per user
            log_data['Accumulated Pushups'] = log_data.groupby('User')['Pushups'].cumsum()
            # User selection dropdown for multiple users
            #user_selection = st.multiselect(
            #    "Select Users",
            #    log_data['User'].unique(),
            #    default=list(log_data['User'].unique())  # Set default to all unique users
            #    )
            # Filter data based on selected users
            if user_selection:
                filtered_data = log_data[log_data['User'].isin(user_selection)]

                # Plot the accumulated data for the selected users
                accumulated_chart = alt.Chart(filtered_data).mark_line(point=True).encode(
                    x=alt.X("Timestamp:T", title="Time"),
                    y="Accumulated Pushups:Q",
                    color="User:N",  # Different colors for each user
                    tooltip=["Timestamp:T", "Accumulated Pushups:Q", "User:N"],
                    size=alt.value(2)
                ).properties(
                    width=800,
                    height=400,
                    #title="Accumulated Push-Ups Over Time (Selected Users)"
                )

                st.altair_chart(accumulated_chart, use_container_width=True)
            else:
                st.write("No users selected. Please select at least one user to display the graph.")

        except Exception as e:
            st.error(f"Error reading or plotting accumulated data: {e}")

# graph for pushups over time
def display_time_series_pushups_bu(log_data, user_selection):
    """
    Displays a time-series graph of pushups for the selected users.

    :param log_data: DataFrame containing the pushup logs with columns 'Timestamp', 'Pushups', and 'User'.
    :param user_selection: List of selected users to filter the data for plotting.
    """
    try:
        # Ensure the Timestamp column is in datetime format
        log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])
        
        # Filter data based on selected users
        if user_selection:
            filtered_data = log_data[log_data['User'].isin(user_selection)]
            
            # Create an interactive selection for zooming only along the x-axis
            x_brush = alt.selection_interval(encodings=['x'], bind='scales')
            y_brush = alt.selection_interval(encodings=['y'], bind='scales')
            
            # Plot the original time-series data for the selected users
            line_chart = alt.Chart(filtered_data).mark_line(point=True).encode(
                x=alt.X("Timestamp:T", title="Time"),
                y=alt.Y("Pushups:Q", title="Pushups"),
                color="User:N",  # Different colors for each user
                tooltip=["Timestamp:T", "Pushups:Q", "User:N"]
            ).properties(
                width=800,
                height=400,
            ).add_selection(
                x_brush,  # Enable zoom on x-axis
                y_brush   # Enable zoom on y-axis
            )
            
            # Display the chart
            st.altair_chart(line_chart, use_container_width=True)
        else:
            st.write("No users selected. Please select at least one user to display the graph.")

    except Exception as e:
        st.error(f"Error reading or plotting data: {e}")

# hopefully better zooming
import plotly.express as px

def display_time_series_pushups(log_data, user_selection):
    """
    Displays a time-series graph of pushups for the selected users using Plotly.

    :param log_data: DataFrame containing the pushup logs with columns 'Timestamp', 'Pushups', and 'User'.
    :param user_selection: List of selected users to filter the data for plotting.
    """
    try:
        # Ensure the Timestamp column is in datetime format
        log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])
        
        # Filter data based on selected users
        if user_selection:
            filtered_data = log_data[log_data['User'].isin(user_selection)]
            
            # Create the Plotly figure
            fig = px.line(
                filtered_data,
                x="Timestamp",
                y="Pushups",
                color="User",
                labels={"Timestamp": "Time", "Pushups": "Pushups", "User": "User"},
                title="Pushups Over Time"
            )
            
            # Customize the layout for better interaction
            fig.update_layout(
                width=800,
                height=400,
                xaxis_title="Time",
                yaxis_title="Pushups",
                margin=dict(l=40, r=40, t=40, b=40),
                legend_title="Users",
            )
            
            # Enable interactive tools like zoom and pan
            fig.update_layout(
                dragmode="zoom",  # Allows zooming by dragging
                hovermode="x unified"  # Unified hover mode for better tooltips
            )
            
            # Display the chart in Streamlit
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No users selected. Please select at least one user to display the graph.")

    except Exception as e:
        st.error(f"Error reading or plotting data: {e}")

     

# last five entries into log
def display_last_five_entries(log_data):
    try:
        # Convert the Timestamp column to datetime format if it's not already
        log_data['Timestamp'] = pd.to_datetime(log_data['Timestamp'])

        # Extract the Date and Time from the Timestamp
        log_data['Date'] = log_data['Timestamp'].dt.date
        log_data['Time'] = log_data['Timestamp'].dt.time

        # Select the relevant columns and get the last 5 entries
        last_five_entries = log_data[['Date', 'Time', 'User', 'Pushups']].tail(5)

        # Convert to list of dictionaries to remove the index
        data_no_index = last_five_entries.to_dict(orient="records")

        # Display the last five entries without the index
        #st.subheader("Last Five Entries")
        st.table(data_no_index)

    except Exception as e:
        st.error(f"Error displaying the last five entries: {e}")

# recent entries into log (more than 5, scrollable element)
def display_recent_entries(log_data, num_entries=20):
    try:
        # Convert the Timestamp column to datetime format if it's not already
        log_data['Timestamp'] = pd.to_datetime(log_data['Timestamp'])
        # Extract the Date and Time from the Timestamp
        log_data['Date'] = log_data['Timestamp'].dt.date
        log_data['Time'] = log_data['Timestamp'].dt.time
        # Select the relevant columns and get the most recent entries
        recent_entries = log_data[['Date', 'Time', 'User', 'Pushups']].tail(num_entries).iloc[::-1]
        # Display the recent entries in a scrollable element
        st.dataframe(
            recent_entries,
            height=250  # Set the height of the scrollable area
        )
    except Exception as e:
        st.error(f"Error displaying the recent entries: {e}")

### START OF THE APP'S SCRIPT
# Title for the app
st.title("Push-Up Tracker.")

## FOR TESTING or syncing data with Codespace Workspace
push_file_to_drive("pushup_log.csv")

# NewYear's gimmick
year = st.select_slider("Happy New Year!", options=["2024", "2025"])
if year == "2025": # Check if the slider is set to "2025"
    st.markdown(
        """
        <style>
            .custom-text {
                font-size: 32px;  /* Adjust the size as needed */
                color: #FF4500;   /* Optional: Set the color */
                text-align: center; /* Center the text */
            }
        </style>
        <div class="custom-text">🎆🎇🎆🎇</div>
        """,
        unsafe_allow_html=True
    )
st.title("")

# Login-part
# Side-by-side layout for username and PIN code
col1, col2, col3 = st.columns([2, 2, 1])  # Adjust column ratios as needed
# User selection dropdown
with col1:
    username = st.selectbox("Select User", options=list(USER_DATABASE.keys()),label_visibility="collapsed",placeholder="Username")
# PIN code input field
with col2:
    pincode = st.text_input("Enter PIN Code", type="password", label_visibility="collapsed",placeholder="PIN")
with col3:
    login = st.button("Login",use_container_width=True)

# Login Validation
if login:
    if username in USER_DATABASE and pincode == USER_DATABASE[username]:
        st.success(f"Welcome, {username}!")
    else:
        st.error("Invalid username or PIN code. Please try again.")

### MAIN CONTENT that is displayed when login was successfull
if username and pincode:
    if USER_DATABASE[username] == pincode:
        st.success(f"Welcome, {username}!")
        
        ## ADD PUSH-UPS
        # Create a form to group the input and button together
        with st.form("log_pushups_form"):
            # Create two columns to place the input field and button side by side
            col1, col2 = st.columns([3, 1],vertical_alignment="bottom")  # Adjust the width ratio as needed
            with col1:
                # Input field for the number of push-ups
                pushups = st.number_input("Enter the number of push-ups you just did:", min_value=1, step=1)
            with col2:
                # Submit button inside the form and aligned with the bottom of the input
                submit_button = st.form_submit_button("Log Push-Ups", use_container_width=True)

            # If the button is pressed or Enter is hit, log the data
            if submit_button:
                # Get the current timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Create a DataFrame for the current entry
                new_entry = pd.DataFrame({"Timestamp": [timestamp], "Pushups": [pushups], "User": [username]})

                # Try to append to the existing log file or create a new one
                # TODO: code should fetch, append, and push here to minimize conflicts when multiple
                # users are logging at the same time (see how this works in practice)
                try:
                    # fetch file from GoogleDrive to Local
                    fetch_file_from_drive("pushup_log.csv")
                    # append local file with current push-ups
                    if os.path.exists(LOG_FILE):
                        # Read the existing log file
                        existing_log = pd.read_csv(LOG_FILE)
                        # Append the new entry
                        updated_log = pd.concat([existing_log, new_entry], ignore_index=True)
                    else:
                        # If the file doesn't exist, create it
                        updated_log = new_entry
                        st.error("Local log-file not existing - sync issue likely")
                    # Save the updated log to the file
                    updated_log.to_csv(LOG_FILE, index=False)

                    # push the updated local log file to Google Drive
                    push_file_to_drive("pushup_log.csv")
                    
                    #file_metadata = {'name': 'pushup_log.csv'}
                    #media = MediaFileUpload(LOG_FILE, mimetype='text/csv')
                    #file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                    # TODO: remove this message again, success-message can be found below
                    # st.success(f"Logged {pushups} push-ups at {timestamp}! (File ID: {file.get('id')})")

                    # Placeholder success message
                    success_message = st.empty()
                    formatted_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    success_message.success(f"Logged {pushups} push-ups at {formatted_timestamp}")
                    
                    time.sleep(2)
                    # Clear the message
                    success_message.empty()

                except Exception as e:
                    st.error(f"Error writing to file: {e}")

        ### SHOW THE LAST 5 ENTRIES
        st.subheader("")
        st.header("Recent entries")
        display_recent_entries(log_data)
        #display_last_five_entries(log_data)
        
        ### VISUALIZATION
        st.subheader("")
        st.header("Visualization")
        ### FILTER THE DATA FOR VISUALISATION
        ## USER FILTER
        st.subheader("Filter")
        user_selection = st.multiselect(
            "Select Users",
            log_data['User'].unique(),
            default=list(log_data['User'].unique())  # Set default to all unique users
            )
        
        ## DATE FILTER
        col1, col2 = st.columns([1, 1])
        with col2:
            # Date range selection for end date
            max_date = datetime.strptime("2025-12-31", "%Y-%m-%d").date()
            end_date = st.date_input(
                "End Date",
                value=max_date if max_date else datetime.now().date(),  # Default to the max date in the data or today
                min_value=log_data['Timestamp'].min().date(),
                max_value=max_date
            )

        with col1:
            # Set the start date to 90 days before the end date or the minimum date in the data
            # This code will be executed after the end_date has been set
            if 'end_date' in locals():  # Check if end_date has been set
                start_date = st.date_input(
                    "Start Date",
                    value=(datetime.combine(end_date, datetime.min.time()) - timedelta(days=90)).date(),
                    min_value=log_data['Timestamp'].min().date(),
                    max_value=end_date
                )
            else:
                # Handle the case where end_date is not yet defined
                start_date = st.date_input(
                    "Start Date",
                    value=log_data['Timestamp'].min().date(),
                    min_value=log_data['Timestamp'].min().date(),
                    max_value=log_data['Timestamp'].max().date()
                )

        ## DISPLAY the accumulated push-ups graph
        # TODO: fix zooming
        # TODO: add fetch to the beginning of visualization, this way the newly added pushups should be displayed
        st.subheader("Accumulated Push-Ups")
        display_accumulated_pushups(log_data, user_selection)

        ## DISPLAY the original push-ups over time graph
        # TODO: fix zoom
        st.subheader("Push-Ups Over Time")
        display_time_series_pushups(log_data, user_selection)


        st.subheader("Legacy")        
        # TODO: add legacy data here
        with st.expander("2022"):
            # fetch 2022 data from GoogleDrive
            # TODO: not really needed as nothing changes here. could just be stored locally as well
            fetch_file_from_drive("pushup_log_2022.csv")
            # load data locally into variable
            if os.path.exists(LOG_FILE):
                log_data_2022 = pd.read_csv("data/pushup_log_2022.csv")
            else:
                st.write("No data file.")
            log_data_2022["Timestamp"] = pd.to_datetime(log_data_2022["Timestamp"])
            # user selection for 2022
            user_selection_2022 = st.multiselect(
                "Select Users",
                log_data_2022['User'].unique(),
                default=list(log_data_2022['User'].unique()),  # Set default to all unique users
                key="user_selection_2022"
                )
            # display accumulated pushups 2022
            display_accumulated_pushups(log_data_2022, user_selection=user_selection_2022)


        st.subheader("Stuff that will change (soon)")
        '''
        - make logging quicker (communication with cloud takes some time right now)
        - make date-filter work
        - fix zooming for figures
        - add optional comments to push-up addition
        - allow deletion of last few own activities by user
        - handle different timezones via user-database, will timezones register locally or globally?
        - add visualizations that were established in googlesheet in the last years
        - allow users to set personal goals for the year
        - move last years data to a different part of the site ("legacy"), will also adjust the user filter to not be too populated
        - might add different disciplines (squats or pull-ups or w/e)
        - differentiate types of push-ups
        - tackle possible issues when multiple users are adding push-ups at the same time
        '''

        # User Suggestions
        # Path to the suggestions file
        SUGGESTIONS_FILE = "data/suggestions.csv"

        # Ensure the data folder exists
        os.makedirs("data", exist_ok=True)

        # Form for user suggestions
        with st.form("suggestion_form"):
            st.write("Have another idea for improvement?")

            # Text area for the suggestion (username is automatically logged)
            suggestion = st.text_area("Your Suggestion", "")
            submit_suggestion = st.form_submit_button("Submit Suggestion")

            if submit_suggestion:
                if suggestion.strip():  # Ensure the suggestion is not empty
                    # Create a DataFrame for the new suggestion
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_suggestion = pd.DataFrame({
                        "Timestamp": [timestamp],
                        "Username": [username],  # Automatically log the username
                        "Suggestion": [suggestion.strip()]
                    })

                    # Try appending or creating the suggestions file
                    try:
                        if os.path.exists(SUGGESTIONS_FILE):
                            # Append to existing suggestions
                            existing_suggestions = pd.read_csv(SUGGESTIONS_FILE)
                            updated_suggestions = pd.concat([existing_suggestions, new_suggestion], ignore_index=True)
                        else:
                            # Create a new suggestions file
                            updated_suggestions = new_suggestion

                        # Save updated suggestions
                        updated_suggestions.to_csv(SUGGESTIONS_FILE, index=False)

                        st.success("Thank you for your suggestion!")
                    except Exception as e:
                        st.error(f"Error saving your suggestion: {e}")
                else:
                    st.warning("Please write a suggestion before submitting.")


    else:
        st.error("Invalid PIN code. Please try again.")

st.subheader("")
"""
💟 Happy pushing. Stefan.
"""



# TODO:
# - make colors static so that they don't change when users are selected in different orders
# - add all the graphs from the googlesheet
# - add specific timestamps to choose from e.g. "2022, 2023, last three months, current month, everything, custom range"
# - add leaderboard displaying the top three of differnt things
#     - top three days by "most PU/day"
#     - top most pushups in a day
# - time-format issues
# - make it possible to delete entries if they were made by mistake (only by the user who entered them)

