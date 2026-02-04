import asyncio
import os
import sqlite3
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask, request
from bleak import BleakClient, BleakScanner

# --- CONFIGURATION ---
THINGY_NAME = "Thingy_Sensor"  # Must match your Firmware Name
DB_NAME = "sensor_data.db"
SERVER_PORT = 8000            # Port this Python script listens on

# Thingy:53 UUIDs (Standard)
UUID_TEMP  = "00002a6e-0000-1000-8000-00805f9b34fb"
UUID_HUMID = "00002a6f-0000-1000-8000-00805f9b34fb"

# Global State (Just to track IP for manual control if needed)
SYSTEM_STATE = {
    "esp32_ip": None 
}

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS readings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  device TEXT,
                  sensor TEXT,
                  value REAL,
                  timestamp DATETIME)''')
    conn.commit()
    conn.close()

def save_reading(device, sensor, value):
    try:
        conn = sqlite3.connect(DB_NAME)
        now = datetime.now()
        conn.execute("INSERT INTO readings (device, sensor, value, timestamp) VALUES (?,?,?,?)", 
                     (device, sensor, value, now))
        # Ring Buffer: Keep last 5 mins
        conn.execute("DELETE FROM readings WHERE timestamp < ?", (now - timedelta(minutes=5),))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

# --- OPTIONAL CONTROL FUNCTION ---
# This is NOT called automatically. It is here only because you said
# the LED is actuated over HTTP, so you have the capability if needed.
def set_esp32_led(turn_on):
    if not SYSTEM_STATE["esp32_ip"]:
        print("ESP32 IP unknown yet.")
        return

    val = "1" if turn_on else "0"
    url = f"http://{SYSTEM_STATE['esp32_ip']}/set?val={val}"
    
    try:
        requests.get(url, timeout=1)
        print(f"👉 Manual Command Sent: LED {'ON' if turn_on else 'OFF'}")
    except Exception as e:
        print(f"HTTP Error: {e}")

# --- HTTP SERVER (Receives ESP32 Data) ---
app = Flask(__name__)

@app.route('/ingest', methods=['POST'])
def ingest_esp32():
    try:
        # 1. Capture ESP32 IP (for potential manual control)
        if SYSTEM_STATE["esp32_ip"] != request.remote_addr:
            SYSTEM_STATE["esp32_ip"] = request.remote_addr
            with open("esp32.conf", "w") as f:
                f.write(request.remote_addr)
            print(f"ESP32 Connected from IP: {request.remote_addr}")

        # 2. Parse Data
        data = request.json
        sensor = data.get('sensor_id', 'ESP_Temp')
        val = float(data.get('value', 0.0))

        # 3. Save Data ONLY (No Triggers)
        save_reading("ESP32", sensor, val)
        print(f"[ESP32] {sensor}: {val:.1f}")
        
        return "OK", 200
    except Exception as e:
        return str(e), 400

def run_server():
    # Listens on 0.0.0.0 so ESP32 can connect
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, use_reloader=False)

# --- BLE CLIENT (Receives Thingy Data) ---
async def run_ble():
    print(f"Scanning for '{THINGY_NAME}'...")
    device = await BleakScanner.find_device_by_name(THINGY_NAME)
    
    if not device:
        print(f"'{THINGY_NAME}' not found. Is it advertising?")
        return

    async with BleakClient(device) as client:
        print(f"Connected to Thingy!")

        def callback(sender, data):
            # Convert Little Endian data
            val = int.from_bytes(data, 'little', signed=True) / 100.0
            
            if sender.uuid == UUID_TEMP:
                print(f"⚡ [Thingy] Temp: {val:.2f}°C")
                save_reading("Thingy", "Temperature", val)
                
            elif sender.uuid == UUID_HUMID:
                print(f"💧 [Thingy] Humid: {val:.2f}%")
                save_reading("Thingy", "Humidity", val)

        await client.start_notify(UUID_TEMP, callback)
        await client.start_notify(UUID_HUMID, callback)
        
        # Keep running
        while True:
            await asyncio.sleep(1)

# --- MAIN ---
if __name__ == "__main__":
    init_db()
    if os.path.exists("esp32.conf"):
        try:
            with open("esp32.conf", "r") as f:
                saved_ip = f.read().strip()
                if saved_ip:
                    SYSTEM_STATE["esp32_ip"] = saved_ip
                    print(f"✅ Restored ESP32 IP from config: {saved_ip}")
        except Exception as e:
            print(f"Could not read config file: {e}")
    # 1. Start HTTP Server for ESP32 (Background Thread)
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    print(f"Server listening on Port {SERVER_PORT}")

    # 2. Start BLE Client for Thingy (Main Thread)
    try:
        asyncio.run(run_ble())
    except KeyboardInterrupt:
        print("Stopping...")
