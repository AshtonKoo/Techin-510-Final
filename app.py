import streamlit as st
import os
import pandas as pd
import altair as alt
import folium
from streamlit_folium import st_folium
import sqlite3
import openai
from st_aggrid import AgGrid, GridUpdateMode
from st_aggrid.grid_options_builder import GridOptionsBuilder
from db import conn_str
from dotenv import load_dotenv
load_dotenv()

openai.api_key = os.getenv('OPENAI_API_KEY')
openai.api_base = os.getenv('OPENAI_API_BASE')


def load_data(query, conn_str):
    return pd.read_sql_query(query, conn_str)

def create_bar_chart(data, x_axis, y_axis, title):
    chart = alt.Chart(data).mark_bar().encode(
        x=x_axis, 
        y=y_axis
    ).properties(
        title=title
    ).interactive()
    return chart

def prepare_data(df):
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['year'] = df['date'].dt.year
    df['day_of_week'] = df['date'].dt.day_name()
    df['day_of_week_num'] = df['day_of_week'].map(
        {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    )

def create_map(df, location, zoom_start):
    m = folium.Map(location=location, zoom_start=zoom_start)
    for idx, row in df.iterrows():
        if pd.notnull(row['geolocation']):
            try:
                lat, lon = map(float, row['geolocation'].strip("{}").split(','))
                folium.Marker(
                    location=[lat, lon],
                    popup=f"{row['title']} - {row['date'].strftime('%Y-%m-%d')}",
                ).add_to(m)
            except ValueError:
                st.error(f"Error parsing geolocation for row {idx}: {row['geolocation']}")
    return m

def init_db():
    conn = sqlite3.connect('event_planner.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            details TEXT NOT NULL,
            category TEXT,
            location TEXT
        );
    ''')
    conn.commit()
    conn.close()

def main():
    st.title("Seattle Events")
    
    df = load_data("SELECT * FROM events", conn_str)
    prepare_data(df)
    

    category = st.selectbox("Select a category to filter", ['All'] + list(df['category'].unique()))
    
    date_range = st.date_input("Select date range", [])
    
    location = st.selectbox("Select a location to filter", ['All'] + list(df['location'].unique()))
    
    weather = st.selectbox("Select a weather condition to filter", ['All'] + list(df['weathercondition'].unique()))

    if category != 'All':
        df = df[df['category'] == category]
    if date_range:
        df = df[(df['date'].dt.date >= date_range[0]) & (df['date'].dt.date <= date_range[1])]
    if location != 'All':
        df = df[df['location'] == location]
    if weather != 'All':
        df = df[df['weathercondition'] == weather]

    st.write(df)

    st.subheader('Event Locations on Map')
    st_folium(create_map(df, [47.6504529, -122.3499861], 12), width=800, height=600)

    gd = GridOptionsBuilder.from_dataframe(df)
    gd.configure_selection(selection_mode='multiple', use_checkbox=True)
    gridoptions = gd.build()

    grid_table = AgGrid(df, height=250, gridOptions=gridoptions,
                    update_mode=GridUpdateMode.SELECTION_CHANGED)

    st.write('## Selected')
    # Assuming grid_table is your AgGridReturn object
    selected_rows = grid_table["selected_rows"]

    # Extract the data from the selected rows
    selected_data = [row for row in selected_rows]

    # Convert the selected data to a DataFrame
    selected_rows_df = pd.DataFrame(selected_data)

    # Filter the DataFrame to include only the 'title' and 'date' columns if they exist
    columns_to_select = ['title', 'date', 'category', 'location']
    if all(col in selected_rows_df.columns for col in columns_to_select):
        selected_columns = selected_rows_df[columns_to_select]

    # Display the selected columns
        st.dataframe(selected_columns)
    else:
        st.write("No selected yet")

    openai.api_key = os.getenv('OPENAI_API_KEY')
    openai.api_base = os.getenv('OPENAI_API_BASE')

    st.write("Chat with AI")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if 'input_flag' not in st.session_state:
        st.session_state.input_flag = True

    input_key = 'prompt' if st.session_state.input_flag else 'prompt_'

    prompt = st.text_input("Your question", value="", key=input_key)

    submit_button = st.button("Ask")

    if submit_button and prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
    
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=st.session_state.messages
            )
        
            answer = response.choices[0].message['content']

            st.session_state.messages.append({"role": "assistant", "content": answer})
        
        except Exception as e:
            st.error(f"Failed to generate a response: {e}")

        st.session_state.input_flag = not st.session_state.input_flag

    for message in st.session_state.messages:
        role = "You" if message["role"] == "user" else "AI"
        st.text_area(f"{role}:", value=message['content'], height=100, key=str(message)+str(st.session_state.messages.index(message)))

if __name__ == "__main__":
    main()
