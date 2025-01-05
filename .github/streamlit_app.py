# Import needed (?) packages
# TODO: remove unneeded packages via pipreqs
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import time
import json
import io
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import pytz
from datetime import datetime
import matplotlib.pyplot as plt
#import matplotlib.pyplot as plt
# For syncing to GoogleDrive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload # Downloader
from googleapiclient.http import MediaIoBaseUpload

### SET TIME ZONE TO GERMANY - BERLIN
# Get the German timezone (CET/CEST)
# Get the current time in UTC and convert it to German time
utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)  # Get UTC time
german_time = utc_time.astimezone(pytz.timezone('Europe/Berlin'))


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

# git add .
# git commit -m "Added Table with last 5 entries"
# git push origin main

# graph for accum pushups
def display_accumulated_pushups(log_data, user_selection):
    try:
        # Sort the data by Timestamp to ensure proper accumulation
        log_data = log_data.sort_values(by="Timestamp")
        
        # Create a new column with the accumulated sum of push-ups per user
        log_data['Accumulated Pushups'] = log_data.groupby('User')['Pushups'].cumsum()

        # Filter data based on selected users
        if user_selection:
            filtered_data = log_data[log_data['User'].isin(user_selection)]

            # Create a Plotly line chart for the accumulated pushups data
            accumulated_chart = px.line(
                filtered_data,
                x="Timestamp",  # X-axis as Timestamp
                y="Accumulated Pushups",  # Y-axis as accumulated pushups
                color="User",  # Color by user
                #title="Accumulated Push-Ups Over Time (Selected Users)",
                labels={"Timestamp": "Time", "Accumulated Pushups": "Accumulated Pushups"}
            )

            # Show the chart in Streamlit
            st.plotly_chart(accumulated_chart, use_container_width=True)
        else:
            st.write("No users selected. Please select at least one user to display the graph.")

    except Exception as e:
        st.error(f"Error reading or plotting accumulated data: {e}")

# graph for pushups over time
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
                #title="Pushups Over Time"
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

# dominance graph
def display_pushups_dominance_with_selection(log_data, user_selection):
    """
    Displays a stacked line chart showing the dominance of pushups by user,
    with the option to select users to include in the plot.

    :param log_data: DataFrame containing the pushup logs with columns 'Timestamp', 'Pushups', and 'User'.
    :param user_selection: List of selected users to filter the data for plotting.
    """
    try:
        # Ensure 'Timestamp' is in datetime format
        log_data['Timestamp'] = pd.to_datetime(log_data['Timestamp'])
        
        if user_selection:
            # Group by date and user, then sum the pushups
            log_data['Date'] = log_data['Timestamp'].dt.date
            daily_pushups = log_data[log_data['User'].isin(user_selection)].groupby(['Date', 'User'])['Pushups'].sum().unstack(fill_value=0)
            
            # Normalize the data so each row sums to 100%
            daily_pushups_percent = daily_pushups.div(daily_pushups.sum(axis=1), axis=0) * 100
            
            # Create a Plotly figure for stacked lines
            fig = go.Figure()

            # Add each user as a separate line
            for user in user_selection:
                fig.add_trace(go.Scatter(
                    x=daily_pushups_percent.index,
                    y=daily_pushups_percent[user],
                    mode='lines',
                    stackgroup='one',  # Stack the lines
                    name=user,
                    line=dict(width=2),
                ))

            # Customize the layout
            fig.update_layout(
                #title="Dominance of Pushups by User Each Day",
                xaxis_title="Date",
                yaxis_title="Percentage of Pushups",
                xaxis=dict(tickformat="%Y-%m-%d"),
                legend_title="User",
                template="plotly_white",
                height=500,
                width=800
            )

            # Show the plot in Streamlit
            st.plotly_chart(fig)
        else:
            st.write("No users selected. Please select at least one user to display the graph.")
    
    except Exception as e:
        st.error(f"Error: {e}")

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
        recent_entries = log_data[['Date', 'Time', 'User', 'Pushups', 'comment']].tail(num_entries).iloc[::-1]
        st.markdown(
            f"""
            <style>
                /* Common Table Styles */
                .scrollable-table {{
                    max-height: 300px; /* Adjust the height as needed */
                    overflow-y: auto;
                    border: 1px solid #333;
                    margin-top: 30px; /* Add a bit of space on top for the header */
                }}
                .scrollable-table table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 14px;
                    text-align: left;
                }}
                .scrollable-table th, .scrollable-table td {{
                    padding: 8px 12px;
                    border: 1px solid #333;
                }}
                .scrollable-table td.comment {{
                    width: 100%; /* Let comments take up remaining space */
                }}

                /* Header Style for Both Light and Dark Modes */
                .scrollable-table th {{
                    position: sticky;
                    top: 0;
                    z-index: 1;  /* Ensure the header stays on top */
                    background-color: transparent; /* No background, just natural blending with the page */
                }}
            </style>
            <div class="scrollable-table">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Time</th>
                            <th>User</th>
                            <th>Pushups</th>
                            <th>Comment</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([
                            f"<tr><td>{row.Date}</td><td>{row.Time}</td><td>{row.User}</td><td>{row.Pushups}</td><td class='comment'>{row.comment or ''}</td></tr>"
                            for _, row in recent_entries.iterrows()
                        ])}
                    </tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True
        )


    except Exception as e:
        st.error(f"Error displaying the recent entries: {e}")

# table giving push ups done on the day by specific user
def display_pushups_today(log_data):
    # Ensure the 'Timestamp' column is in datetime format
    log_data['Timestamp'] = pd.to_datetime(log_data['Timestamp'])
    # Get today's date (without time component)
    #today = datetime.today().date()
    today = german_time.date()
    # Filter the DataFrame for today's pushups
    today_df = log_data[log_data['Timestamp'].dt.date == today]
    if not today_df.empty:
        # Group by user and sum the pushups
        pushups_today = today_df.groupby('User')['Pushups'].sum().reset_index()
        # Sort by pushups in descending order
        pushups_today = pushups_today.sort_values(by='Pushups', ascending=False).reset_index(drop=True)
        # Display the table with total pushups for each user today
        st.dataframe(pushups_today)
    else:
        # Display a message if no pushups were done today
        st.write("No pushups logged for today.")

# table giving the push up average (daily)
def display_daily_average_pushups(log_data, start_date="2024-12-31"):
    """
    Displays a table showing the daily average of pushups for each user, 
    divided by the total days passed since the start date, 
    sorted by the highest average.

    :param log_data: DataFrame containing pushup logs.
    :param start_date: Start date as a string in the format 'YYYY-MM-DD'.
    """
    # Ensure the 'Timestamp' column is in datetime format
    log_data['Timestamp'] = pd.to_datetime(log_data['Timestamp'])
    
    # Parse the start date and calculate the days passed
    start_date = pd.to_datetime(start_date).date()
    today = date.today()
    days_passed = (today - start_date).days + 1  # Include the start day
    
    if days_passed <= 0:
        st.error("Invalid start date: must be before today.")
        return

    # Calculate the total pushups for each user
    user_totals = log_data.groupby('User')['Pushups'].sum().reset_index()
    
    # Add a column for daily average based on total days passed
    user_totals['Daily Average'] = user_totals['Pushups'] / days_passed
    
    # Sort the table by the daily average in descending order
    user_totals = user_totals.sort_values(by='Daily Average', ascending=False).reset_index(drop=True)
    
    # Display the table
    st.dataframe(user_totals[['User', 'Daily Average']])

# display heatmap
def display_pushup_heatmap(log_data):
    """
    Displays a heatmap showing pushup activity by weekday and hour.
    Allows selection of a single user or all users combined.

    :param log_data: DataFrame containing pushup logs with 'Timestamp', 'Pushups', and 'User' columns.
    """
    # Ensure 'Timestamp' is in datetime format
    log_data['Timestamp'] = pd.to_datetime(log_data['Timestamp'])

    # Extract weekday and hour from the timestamp
    log_data['Weekday'] = log_data['Timestamp'].dt.day_name()
    log_data['Hour'] = log_data['Timestamp'].dt.hour

    # Define weekday order for plotting
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    # Create a user selection dropdown
    user_selection = st.selectbox(
        "Select User", 
        options=["All Users"] + log_data['User'].unique().tolist(), 
        index=0
    )

    # Filter the data for the selected user or keep all users
    if user_selection != "All Users":
        filtered_data = log_data[log_data['User'] == user_selection]
    else:
        filtered_data = log_data

    # Group by weekday and hour to sum pushups
    heatmap_data = (
        filtered_data.groupby(['Weekday', 'Hour'])['Pushups'].sum()
        .reindex(weekday_order, level=0)  # Ensure correct weekday order
        .unstack(fill_value=0)  # Reshape for heatmap
    )
        # Plot the heatmap
    plt.figure(figsize=(12, 6))
    sns.heatmap(
        heatmap_data, 
        annot=True, 
        fmt=".0f", 
        cmap="YlGnBu", 
        cbar_kws={'label': 'Total Pushups'}
    )
    plt.title(f"Pushup Activity Heatmap ({user_selection})")
    plt.xlabel("Hour")
    plt.ylabel("Weekday")
    plt.tight_layout()

    # Display the heatmap in Streamlit
    st.pyplot(plt)
    plt.close()


### GIMMICK AREA

# Custom CSS for the banner
st.markdown(
    """
    <style>
    .banner-container {
        position: relative;
        overflow: hidden; /* Ensures content outside is not visible */
        width: 100%;
        height: 50px; /* Adjust height as needed */
    }

    .banner-text {
        position: absolute;
        white-space: nowrap;
        display: inline-block;
        animation: scroll-text 15s linear infinite; /* Slower animation */
        font-size: 24px; /* Adjust font size */
        color: var(--text-color); /* Dynamic text color */
        padding-left: 0; /* Starts immediately without delay */
    }

    /* Animation */
    @keyframes scroll-text {
        0% {
            transform: translateX(100%); /* Start just outside the right edge */
        }
        100% {
            transform: translateX(-100%); /* End just outside the left edge */
        }
    }

    /* Light Mode Styles */
    @media (prefers-color-scheme: light) {
        .banner-container {
            --text-color: #000000; /* Black text for light mode */
        }
    }

    /* Dark Mode Styles */
    @media (prefers-color-scheme: dark) {
        .banner-container {
            --text-color: #ffffff; /* White text for dark mode */
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Add the scrolling text in the banner
st.markdown(
    """
    <div class="banner-container">
        <div class="banner-text">Some new features dropped. Hurrah. Hurrah. Test them out while they are still warm and send suggestions at the bottom of the applet. Timezone is now CET/CEST (the German one). Sorry to the Estonians :(. Cheers. Happy pushing.</div>
    </div>
    """,
    unsafe_allow_html=True
)








### START OF THE APP'S SCRIPT
# Title for the app
st.title("Push-Up Tracker.")

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
        #time.sleep(3)
        #st.empty()
    else:
        st.error("Invalid username or PIN code. Please try again.")

### MAIN CONTENT that is displayed when login was successfull
if username and pincode:
    if USER_DATABASE.get(username) == pincode:
        #st.success(f"Welcome, {username}!")
        #time.sleep(3)  # Wait for 3 seconds
        #st.empty()  # Clear the success message
        
        ### LOAD LOG TO BE DISPLAYED
        log_data = fetch_file_from_drive("pushup_log.csv")

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

            # Optional comment input
            comment = st.text_input("Add a comment (optional):")

            # If the button is pressed or Enter is hit, log the data
            if submit_button:
                # Get the current timestamp
                #timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                timestamp = german_time.strftime("%Y-%m-%d %H:%M:%S")
                # Create a DataFrame for the current entry
                new_entry = pd.DataFrame({"Timestamp": [timestamp], 
                                          "Pushups": [pushups], 
                                          "User": [username],
                                          "comment":[comment if comment.strip() else None]})

                # Try to append to the existing log file or create a new one
                # TODO: this is quite slow because it does two syncs. how can i get this to be faster?
                try:
                    # fetch file from GoogleDrive to Local
                    log = fetch_file_from_drive("pushup_log.csv")
                    # append local file with current push-ups
                    log = pd.concat([log, new_entry], ignore_index=True)

                    # push the updated local log file to Google Drive
                    push_file_to_drive(log, "pushup_log.csv")

                    # Placeholder success message
                    success_message = st.empty()
                    formatted_timestamp = german_time.strftime('%Y-%m-%d %H:%M')
                    success_message.success(f"Logged {pushups} push-ups at {formatted_timestamp}")
                    time.sleep(2)
                    # Clear the message
                    success_message.empty()

                except Exception as e:
                    st.error(f"Error writing to file: {e}")

        ### SHOW RECENT ENTRIES
        st.subheader("")
        st.header("Recent entries")
        display_recent_entries(log_data)
        #display_last_five_entries(log_data)
        
        ### SHOW TODAYS PUSHUPS PER USER
        st.subheader("")
        st.header("Today's pushups")
        display_pushups_today(log_data)

        ### SHOW AVERAGE OF ALL USERS
        st.subheader("")
        with st.expander("Average pushups per day"):
            display_daily_average_pushups(log_data)
        with st.expander ("Heatmap of pushups"):
            display_pushup_heatmap(log_data)

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

        if st.button("Show/Refresh Visualization"):
            # TODO: make it so that the vis is displayed but only updated by the button
            ## DISPLAY the accumulated push-ups graph
            st.subheader("Accumulated Push-Ups")
            display_accumulated_pushups(log_data, user_selection)

            ## DISPLAY the original push-ups over time graph
            st.subheader("Push-Ups Over Time")
            display_time_series_pushups(log_data, user_selection)

            ## DISPLAY dominance plot
            st.subheader("Pushup dominance")
            display_pushups_dominance_with_selection(log_data, user_selection)

        ## SHOW LEGACY DATA FROM 2022
        st.subheader("")
        st.subheader("Legacy") 
        # Use session_state to track if the expander is open
        if 'expander_opened' not in st.session_state:
            st.session_state.expander_opened = False       
        with st.expander("2022"):
            st.session_state.expander_opened = True
            if st.session_state.expander_opened:
            # fetch 2022 data from GoogleDrive
                log_data_2022 = fetch_file_from_drive("pushup_log_2022.csv")
                log_data_2022["Timestamp"] = pd.to_datetime(log_data_2022["Timestamp"])
                # user selection for 2022
                user_selection_2022 = st.multiselect(
                    "Select Users",
                    log_data_2022['User'].unique(),
                    default=list(log_data_2022['User'].unique()),  # Set default to all unique users
                    key="user_selection_2022"
                    )
                display_accumulated_pushups(log_data_2022, user_selection_2022)
                display_time_series_pushups(log_data_2022, user_selection_2022)

        with st.expander("1998"):
            st.image("https://media1.tenor.com/m/ZAMoMuQgf9UAAAAd/mapache-pedro.gif", width = 300)
        
        ### FUTURE CHANGES
        st.subheader("Stuff that will change (soon)")
        '''
        - make logging quicker (communication with cloud takes some time right now) look into st.session_state
        - make date-filter work
        - add optional comments to push-up addition
        - allow deletion of last few own activities by user
        - handle different timezones via user-database, will timezones register locally or globally?
        - add visualizations that were established in googlesheet in the last years
        - allow users to set personal goals for the year
        - might add different disciplines (squats or pull-ups or w/e)
        - differentiate types of push-ups
        - tackle possible issues when multiple users are adding push-ups at the same time
        - stable colors per user in the graphs
        - button that actively loads the vis? to increase speed of application
        - add prizes (cash or sexual favors. tbd.)
        '''

        ### USER SUGGESTIONS
        # fetch suggestions from GoogleDrive
        suggestion = fetch_file_from_drive("suggestion.csv")

        # Ensure suggestion is a DataFrame, if it's empty, initialize with the proper structure
        if suggestion is None or suggestion.empty:
            suggestion = pd.DataFrame(columns=["Timestamp", "Username", "Suggestion"])

        # Form for user suggestions
        with st.form("suggestion_form"):
            st.write("Have another idea for improvement?")
            # Text area for the suggestion (username is automatically logged)
            suggestion_text = st.text_area("Your Suggestion", "")
            submit_suggestion = st.form_submit_button("Submit Suggestion")

            if submit_suggestion:
                if suggestion_text.strip():  # Ensure the suggestion is not empty
                    # Create a DataFrame for the new suggestion
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_suggestion = pd.DataFrame({
                        "Timestamp": [timestamp],
                        "Username": [username],  # Automatically log the username
                        "Suggestion": [suggestion_text.strip()]
                    })
                    
                    # Append new suggestion to the existing suggestions DataFrame
                    suggestion = pd.concat([suggestion, new_suggestion], ignore_index=True)
                    
                    st.success("Thank you for your suggestion!")
                    
                    # Push the updated suggestions to Google Drive
                    push_file_to_drive(suggestion, "suggestion.csv")
                else:
                    st.warning("Please write a suggestion before submitting.")


    else:
        st.error("Invalid PIN code. Please try again.")

st.subheader("")
"""
💟 Happy pushing. Stefan.
"""



# TODO:
# - add all the graphs from the googlesheet
# - add specific timestamps to choose from e.g. "2022, 2023, last three months, current month, everything, custom range"
# - add leaderboard displaying the top three of differnt things
#     - top three days by "most PU/day"
#     - top most pushups in a day
# - time-format issues
# - make it possible to delete entries if they were made by mistake (only by the user who entered them)
# - make dominance sheet so that current user is always at the bottom
# - make more efficient, seperate streamlit for vis?
# - telegram integration?
# - with plotly, i actually don't need the user selection anymore because it can be done within the plot






