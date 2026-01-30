#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <DHT.h>

// --- USER CONFIGURATION ---
const char* ssid = "Bajnok 2.4";
const char* password = "#21Szuret21"; 
const char* pi_url = "http://192.168.0.150:8000/ingest"; 

// --- HARDWARE CONFIGURATION ---
#define DHTPIN 4       // DHT11 Data pin connected to GPIO 4
#define DHTTYPE DHT11  // Sensor type
DHT dht(DHTPIN, DHTTYPE);

// On many ESP32 boards, the built-in LED is GPIO 2.
// If using an external LED, change this number (e.g., 12, 13).
const int ledPin = 2; 

WebServer server(80);

void setup() {
  Serial.begin(115200);
  
  // Initialize Hardware
  pinMode(ledPin, OUTPUT);
  dht.begin();

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // --- ACTUATOR ENDPOINT ---
  // Listens for http://<ESP_IP>/set?val=1 (ON) or val=0 (OFF)
  server.on("/set", []() {
    if (server.hasArg("val")) {
      String valStr = server.arg("val");
      int state = 0;
      
      // Handle various inputs: "ON", "1", "true"
      if (valStr.equalsIgnoreCase("ON") || valStr == "1") state = 1;
      else if (valStr.equalsIgnoreCase("OFF") || valStr == "0") state = 0;
      
      digitalWrite(ledPin, state);
      server.send(200, "text/plain", state ? "ON" : "OFF");
      Serial.printf("Actuator Command: LED %s\n", state ? "ON" : "OFF");
    } else {
      server.send(400, "text/plain", "Missing 'val' argument");
    }
  });
  
  server.begin();
  Serial.println("HTTP Server started");
}

void loop() {
  // 1. Handle incoming HTTP requests (Actuator)
  server.handleClient(); 

  // 2. Send Sensor Data (Every 2 seconds)
  static unsigned long lastTime = 0;
  if (millis() - lastTime > 2000) {
    lastTime = millis();

    float t = dht.readTemperature();
    // Check if read failed (returns NaN)
    if (isnan(t)) {
      Serial.println("Failed to read from DHT sensor!");
      return; 
    }

    if(WiFi.status() == WL_CONNECTED){
      HTTPClient http;
      http.begin(pi_url);
      http.addHeader("Content-Type", "application/json");
      
      // Payload format: {"sensor_id": "dht11_temp", "value": 24.5}
      String payload = "{\"sensor_id\": \"dht11_temp\", \"value\": " + String(t) + "}";
      
      int httpResponseCode = http.POST(payload);
      
      if (httpResponseCode > 0) {
        Serial.printf("Sent: %.1fC (Code: %d)\n", t, httpResponseCode);
      } else {
        Serial.printf("Error sending: %s\n", http.errorToString(httpResponseCode).c_str());
      }
      http.end();
    }
  }
}