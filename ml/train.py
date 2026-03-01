# ======================================================================#
#                    Train Model.py  -  John Jamison                    #
# ======================================================================#
# This program outputs a random forest decition tree AI model using the 
# inputs from the sensor model. The model, the Random Forest, is an AI 
# model that produces a decision tree capable of making predictions based
# on given input features. The random forest produces a batch of variating 
# decision trees, and outputs the best decision tree model of the batch. 


import serial
import time
import pandas as pd
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import warnings
import collector

# Suppress warnings for cleaner console output
warnings.filterwarnings('ignore')

# --- CONFIGURATION ---
SERIAL_PORT =   # Change to your Arduino's port (e.g., '/dev/ttyACM0' on Mac/Linux)
BAUD_RATE =  115200  # Matches your Arduino's Serial.begin()
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


# ---========================--- Train Model ---========================---
def train_model():
    # Trains an AI model using a Random Forest Classifier model,
    # an enseble learning method, a method that combines multiple 
    # decision trees.
    

    if not os.path.exists(DATA_FILE):
        print("No data found! Please collect data first.\n")
        return
        
    print("Loading data and training model...")
    df = pd.read_csv(DATA_FILE)
    
    X = df[['Temperature', 'Humidity', 'Pressure', 'GasResistance']]
    y = df['Label']
    
    # Split data to test the accuracy of the model. Here we've set the training
    #   size to be 80% of the collected data, and 20% be fore testing. random_state
    #   sets the seed number that shuffles the data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    #Create a Random forest with 100 empty decision trees
    model = RandomForestClassifier(n_estimators=100, random_state=42)

    #This line does the heavy lifting, nad trains the model
    model.fit(X_train, y_train)
    

    #==========   Test the data   ==========
    predictions = model.predict(X_test)
    acc = accuracy_score(y_test, predictions)
    
    # Save the trained model to disk
    joblib.dump(model, MODEL_FILE)
    print(f"Model trained successfully! Test Accuracy: {acc * 100:.2f}%")
    print(f"Model saved to {MODEL_FILE}\n")


# ---========================--- Live Predict ---========================---
def live_predict(ser):
    # runs the actual model produced by the train_model() function by
    # feeding live data from the arduino to the model.

    # Throw error if file not exist
    if not os.path.exists(MODEL_FILE):
        print("No model found! Please train the model first.\n")
        return
        
    print("Loading model for live prediction...")
    model = joblib.load(MODEL_FILE)
    print("Listening to Arduino...")
    
    # While data is still being read in...
    try:
        while True:
            data = read_arduino_data(ser)
            if data:
                #save it as a data frame and feed it to the model
                features = pd.DataFrame([data], columns=['Temperature', 'Humidity', 'Pressure', 'GasResistance'])
                prediction = model.predict(features)[0]
                print(f"Live Reading: {data} -> Detected Strain: **{prediction}**")
    except KeyboardInterrupt:
        print("\nStopped live prediction.\n")


# ---========================--- Main ---========================---
def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2) # Give the serial connection a moment to initialize
    except Exception as e:
        print(f"Could not open serial port {SERIAL_PORT}. Check your connection and port name.")
        return

    while True:
        print("=== BME688 AI Bacteria Detector ===")
        print("1. Train AI Model")
        print("2. Run Live Predictions")
        print("3. Exit")
        choice = input("Select an option (1-3): ")
        
        if choice == '1':
            train_model()
        elif choice == '2':
            live_predict(ser)
        elif choice == '3':
            print("Exiting...")
            break
        else:
            print("Invalid choice.\n")

if __name__ == '__main__':
    main()
