import streamlit as st

# Title for the app
st.title("Push-Up Tracker")

# Input field for logging push-ups
pushups = st.number_input("Enter the number of push-ups you just did:", min_value=1, step=1)

# Button to log the push-ups
if st.button("Log Push-Ups"):
    st.success(f"You just logged {pushups} push-ups!")

