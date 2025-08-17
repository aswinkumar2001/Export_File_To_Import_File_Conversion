import streamlit as st
import pandas as pd
from datetime import datetime

# Title of the app
st.title("Export File to Importable File Converter")

# File uploader with acceptance message
uploaded_file = st.file_uploader("Upload your Excel file (xlsx/xls)", type=["xlsx", "xls"])

if uploaded_file is not None:
    errors = []
    try:
        # Read the Excel file
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        # Check if "Timestamp" column exists
        if "Timestamp" not in df.columns:
            errors.append("Error: 'Timestamp' column not found in the uploaded file.")
        else:
            # Convert Timestamp format from "Thursday, March 27, 2025 15:45" to "27/03/2025 15:45"
            try:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%A, %B %d, %Y %H:%M")
                df['Timestamp'] = df['Timestamp'].dt.strftime("%d/%m/%Y %H:%M")
            except ValueError as e:
                errors.append(f"Error converting timestamps: {str(e)}. Ensure format is 'Day, Month DD, YYYY HH:MM'.")
            
            # Process Meter names to remove everything after the last " - "
            try:
                for column in df.columns:
                    if column != "Timestamp":
                        # Extract Meter_Name by taking text before the last " - "
                        new_name = column.rsplit(" - ", 1)[0]
                        df.rename(columns={column: new_name}, inplace=True)
            except IndexError as e:
                errors.append(f"Error processing meter names: {str(e)}. Ensure meter names contain ' - ' separator.")
            except Exception as e:
                errors.append(f"Unexpected error processing meter names: {str(e)}.")
            
            # Melt the dataframe to convert from wide to long format
            try:
                melted_df = pd.melt(df, 
                                  id_vars=["Timestamp"], 
                                  var_name="Meter", 
                                  value_name="Energy Reading")
                
                # Remove any rows with NaN values in Energy Reading
                melted_df = melted_df.dropna(subset=["Energy Reading"])
                
                # Validate converted data
                if melted_df.empty:
                    errors.append("Warning: No valid data after conversion. Check your input file.")
            except Exception as e:
                errors.append(f"Error during data melting: {str(e)}.")
            
            # Display errors if any
            if errors:
                st.error("The following issues were encountered:")
                for error in errors:
                    st.write(error)
            
            # Display the converted data if no critical errors
            if not errors or all("Warning" in e for e in errors):
                st.write("Converted Data Preview:", melted_df)
                
                # Offer download as XLSX
                try:
                    output = melted_df.to_excel("converted_meter_data.xlsx", index=False, engine='openpyxl')
                    with open("converted_meter_data.xlsx", "rb") as file:
                        st.download_button(
                            label="Download Converted File as XLSX",
                            data=file,
                            file_name="converted_meter_data.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                except Exception as e:
                    errors.append(f"Error generating XLSX file: {str(e)}.")

    except Exception as e:
        errors.append(f"Unexpected error reading file: {str(e)}.")
        st.error("The following issues were encountered:")
        for error in errors:
            st.write(error)
