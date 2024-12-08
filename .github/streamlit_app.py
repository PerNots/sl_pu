import streamlit as st
import pandas as pd
from datetime import datetime
import os
import altair as alt

# Ensure the data directory exists
os.makedirs("data", exist_ok=True)

# File to store push-up logs
LOG_FILE = "data/pushup_log.csv"

# Dictionary of users and their PIN codes
USER_DATABASE = st.secrets["user_database"]

# Debugging: Show where the file is saved
st.write(f"Saving to: {os.path.abspath(LOG_FILE)}")

# Title for the app
st.title("Push-Up Tracker")

# User Authentication
st.subheader("User Login")
username = st.selectbox("Select your username:", options=list(USER_DATABASE.keys()))  # Drop-down menu for usernames
pincode = st.text_input("Enter your PIN code:", type="password")

if username and pincode:
    if USER_DATABASE[username] == pincode:
        st.success(f"Welcome, {username}!")
        
        # Input field for logging push-ups
        pushups = st.number_input("Enter the number of push-ups you just did:", min_value=1, step=1)

        # Button to log the push-ups
        if st.button("Log Push-Ups"):
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

                st.success(f"Logged {pushups} push-ups at {timestamp}!")
            except Exception as e:
                st.error(f"Error writing to file: {e}")

        # Display the graph
        st.subheader("Push-Ups Over Time")

        if os.path.exists(LOG_FILE):
            try:
                # Read the log file
                log_data = pd.read_csv(LOG_FILE)

                # Convert the Timestamp column to a datetime type
                log_data["Timestamp"] = pd.to_datetime(log_data["Timestamp"])

                # Plot the data using Altair
                line_chart = alt.Chart(log_data).mark_line(point=True).encode(
                    x="Timestamp:T",
                    y="Pushups:Q",
                    color="User:N",  # Different colors for different users
                    tooltip=["Timestamp:T", "Pushups:Q", "User:N"]
                ).properties(
                    width=800,
                    height=400,
                    title="Push-Ups Over Time (All Users)"
                )

                st.altair_chart(line_chart, use_container_width=True)
            except Exception as e:
                st.error(f"Error reading or plotting data: {e}")
        else:
            st.write("No data to display yet.")

    else:
        st.error("Invalid PIN code. Please try again.")
