import streamlit as st
import pandas as pd
from datetime import datetime
import io
import re

# Title of the app
st.title("Export File to Importable File Converter")

# File uploader with acceptance message
uploaded_file = st.file_uploader("Upload your data file", type=["xlsx", "xls", "csv"])

def extract_meter_and_reading(column_name):
    """
    Extract meter name and reading type from column name
    Format: "MeterName - ReadingType (unit)" or "MeterName - ReadingType_unit"
    Returns: (meter_name, reading_type, unit)
    """
    if " - " not in column_name:
        return column_name, "Unknown Reading", "Unknown Unit"
    
    # Split into meter and reading parts
    parts = column_name.split(" - ", 1)
    meter_name = parts[0].strip()
    reading_part = parts[1].strip()
    
    # Extract reading type and unit using regex
    # Pattern for "ReadingType (unit)"
    pattern_with_parentheses = r"^(.*?)\s*\((.*?)\)$"
    match = re.match(pattern_with_parentheses, reading_part)
    
    if match:
        reading_type = match.group(1).strip()
        unit = match.group(2).strip()
    else:
        # Pattern for "ReadingType_unit" or just "ReadingType"
        if "_" in reading_part:
            reading_parts = reading_part.rsplit("_", 1)
            reading_type = reading_parts[0].strip()
            unit = reading_parts[1].strip()
        else:
            reading_type = reading_part
            unit = "Unknown Unit"
    
    return meter_name, reading_type, unit

if uploaded_file is not None:
    errors = []
    warnings = []
    
    try:
        # Determine file type and read accordingly
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        if file_extension in ['xlsx', 'xls']:
            # Read Excel file
            df = pd.read_excel(uploaded_file, engine='openpyxl')
            st.success(f"✅ Successfully loaded Excel file: {uploaded_file.name}")
            
        elif file_extension == 'csv':
            # Provide CSV reading options
            st.sidebar.subheader("CSV Import Options")
            csv_encoding = st.sidebar.selectbox(
                "Select encoding",
                ["utf-8", "latin-1", "iso-8859-1", "cp1252"],
                index=0,
                help="If you encounter encoding errors, try different encodings"
            )
            
            csv_separator = st.sidebar.selectbox(
                "Select separator",
                [",", ";", "\t", "|"],
                index=0,
                help="Character used to separate columns in your CSV file"
            )
            
            # Read CSV file
            df = pd.read_csv(uploaded_file, encoding=csv_encoding, sep=csv_separator)
            st.success(f"✅ Successfully loaded CSV file: {uploaded_file.name}")
        
        # Display original data preview
        st.subheader("Original Data Preview")
        st.write(f"File: {uploaded_file.name} | Shape: {df.shape} | Columns: {len(df.columns)}")
        st.write(df.head())
        
        # Show column names for reference
        with st.expander("View all column names"):
            st.write("Columns in your file:", list(df.columns))
        
        # Check if "Timestamp" column exists (case-insensitive)
        timestamp_columns = [col for col in df.columns if 'timestamp' in col.lower()]
        
        if not timestamp_columns:
            errors.append("Error: No 'Timestamp' column found in the uploaded file.")
            st.error("Please check that your file contains a 'Timestamp' column.")
        else:
            # Use the first timestamp-like column found
            timestamp_col = timestamp_columns[0]
            if len(timestamp_columns) > 1:
                warnings.append(f"Multiple timestamp-like columns found. Using '{timestamp_col}'")
            
            # Rename to standard "Timestamp" for consistency
            if timestamp_col != "Timestamp":
                df = df.rename(columns={timestamp_col: "Timestamp"})
                warnings.append(f"Renamed column '{timestamp_col}' to 'Timestamp'")
            
            # Convert Timestamp format
            try:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%A, %B %d, %Y %H:%M")
                df['Timestamp'] = df['Timestamp'].dt.strftime("%d/%m/%Y %H:%M")
            except ValueError as e:
                # Try alternative parsing if exact format doesn't work
                try:
                    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime("%d/%m/%Y %H:%M")
                    warnings.append("Timestamp format was auto-detected. Please verify the conversion.")
                except:
                    errors.append(f"Error converting timestamps: {str(e)}. Ensure format is 'Day, Month DD, YYYY HH:MM'.")
            
            # Process each data column and build the final dataframe
            try:
                # Initialize empty list to store all processed data
                all_data = []
                reading_types = set()
                
                # Process each data column (excluding Timestamp)
                data_columns = [col for col in df.columns if col != "Timestamp"]
                
                st.subheader("Column Processing")
                progress_bar = st.progress(0)
                
                for i, column in enumerate(data_columns):
                    progress_bar.progress((i + 1) / len(data_columns))
                    
                    # Extract meter name, reading type, and unit
                    meter_name, reading_type, unit = extract_meter_and_reading(column)
                    reading_types.add(reading_type)
                    
                    # Create temporary dataframe for this column
                    temp_df = df[['Timestamp', column]].copy()
                    temp_df = temp_df.rename(columns={column: 'Value'})
                    temp_df['Meter'] = meter_name
                    temp_df['ReadingType'] = reading_type
                    temp_df['Unit'] = unit
                    
                    # Remove rows with NaN values
                    temp_df = temp_df.dropna(subset=['Value'])
                    
                    if not temp_df.empty:
                        all_data.append(temp_df)
                    
                    st.write(f"**{column}** → Meter: '{meter_name}', Reading: '{reading_type}', Unit: '{unit}'")
                
                if not all_data:
                    errors.append("No valid data found after processing all columns.")
                else:
                    # Combine all data
                    combined_df = pd.concat(all_data, ignore_index=True)
                    
                    # Create the final pivoted dataframe
                    melted_df = combined_df.pivot_table(
                        index=['Timestamp', 'Meter'],
                        columns='ReadingType',
                        values='Value',
                        aggfunc='first'  # Take first value if duplicates exist
                    ).reset_index()
                    
                    # Flatten column names
                    melted_df.columns.name = None
                    
                    # Add unit information as a separate metadata
                    unit_info = combined_df[['ReadingType', 'Unit']].drop_duplicates()
                    unit_dict = dict(zip(unit_info['ReadingType'], unit_info['Unit']))
                    
                    # Remove any rows where all reading values are NaN
                    reading_columns = [col for col in melted_df.columns if col not in ['Timestamp', 'Meter']]
                    melted_df = melted_df.dropna(subset=reading_columns, how='all')
                    
                    if melted_df.empty:
                        errors.append("No valid data after pivoting. Check your input file.")
                    else:
                        # Display processing summary
                        st.success(f"✅ Processed {len(data_columns)} columns into {len(melted_df)} records")
                        st.write(f"**Reading types found:** {list(reading_types)}")
                        
            except Exception as e:
                errors.append(f"Error during data processing: {str(e)}")
        
    except UnicodeDecodeError as e:
        errors.append(f"Encoding error reading CSV file. Try changing the encoding in CSV Import Options.")
    except Exception as e:
        errors.append(f"Error reading file: {str(e)}")
    
    # Display warnings and errors
    if warnings:
        st.warning("Conversion completed with warnings:")
        for warning in warnings:
            st.write(f"• {warning}")
    
    if errors:
        st.error("Conversion failed with errors:")
        for error in errors:
            st.write(f"• {error}")
    else:
        # Display success message and converted data
        st.success("✅ File converted successfully!")
        
        st.subheader("Converted Data Preview")
        st.write(f"Shape: {melted_df.shape}")
        st.write(melted_df.head(10))
        
        # Data summary
        st.subheader("Data Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", len(melted_df))
        with col2:
            st.metric("Unique Meters", melted_df['Meter'].nunique())
        with col3:
            st.metric("Reading Types", len(reading_types))
        with col4:
            st.metric("Date Range", f"{melted_df['Timestamp'].min()} to {melted_df['Timestamp'].max()}")
        
        # Display unit information
        with st.expander("📊 Reading Types and Units"):
            unit_info_df = pd.DataFrame([
                {'Reading Type': rt, 'Unit': unit_dict.get(rt, 'Unknown')} 
                for rt in reading_types
            ])
            st.write(unit_info_df)
        
        # Display meter statistics
        with st.expander("View Meter Statistics"):
            meter_stats = melted_df.groupby('Meter').agg({
                'Timestamp': 'count'
            }).rename(columns={'Timestamp': 'Record Count'})
            st.write(meter_stats)
        
        # Offer download as XLSX without saving to disk
        try:
            # Create in-memory buffer for the Excel file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main data sheet
                melted_df.to_excel(writer, index=False, sheet_name='Meter_Data')
                
                # Metadata sheet
                metadata_df = pd.DataFrame([
                    {'Reading Type': rt, 'Unit': unit_dict.get(rt, 'Unknown')} 
                    for rt in reading_types
                ])
                metadata_df.to_excel(writer, index=False, sheet_name='Reading_Types')
                
                # Column info sheet
                column_info = pd.DataFrame({
                    'Column Name': melted_df.columns,
                    'Description': [
                        'Timestamp of the reading',
                        'Name of the meter/device',
                        *[f'{rt} reading ({unit_dict.get(rt, "Unknown unit")})' for rt in reading_types]
                    ]
                })
                column_info.to_excel(writer, index=False, sheet_name='Column_Info')
            
            output.seek(0)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"converted_meter_data_{timestamp}.xlsx"
            
            st.download_button(
                label="📥 Download Converted File as XLSX",
                data=output,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_xlsx"
            )
            
            # Also offer CSV download for smaller files
            csv_data = melted_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv_data,
                file_name=f"converted_meter_data_{timestamp}.csv",
                mime="text/csv",
                key="download_csv"
            )
            
        except Exception as e:
            st.error(f"Error generating download file: {str(e)}")

else:
    st.info("👆 Please upload an Excel or CSV file to get started.")
    
    # Usage instructions
    with st.expander("ℹ️ How to use this converter"):
        st.markdown("""
        **Supported File Formats:**
        - Excel files (.xlsx, .xls)
        - CSV files (.csv)
        
        **Expected Column Format:**
        - `Timestamp` column with format: "Day, Month DD, YYYY HH:MM"
        - Data columns with format: "MeterName - ReadingType (Unit)" 
          Example: "DAN3/ELEC/MDB/02-MDB_Energy Meter - Energy Reading (kWh)"
        
        **Conversion Process:**
        1. Extracts meter name (before first " - ")
        2. Extracts reading type (after " - " and before first "(" or "_")
        3. Extracts unit (within parentheses or after underscore)
        4. Combines readings by Timestamp and Meter
        5. Creates separate columns for each reading type
        
        **Output Format:**
        - Columns: Timestamp, Meter, ReadingType1, ReadingType2, ...
        - Each row represents unique (Timestamp, Meter) combination
        """)
    
    # Example file format
    with st.expander("📋 Example Input Format"):
        example_data = {
            'Timestamp': ['Thursday, March 27, 2025 15:45', 'Thursday, March 27, 2025 16:00'],
            'DAN3/ELEC/MDB/02-MDB_Energy Meter - Energy Reading (kWh)': [1250.5, 1251.2],
            'DAN3/ELEC/MDB/02-MDB_Energy Meter - Power Demand (kW)': [45.3, 46.1],
            'Building B - Main Meter - Energy Reading (kWh)': [890.3, 891.1],
            'Building B - Main Meter - Power Factor': [0.95, 0.96]
        }
        example_df = pd.DataFrame(example_data)
        st.write("Example input structure:")
        st.dataframe(example_df)
        
        st.write("**Would be converted to:**")
        example_output = {
            'Timestamp': ['27/03/2025 15:45', '27/03/2025 16:00', '27/03/2025 15:45', '27/03/2025 16:00'],
            'Meter': ['DAN3/ELEC/MDB/02-MDB_Energy Meter', 'DAN3/ELEC/MDB/02-MDB_Energy Meter', 
                     'Building B - Main Meter', 'Building B - Main Meter'],
            'Energy Reading': [1250.5, 1251.2, 890.3, 891.1],
            'Power Demand': [45.3, 46.1, None, None],
            'Power Factor': [None, None, 0.95, 0.96]
        }
        example_output_df = pd.DataFrame(example_output)
        st.dataframe(example_output_df)
