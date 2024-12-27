import streamlit as st
import pandas as pd
from datetime import datetime
import os
import altair as alt
from datetime import datetime, timedelta
import time
import json
# For syncing to GoogleDrive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = '.streamlit/pushup-sync-37f17b097d7a.json'  # Path to your downloaded JSON key

# Load service account key from secrets
SERVICE_ACCOUNT_KEY = st.secrets["service_account"]["key"]
key_dict = json.loads(SERVICE_ACCOUNT_KEY)

# Authenticate with the service account
from google.oauth2 import service_account
credentials = service_account.Credentials.from_service_account_info(key_dict)
# Build the Google Drive API client
drive_service = build('drive', 'v3', credentials=credentials)


# git add .
# git commit -m "Added Table with last 5 entries"
# git push origin main


# Ensure the data directory exists
os.makedirs("data", exist_ok=True)

# File to store push-up logs
LOG_FILE = "data/pushup_log.csv" # local file that will be synced to GoogleDrive via ServiceAccount
if os.path.exists(LOG_FILE):
    log_data = pd.read_csv(LOG_FILE)
else:
    st.write("No data file.")
log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])

# Dictionary of users and their PIN codes
USER_DATABASE = st.secrets["user_database"]

# Debugging: Show where the file is saved
#st.write(f"Saving to: {os.path.abspath(LOG_FILE)}")

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
                    x="Timestamp:T",
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

# last five entries into database
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


# Title for the app
st.title("Push-Up Tracker.")

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

# Main content that is displayed when login was successfull
if username and pincode:
    if USER_DATABASE[username] == pincode:
        st.success(f"Welcome, {username}!")
        
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
                try:
                    if os.path.exists(LOG_FILE):
                        # Read the existing log file
                        existing_log = pd.read_csv(LOG_FILE)
                        # Append the new entry
                        updated_log = pd.concat([existing_log, new_entry], ignore_index=True)
                    else:
                        # If the file doesn't exist, create it
                        updated_log = new_entry

                    # Save the updated log to the file
                    updated_log.to_csv(LOG_FILE, index=False)

                    # Upload the updated log file to Google Drive
                    file_metadata = {'name': 'pushup_log.csv'}
                    media = MediaFileUpload(LOG_FILE, mimetype='text/csv')
                    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                    # TODO: remove this message again, success-message can be found below
                    st.success(f"Logged {pushups} push-ups at {timestamp}! (File ID: {file.get('id')})")

                    # Placeholder success message
                    success_message = st.empty()
                    formatted_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    success_message.success(f"Logged {pushups} push-ups at {formatted_timestamp}")
                    
                    time.sleep(2)
                    # Clear the message
                    success_message.empty()

                except Exception as e:
                    st.error(f"Error writing to file: {e}")

        st.subheader("")
        st.subheader("Filter")
        user_selection = st.multiselect(
            "Select Users",
            log_data['User'].unique(),
            default=list(log_data['User'].unique())  # Set default to all unique users
            )
        
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
        
        st.subheader("")
        st.header("Last 5 entries")
        display_last_five_entries(log_data)
        # Display the accumulated push-ups graph
        st.subheader("")
        st.header("Visualization")
        st.subheader("Accumulated Push-Ups")
        display_accumulated_pushups(log_data, user_selection)

        # Display the original push-ups over time graph
        st.subheader("Push-Ups Over Time")

        if os.path.exists(LOG_FILE):
            try:
                # Read the log file
                log_data = pd.read_csv(LOG_FILE)

                # Convert the Timestamp column to a datetime type
                log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])

                # Filter data based on selected users for the time-series graph
                if user_selection:
                    filtered_data = log_data[log_data['User'].isin(user_selection)]

                    # Create an interactive selection for zoom and pan
                    brush = alt.selection_interval(encodings=['x'])

                    # Plot the original time-series data for the selected users with interactive zoom
                    line_chart = alt.Chart(filtered_data).mark_line(point=True).encode(
                        x=alt.X("Timestamp:T", title="Time"),
                        y=alt.Y("Pushups:Q", title="Push-Ups"),
                        color="User:N",  # Different colors for each user
                        tooltip=["Timestamp:T", "Pushups:Q", "User:N"]
                    ).properties(
                        width=800,
                        height=400,
                        title="Push-Ups Over Time (Selected Users)"
                    ).add_selection(
                        brush
                    ).interactive()  # Enables zoom and pan

                    # Display the chart
                    st.altair_chart(line_chart, use_container_width=True)
                else:
                    st.write("No users selected. Please select at least one user to display the graph.")

            except Exception as e:
                st.error(f"Error reading or plotting data: {e}")
        else:
            st.write("No data to display yet.")

        st.subheader("Stuff that will change (soon)")
        '''
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
        - establish suggestion tab that let's you send your own suggestions on what to change
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

