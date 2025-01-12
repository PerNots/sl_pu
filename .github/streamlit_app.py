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
import pytz
from datetime import datetime
import seaborn as sns
import matplotlib.colors as mcolors
# For syncing to GoogleDrive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload # Downloader
from googleapiclient.http import MediaIoBaseUpload

st.set_page_config(page_title="Pushup-Tracker", page_icon="random")


### SET TIME ZONE TO GERMANY - BERLIN
# Get the German timezone (CET/CEST)
# Get the current time in UTC and convert it to German time
utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)  # Get UTC time
german_time = utc_time.astimezone(pytz.timezone('Europe/Berlin'))


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
# git push origin <branch>
# git checkout <branch>
# git merge <branch>

# assign stable colors
def generate_user_colors(user_database):
    """
    Generate stable user colors using the Set3 ColorBrewer palette.
    
    :param user_database: Dictionary of users (keys) and PINs (values) from Streamlit secrets.
    :return: A dictionary mapping each user to a ColorBrewer color (hex format).
    """
    users = list(user_database.keys())
    num_users = len(users)
    
    # Get the Set3 ColorBrewer palette (you can adjust the number of colors as needed)
    palette = sns.color_palette("Set3", num_users)
    
    # Assign colors to users
    user_colors = {user: mcolors.to_hex(palette[i]) for i, user in enumerate(users)}
    return user_colors

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
                color_discrete_map=USER_COLORS,  # Use the USER_COLORS dictionary
                labels={"Timestamp": "Time", "Accumulated Pushups": "Accumulated Pushups"}
            )

            # Show the chart in Streamlit
            st.plotly_chart(accumulated_chart, use_container_width=True)
        else:
            st.write("No users selected. Please select at least one user to display the graph.")

    except Exception as e:
        st.error(f"Error reading or plotting accumulated data: {e}")

# Graph for accumulated pushups filtered by month
def display_monthly_accumulated_pushups(log_data, user_selection):
    try:
        # Convert the Timestamp column to datetime format
        log_data['Timestamp'] = pd.to_datetime(log_data['Timestamp'])
        log_data['Month'] = log_data['Timestamp'].dt.to_period('M')  # Extract month as a period

        # Get unique months for the dropdown and set the default to the current month
        unique_months = log_data['Month'].dt.strftime('%Y-%m').unique()
        current_month = pd.Timestamp.now().to_period('M').strftime('%Y-%m')

        # Initialize session state for the month selector if not set
        if "selected_month" not in st.session_state:
            st.session_state.selected_month = current_month

        # Dropdown for selecting the month, directly linked to session state
        selected_month = st.selectbox(
            "Select a month to display:",
            unique_months,
            index=list(unique_months).index(st.session_state.selected_month),
            key="selected_month"
        )

        # Filter data for the selected month
        filtered_data = log_data[log_data['Month'].dt.strftime('%Y-%m') == selected_month]

        # Filter data for selected users
        if user_selection:
            filtered_data = filtered_data[filtered_data['User'].isin(user_selection)]

        # Reset accumulated push-ups for the selected month
        filtered_data['Accumulated Pushups'] = (
            filtered_data.groupby('User')['Pushups'].cumsum()
        )

        # Plot the data
        accumulated_chart = px.line(
            filtered_data,
            x="Timestamp",
            y="Accumulated Pushups",
            color="User",
            color_discrete_map=USER_COLORS,  # Use the USER_COLORS dictionary
            category_orders={"User": list(USER_COLORS.keys())},  # Ensure consistent color order
            labels={"Timestamp": "Time", "Accumulated Pushups": "Accumulated Pushups"}
        )

        # Show the chart
        st.plotly_chart(accumulated_chart, use_container_width=True)

    except Exception as e:
        st.error(f"Error reading or plotting accumulated data: {e}")

# graph for pushups over time
def display_time_series_pushups(log_data, user_selection):
    """
    Displays a time-series graph of pushups for the selected users using Plotly,
    aggregated to show one datapoint per day.

    :param log_data: DataFrame containing the pushup logs with columns 'Timestamp', 'Pushups', and 'User'.
    :param user_selection: List of selected users to filter the data for plotting.
    """
    try:
        # Ensure the Timestamp column is in datetime format
        log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])

        # Filter data based on selected users
        if user_selection:
            filtered_data = log_data[log_data['User'].isin(user_selection)]

            # Aggregate data to sum pushups per day per user
            filtered_data['Date'] = filtered_data['Timestamp'].dt.date  # Extract date component
            daily_data = (
                filtered_data.groupby(['Date', 'User'])['Pushups']
                .sum()
                .reset_index()
            )

            # Create the Plotly figure
            fig = px.line(
                daily_data,
                x="Date",
                y="Pushups",
                color="User",
                color_discrete_map=USER_COLORS,
                labels={"Date": "Date", "Pushups": "Pushups", "User": "User"},
            )

            # Customize the layout for better interaction
            fig.update_layout(
                width=800,
                height=400,
                xaxis_title="Date",
                yaxis_title="Pushups",
                margin=dict(l=40, r=40, t=40, b=40),
                legend_title="Users",
            )

            # Enable interactive tools like zoom and pan
            fig.update_layout(
                dragmode="zoom",
                hovermode="x unified"
            )

            # Display the chart in Streamlit
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No users selected. Please select at least one user to display the graph.")

    except Exception as e:
        st.error(f"Error reading or plotting data: {e}")

# dominance graph
def display_pushups_dominance_with_selection(log_data, user_selection, username):
    """
    Displays a stacked line chart showing the dominance of pushups by user,
    with the current user always as the bottom-most line.

    :param log_data: DataFrame containing the pushup logs with columns 'Timestamp', 'Pushups', and 'User'.
    :param user_selection: List of selected users to filter the data for plotting.
    :param username: The current user, who will always appear as the bottom-most line.
    """
    try:
        # Ensure 'Timestamp' is in datetime format
        log_data['Timestamp'] = pd.to_datetime(log_data['Timestamp'])
        
        if user_selection:
            # Ensure the current user is in the selection
            if username not in user_selection:
                user_selection.append(username)
            
            # Group by date and user, then sum the pushups
            log_data['Date'] = log_data['Timestamp'].dt.date
            daily_pushups = log_data[log_data['User'].isin(user_selection)].groupby(['Date', 'User'])['Pushups'].sum().unstack(fill_value=0)
            
            # Normalize the data so each row sums to 100%
            daily_pushups_percent = daily_pushups.div(daily_pushups.sum(axis=1), axis=0) * 100
            
            # Reorder columns so the current user is the first one
            user_order = [username] + [user for user in user_selection if user != username]
            daily_pushups_percent = daily_pushups_percent[user_order]
            
            # Create a Plotly figure for stacked lines
            fig = go.Figure()

            # Add each user as a separate line in the specified order
            for user in user_order:
                fig.add_trace(go.Scatter(
                    x=daily_pushups_percent.index,
                    y=daily_pushups_percent[user],
                    mode='lines',
                    stackgroup='one',  # Stack the lines
                    name=user,
                    line=dict(width=2, color=USER_COLORS.get(user, '#000000')),  # Use color from USER_COLORS                
                ))

            # Customize the layout
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Percentage of Pushups",
                xaxis=dict(
                    tickformat="%b %-d",  # Display "Jan 1", "Jan 2", etc.
                    tickangle=0  # Keep ticks horizontal
                ),
                legend_title="User",
                template="plotly_white",
                height=500,
                width=800,
                margin=dict(l=40, r=40, t=10, b=40),  # Reduce top margin
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
        # Display the recent entries in a scrollable element
        st.dataframe(
            data = recent_entries,
            height = 250,  # Set the height of the scrollable area
            use_container_width = True,
            hide_index = True
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
        st.dataframe(data=pushups_today, 
                     hide_index=True)
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
    user_totals['Daily Average'] = user_totals['Daily Average'].round(1)
    # Display the table
    st.dataframe(user_totals[['User', 'Daily Average']], hide_index=True)

# Table personal stats
def display_user_stats(log_data, user_selection):
    """
    Display the current user's pushup stats: total, average, 7-day floating average,
    expected pushups for 31.12.2025, and standard deviation.

    :param log_data: DataFrame containing the pushup logs with 'Timestamp', 'Pushups', and 'User' columns.
    :param user_selection: Selected user to display stats for.
    """
    try:
        # Filter the data for the selected user
        user_data = log_data[log_data['User'] == user_selection].copy()

        # Convert the Timestamp column to datetime
        user_data['Timestamp'] = pd.to_datetime(user_data['Timestamp'])

        # Set a start date for tracking stats (e.g., from 31.12.2024 onward)
        start_date = datetime(2024, 12, 31)
        user_data = user_data[user_data['Timestamp'] >= start_date]

        # Create a daily pushups series, summing pushups by day
        user_data['Date'] = user_data['Timestamp'].dt.date
        daily_pushups = user_data.groupby('Date')['Pushups'].sum()

        # Create a complete date range from the start date to the latest recorded date
        all_dates = pd.date_range(start=start_date, end=daily_pushups.index.max(), freq='D')

        # Reindex the daily pushups data to include all dates, filling missing days with 0
        daily_pushups_full = daily_pushups.reindex(all_dates, fill_value=0)

        # Calculate the total pushups
        total_pushups = daily_pushups_full.sum()

        # Calculate the average pushups per day
        average_pushups = daily_pushups_full.mean().round(1)

        # Calculate the 7-day floating average
        daily_pushups_7day_avg = daily_pushups_full.rolling(window=7, min_periods=1).mean().round(1)

        # Calculate the expected pushups for 31.12.2025
        end_date = datetime(2025, 12, 31)
        days_to_2025 = (end_date - daily_pushups_full.index[-1]).days
        expected_pushups_2025 = (average_pushups * days_to_2025).round(0)

        # Calculate the standard deviation of pushups
        std_dev_pushups = daily_pushups_full.std().round(1)

        # Create a summary DataFrame
        stats = {
            "Metric": ["Name", "Total Pushups", "Average Pushups", "7-Day Floating Average", "Expected Pushups for 31.12.2025", "Standard Deviation"],
            "Value": [user_selection, total_pushups, average_pushups, daily_pushups_7day_avg.iloc[-1], expected_pushups_2025, std_dev_pushups]
        }
        stats_df = pd.DataFrame(stats)

        # Display the stats table
        st.write(f"### {user_selection}'s Pushup Stats")
        st.dataframe(stats_df, hide_index=True)

    except Exception as e:
        st.error(f"Error calculating user stats: {e}")

    except Exception as e:
        st.error(f"Error calculating stats for {user_selection}: {e}")

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

    # Plot the heatmap using Plotly
    fig = px.imshow(
        heatmap_data.values, 
        labels=dict(x="Hour", y="Weekday", color="Total Pushups"),
        x=heatmap_data.columns,
        y=heatmap_data.index,
        color_continuous_scale="YlGnBu",
        title=f"Pushup Activity Heatmap ({user_selection})"
    )

    # Update layout for better visualization
    fig.update_layout(
        xaxis_title="Hour",
        yaxis_title="Weekday",
        coloraxis_colorbar=dict(title=""),
        template="plotly_dark" if st.session_state.get("theme", {"base": "light"})["base"] == "dark" else "plotly",
        height=500
    )

    # Display the heatmap in Streamlit
    st.plotly_chart(fig)

# total pushups done within the project
def display_total_accumulated_pushups(log_data):
    """
    Displays a time-series graph of the total accumulated pushups over time.

    :param log_data: DataFrame containing the pushup logs with columns 'Timestamp' and 'Pushups'.
    """
    try:
        # Ensure the Timestamp column is in datetime format
        log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])

        # Aggregate data to sum pushups per day
        log_data['Date'] = log_data['Timestamp'].dt.date  # Extract date component
        daily_totals = (
            log_data.groupby('Date')['Pushups']
            .sum()
            .reset_index()
            .sort_values('Date')  # Ensure data is sorted by date
        )

        # Compute the accumulated sum of pushups
        daily_totals['Accumulated Pushups'] = daily_totals['Pushups'].cumsum()

        # Create the Plotly figure
        fig = px.line(
            daily_totals,
            x="Date",
            y="Accumulated Pushups",
            labels={"Date": "Date", "Accumulated Pushups": "Total Pushups"},
            #title="Total Accumulated Pushups Over Time",
        )

        # Customize the layout for better interaction
        fig.update_layout(
            width=800,
            height=400,
            xaxis_title="Date",
            yaxis_title="Accumulated Pushups",
            margin=dict(l=40, r=40, t=40, b=40),
            dragmode="zoom",  # Enable zooming and panning
            hovermode="x unified"  # Unified hover mode for better tooltips
        )

        # Display the chart in Streamlit
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error reading or plotting data: {e}")

# total pushups done within the project stacked users
def display_total_accumulated_pushups_by_user(log_data, username):
    """
    Displays a stacked area chart of the accumulated pushups by each user, 
    with the current user as the bottommost entry.

    :param log_data: DataFrame containing the pushup logs with columns 'Timestamp', 'Pushups', and 'User'.
    :param username: The current user, who will always appear as the bottom-most entry.
    """
    try:
        # Ensure 'Timestamp' is in datetime format
        log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])

        # Extract date component and sum pushups per user per day
        log_data['Date'] = log_data['Timestamp'].dt.date
        daily_totals = (
            log_data.groupby(['Date', 'User'])['Pushups']
            .sum()
            .reset_index()
            .sort_values(['Date', 'User'])  # Ensure data is sorted by date and user
        )

        # Pivot data to have one column per user
        daily_totals_pivot = daily_totals.pivot(index='Date', columns='User', values='Pushups').fillna(0)

        # Ensure the current user is the first column
        user_order = [username] + [user for user in daily_totals_pivot.columns if user != username]
        daily_totals_pivot = daily_totals_pivot[user_order]

        # Compute cumulative sum for each user over time
        accumulated_pushups = daily_totals_pivot.cumsum()

        # Create a stacked area chart
        fig = go.Figure()

        for user in accumulated_pushups.columns:
            fig.add_trace(go.Scatter(
                x=accumulated_pushups.index,
                y=accumulated_pushups[user],
                mode='lines',
                stackgroup='one',  # Enable stacking
                name=user,
                line=dict(width=2, color=USER_COLORS.get(user, '#000000')),
            ))

        # Customize the layout
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Total Pushups",
            xaxis=dict(
                tickformat="%b %-d",  # Display "Jan 1", "Jan 2", etc.
            ),
            legend_title="User",
            template="plotly_white",
            height=500,
            width=800,
            margin=dict(l=40, r=40, t=10, b=40),  # Adjust margins
            dragmode="zoom",  # Enable zooming and panning
            hovermode="x unified"  # Unified hover mode for tooltips
        )

        # Display the chart in Streamlit
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")

def display_daily_pushup_contributions(log_data, username):
    """
    Displays a stacked bar plot of daily pushup contributions by each user.

    :param log_data: DataFrame containing the pushup logs with columns 'Timestamp', 'Pushups', and 'User'.
    :param username: The current user, who will always appear as the bottom-most bar segment.
    """
    try:
        # Ensure 'Timestamp' is in datetime format
        log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])

        # Extract date component and sum pushups per user per day
        log_data['Date'] = log_data['Timestamp'].dt.date
        daily_totals = (
            log_data.groupby(['Date', 'User'])['Pushups']
            .sum()
            .reset_index()
            .sort_values(['Date', 'User'])  # Ensure data is sorted by date and user
        )

        # Pivot data to have one column per user
        daily_totals_pivot = daily_totals.pivot(index='Date', columns='User', values='Pushups').fillna(0)

        # Ensure the current user is the first column
        user_order = [username] + [user for user in daily_totals_pivot.columns if user != username]
        daily_totals_pivot = daily_totals_pivot[user_order]

        # Create a stacked bar chart
        fig = go.Figure()

        for user in daily_totals_pivot.columns:
            fig.add_trace(go.Bar(
                x=daily_totals_pivot.index,
                y=daily_totals_pivot[user],
                name=user,
                marker_color=USER_COLORS.get(user, '#000000') 
            ))

        # Customize the layout
        fig.update_layout(
            barmode="stack",  # Stacked bars
            xaxis_title="Date",
            yaxis_title="Pushups",
            xaxis=dict(
                tickformat="%b %-d",  # Display "Jan 1", "Jan 2", etc.
            ),
            legend_title="User",
            template="plotly_white",
            height=500,
            width=800,
            margin=dict(l=40, r=40, t=10, b=40),  # Adjust margins
        )

        # Display the chart in Streamlit
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")


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
        background-color: rgba(209, 166, 48, 0.6); /* Fixed background color with 60% opacity */
        display: flex;
        align-items: center; /* Vertically center text */
        justify-content: center; /* Horizontally center text */
    }

    .banner-text {
        white-space: nowrap;
        animation: scroll-text 25s linear infinite; /* Slower animation */
        font-size: 24px; /* Adjust font size */
        color: #000000; /* Fixed text color (black) */
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
    </style>
    """,
    unsafe_allow_html=True
)

# Add the scrolling text in the banner
st.markdown(
    """
    <div class="banner-container">
        <div class="banner-text">Newest feature: Accumulated push-ups are now displayed month-wise (in addition to the full-year-view). Cheers. Happy pushing.</div>
    </div>
    """,
    unsafe_allow_html=True
)








### START OF THE APP'S SCRIPT

USER_COLORS = generate_user_colors(USER_DATABASE)  # Viridis-based color mapping

#st.text(USER_COLORS)
# Title for the app
st.title("Push-Up Tracker.")

# Login-part
# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'username' not in st.session_state:
    st.session_state['username'] = None

if not st.session_state.get('logged_in', False):
    # Debugging: Print the raw query parameters
    query_params = st.query_params
    #st.write(f"Query parameters: {query_params}")

    # Get prefilled username from query parameters
    prefilled_username = query_params.get("username", None)  # Default to None if not found
    prefilled_pin = query_params.get("pin", None)
    #st.write(f"Prefilled username from URL: {prefilled_username}")

    with st.form(key='login_form'):
        col1, col2, col3 = st.columns([2, 2, 1])  # Adjust column ratios as needed
        # User selection dropdown
        with col1:
            username_options = list(USER_DATABASE.keys())
            matching_index = (
                username_options.index(prefilled_username)
                if prefilled_username in username_options
                else 0  # Default to first option if no match
            )
            username = st.selectbox(
                "Select User",
                options=username_options,
                index=matching_index,
                label_visibility="collapsed",
                placeholder="Username",
                key="username_select"  # Assign a unique key
            )
        # PIN code input field
        with col2:
            pincode = st.text_input(
                "Enter PIN Code",
                type="password",
                label_visibility="collapsed",
                placeholder="PIN",
                value=prefilled_pin if prefilled_pin else "",  # Prefill the PIN if available
                key="pin_input"  # Assign a unique key
            )
        with col3:
            login = st.form_submit_button("Login", use_container_width=True)  # This button now submits the form
        with st.expander("Want to log-in faster?"):
            st.markdown(
                '<p style="font-size:12px; color:gray; background-color:#d9fdd3; padding:6px; margin:4px 0px 4px 0px; border-radius:4px;">'
                '- For faster login, save the website as a bookmark with the URL:<br>'
                '<strong>"pushup.streamlit.app?username=*yourname*"</strong> First letter needs to be caps.<br>'
                '- For much faster login save as:<br>'
                '<strong>"pushup.streamlit.app?username=*yourname*&pin=*yourpin*"</strong> Be aware that this will store your PIN in the bookmark URL.<br>'
                'Thanks Lea for the tip!</p>',
                unsafe_allow_html=True
            )
    # Login Validation
    if login:
        if username in USER_DATABASE and pincode == USER_DATABASE[username]:
            st.session_state['logged_in'] = True  # Mark as logged in
            st.session_state['username'] = username  # Store username
            st.success(f"Welcome, {username}!")
        else:
            st.error("Invalid username or PIN!")

# Initialize session state for log_data if not already present
### LOAD LOG TO BE DISPLAYED
if 'log_data' not in st.session_state:
    st.session_state.log_data = fetch_file_from_drive("pushup_log.csv")

### MAIN CONTENT that is displayed when login was successfull
if st.session_state['logged_in']:
    # if USER_DATABASE.get(username) == pincode:
    #st.success(f"Welcome, {username}!")
    #time.sleep(3)  # Wait for 3 seconds
    #st.empty()  # Clear the success message
    username = st.session_state['username']
    ### LOAD LOG TO BE DISPLAYED
    #log_data = fetch_file_from_drive("pushup_log.csv")

    ## ADD PUSH-UPS
    # Create a form to group the input and button together
    with st.form("log_pushups_form"):
        # Create two columns to place the input field and button side by side
        # Input field for the number of push-ups (broad column)
        pushups = st.number_input("Enter the number of push-ups you just did:", min_value=1, step=1, label_visibility="collapsed")
        col1, col2 = st.columns([3, 1], vertical_alignment="bottom")  # Adjust the width ratio as needed
        with col1:
            # Optional comment input (right column)
            comment = st.text_input("Add a comment (optional):", label_visibility="collapsed", placeholder="Add an optional comment here...")
        with col2:
            # Submit button (aligned with the bottom of the comment input)
            submit_button = st.form_submit_button("Log Push-Ups", use_container_width=True)

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
            with st.spinner('Working on it...'):
                try:
                    # fetch file from GoogleDrive to Local
                    log = fetch_file_from_drive("pushup_log.csv")
                    # append local file with current push-ups
                    log = pd.concat([log, new_entry], ignore_index=True)
                    # push the updated local log file to Google Drive
                    push_file_to_drive(log, "pushup_log.csv")
                    # Update the log in session_state to reflect the changes
                    st.session_state.log_data = log
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
    display_recent_entries(st.session_state.log_data)
    #display_last_five_entries(log_data)
    
    ### SHOW TODAYS PUSHUPS PER USER
    st.subheader("")
    st.header("Today's pushups")
    display_pushups_today(st.session_state.log_data)

    ### SHOW PERSONAL STATS
    st.subheader("")
    st.header("Your personal stats!")
    display_user_stats(st.session_state.log_data, username)

    ### SHOW AVERAGE OF ALL USERS
    # TOO COMPETITIVE, TOO PERSONAL
    #with st.expander("Average pushups per day"):
    #    display_daily_average_pushups(st.session_state.log_data)

    user_selection = list(st.session_state.log_data['User'].unique())

    with st.expander ("Heatmap of pushups"):
        display_pushup_heatmap(st.session_state.log_data)

    with st.expander ("Accumulated pushups by month and user"):
        display_monthly_accumulated_pushups(st.session_state.log_data, user_selection)

    ### VISUALIZATION
    st.subheader("")
    st.header("Visualization")
    
    ### FILTER SECTION WAS REMOVED HERE BECAUSE PLOTLY IS CAPABLE OF DOING THIS


    if st.button("Show/Refresh Visualization"):
        # TODO: make it so that the vis is displayed but only updated by the button
        
        st.subheader("Accumulated Push-Ups")
        ## DISPLAY the accumulated push-ups graph
        st.text("Accumulated, unstacked, full year")
        display_accumulated_pushups(st.session_state.log_data, user_selection)

        ## DISPLAY the original push-ups over time graph
        st.subheader("Push-Ups Over Time")
        st.text("Not-accumulated, unstacked")
        display_time_series_pushups(st.session_state.log_data, user_selection)

        ## DISPLAY dominance plot
        st.subheader("Pushup dominance")
        st.text("Percentage of all pushups done by each user per day. Current user is always the bottommost line.")
        display_pushups_dominance_with_selection(st.session_state.log_data, user_selection, username)

        ## DISPLAY total pushups done within the project
        st.subheader("Total pushups done for this tracker")
        st.text("Accumulated, stacked")
        display_total_accumulated_pushups_by_user(st.session_state.log_data, username)

        ## DISPLAY TODO:
        st.subheader("Total pushups done per day and how much each user contributed")
        st.text("Not-accumulated, stacked")
        display_daily_pushup_contributions(st.session_state.log_data, username)


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
            #user_selection_2022 = st.multiselect(
            #    "Select Users",
            #    log_data_2022['User'].unique(),
            #    default=list(log_data_2022['User'].unique()),  # Set default to all unique users
            #    key="user_selection_2022"
            #    )
            user_selection_2022 = list(log_data_2022['User'].unique())
            display_accumulated_pushups(log_data_2022, user_selection_2022)
            display_time_series_pushups(log_data_2022, user_selection_2022)

    with st.expander("1998"):
        st.image("https://media1.tenor.com/m/ZAMoMuQgf9UAAAAd/mapache-pedro.gif", width = 300)
    
    ### FUTURE CHANGES
    st.subheader("Stuff that will change (soon)")
    '''
    - get different color palette (suggestions welcome)
    - allow deletion of last few own activities by user
    - handle different timezones via user-database, will timezones register locally or globally?
    - add visualizations that were established in googlesheet in the last years
    - allow users to set personal goals for the year
    - might add different disciplines (squats or pull-ups or w/e)
    - differentiate types of push-ups
    - tackle possible issues when multiple users are adding push-ups at the same time
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
    st.text("Log in to see data and log pushups")

st.subheader("")
"""
💟 Happy pushing. Stefan.
"""



