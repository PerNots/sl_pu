import streamlit as st
import pandas as pd
from datetime import datetime

# File to store push-up logs - where is this?
LOG_FILE = "pushup_log.csv"

# Title for the app
st.title("Push-Up Tracker")

# Input field for logging push-ups
pushups = st.number_input("Enter the number of push-ups you just did:", min_value=1, step=1)

# Button to log the push-ups
if st.button("Log Push-Ups"):
    # Get the current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create a DataFrame for the current entry
    new_entry = pd.DataFrame({"Timestamp": [timestamp], "Pushups": [pushups]})

    # Try to append to the existing log file or create a new one
    try:
        # Read the existing log file
        existing_log = pd.read_csv(LOG_FILE)
        # Append the new entry
        updated_log = pd.concat([existing_log, new_entry], ignore_index=True)
    except FileNotFoundError:
        # If the file doesn't exist, create it
        updated_log = new_entry

    # Save the updated log to the file
    updated_log.to_csv(LOG_FILE, index=False)

    st.success(f"Logged {pushups} push-ups at {timestamp}!")
