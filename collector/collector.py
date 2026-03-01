# ======================================================================#
#                    Collector.py  -  John Jamison                    #
# ======================================================================#
# Random Forest is an AI model that produces a decision tree capable of
# making predictions based on given input features. The random forest
# produces a batch of variating decision trees, and outputs the best 
# decision tree model of the batch. 

import pandas as pd
import os
from collections import deque

# --- CONFIGURATION ---
SERIAL_PORT =   # Change to your Arduino's port (e.g., '/dev/ttyACM0' on Mac/Linux)
BAUD_RATE =    # Matches your Arduino's Serial.begin()
DATA_FILE = 'data.csv'
MODEL_FILE = 'bacteria_model.pkl'

# ---========================--- Read Arduino ---========================---
def read_arduino_data(ser):
    # Bridge between arduino and python. This function reads in lines from 
    # the arduino and parses it into a float array that of 4 values:
    # Temperature, Humidity, Pressure, Gas Resistance 

    try:
        # Receive and translate bytes from Arduino
        line = ser.readline().decode('utf-8').strip()

        # If input is detected...
        if line:
            # Expecting Arduino to print: Temperature,Humidity,Pressure,GasResistance
            data = [float(val) for val in line.split(',')]
            if len(data) == 4:
                return data
    except Exception:
        pass
    return None

# ---========================--- Collect Data ---========================---
def collect_data(ser):
    # Records live data and tags it with your chosen label.
    strain_name = input("Enter the name of the bacteria strain: ")
    #samples_to_collect = int(input("How many samples should we collect?: "))
    buffer = deque()

    try:
        while True:
            data = read_arduino_data(ser)
            if data:
                current_time = time.time()
                # Add new reading with a timestamp
                buffer.append((current_time, data))
                
                # Purge any readings older than 10 seconds
                while buffer and buffer[0][0] < current_time - 10:
                    buffer.popleft()
                    
    except KeyboardInterrupt:
        print(f"\nCaptured {len(buffer)} readings from the 10-second window.")
        
        # Extract just the data arrays and append the label
        data_list = []
        for _, row in buffer:
            row_copy = list(row)
            row_copy.append(strain_name)
            data_list.append(row_copy)
            
        df = pd.DataFrame(data_list, columns=['Temperature', 'Humidity', 'Pressure', 'GasResistance', 'Label'])
        
        if os.path.exists(DATA_FILE):
            df.to_csv(DATA_FILE, mode='a', header=False, index=False)
        else:
            df.to_csv(DATA_FILE, index=False)
            
        print(f"Data saved to {DATA_FILE}!\n")
