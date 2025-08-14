import streamlit as st
import pandas as pd

# Title of the app
st.title("Excel Meter Data Converter")

# File uploader
uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    # Read the Excel file
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    
    # Melt the dataframe to convert from wide to long format
    melted_df = pd.melt(df, 
                        id_vars=["Timestamp"], 
                        var_name="Meter", 
                        value_name="Energy Reading")
    
    # Remove any rows with NaN values in Energy Reading
    melted_df = melted_df.dropna(subset=["Energy Reading"])
    
    # Display the converted data
    st.write("Converted Data Preview:", melted_df)
    
    # Offer download
    output = melted_df.to_csv(index=False)
    st.download_button(
        label="Download Converted File as CSV",
        data=output,
        file_name="converted_meter_data.csv",
        mime="text/csv"
    )