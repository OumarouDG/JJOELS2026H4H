# ======================================================================#
#             Collector.py  - Banana Model - John Jamison               #
# ======================================================================#
# Random Forest is an AI model that produces a decision tree capable of
# making predictions based on given input features. The random forest
# produces a batch of variating decision trees, and outputs the best 
# decision tree model of the batch. 

import pandas as pd
import os
import time
import serial
import sensorNormalize

# --- CONFIGURATION ---
SERIAL_PORT = 'COM3' 
BAUD_RATE = 115200  
DATA_FILE = 'banana_data.csv'

# ---========================--- Read Arduino ---========================---
def read_arduino_data(ser):
    # Bridge between arduino and python. This function reads in lines from 
    # the arduino and parses it into a float array that of 4 values:
    # Temperature, Humidity, Pressure, Gas Resistance 
    try:
        # Only try to read if there is actually data waiting
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            if line:
                data = [float(val) for val in line.split(',')]
                if len(data) == 4:
                    return data[3] # Gas Resistance
    except Exception as e:
        print(f"Read Error: {e}")
    return None


# ---========================--- Extract Gas Features ---========================---
def extract_gas_features(raw_gas_readings):
    series = pd.Series(raw_gas_readings)
    slope = 0
    if len(series) > 1:
        slope = (series.iloc[-1] - series.iloc[0]) / 2.0 
    return {
        'Gas_mean':  series.mean(),
        'Gas_min':   series.min(),
        'Gas_max':   series.max(),
        'Gas_std':   series.std(),
        'Gas_slope': slope
    }

# ---========================--- Read Arduino ---========================---
def collect_data(ser):
    # collect and records a continuous stream of data in intervals chosen by 
    # the user. This specific verison of collect_data() only records the gas
    # pressure. To capture important details, the function records the mean
    # min, max, and standard dev of the interval. 

    label = input("Enter label: ")
    
    print(f"\n[DEBUG] Starting collection. File: {os.path.abspath(DATA_FILE)}")
    interval = input("Enter time interval: ")

    #Normalize the sensor for accurate data
    ready = sensorNormalize.sensor_normalize(ser, read_arduino_data, extract_gas_features)

    #Main Loop
    if ready: 
        try:
            while True:
                gas_readings = []
                start_time = time.time()
                print(f"\n[DEBUG] Starting {interval} s window at {time.strftime('%H:%M:%S')}...")
                
                while time.time() - start_time < interval:
                    val = read_arduino_data(ser)
                    if val is not None:
                        gas_readings.append(val)
                    # Small sleep to prevent the CPU from red-lining
                    time.sleep(0.01)

                if gas_readings:
                    print(f"[DEBUG] Captured {len(gas_readings)} readings. Saving...")
                    series = pd.Series(gas_readings)
                    fingerprint = {
                        'Gas_mean': series.mean(),
                        'Gas_min':  series.min(),
                        'Gas_max':  series.max(),
                        'Gas_std':  series.std(),
                        'Label': label
                    }
                    
                    # Save frame to file
                    # This single line handles creating the file OR appending to it
                    df_row.to_csv(DATA_FILE, mode='a', header=not os.path.exists(DATA_FILE), index=False)
                    
                    print(f"--> SUCCESS: Fingerprint saved to {DATA_FILE}")
                else:
                    print("[DEBUG] WARNING: Window ended but NO gas data was received!")
                
        except KeyboardInterrupt:
            print("\n--- Collection Stopped ---")


# ---========================--- Main ---========================---
if __name__ == '__main__':

    try:
        print(f"[DEBUG] Attempting to open {SERIAL_PORT}...")
        arduino_serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # Bridge stabilization
        print("[DEBUG] Serial port open and ready.")
        collect_data(arduino_serial)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")