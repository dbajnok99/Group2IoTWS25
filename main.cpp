#include <WiFi.h>
#include <ArduinoMqttClient.h>

void onMqttMessage(int messageSize);

const char* ssid = "Josef";
const char* password = "highground";

const char broker[] = "172.20.10.4";
int        port     = 1883;

const char topic_pub_living_temp[] = "myhome/livingroom/temperature";
const char topic_pub_bed_temp[]    = "myhome/bedroom/temperature";

const char topic_sub_living_color[] = "myhome/livingroom/light/colorLED1";
const char topic_sub_living_white[] = "myhome/livingroom/light/whiteLED1";
const char topic_sub_bed_light[]    = "myhome/bedroom/light/bedside";

// ------------------- GLOBALS -------------------
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);


const long interval = 10000; // 10 seconds
unsigned long previousMillis = 0;



void onMqttMessage(int messageSize) {
  
  String topic = mqttClient.messageTopic();
  String payload = "";

  // Read the message content
  while (mqttClient.available()) {
    payload += (char)mqttClient.read();
  }

  Serial.println("\n--- INCOMING MESSAGE (QoS 1) ---");
  Serial.print("Topic: ");
  Serial.println(topic);
  Serial.print("Payload: ");
  Serial.println(payload);

  // Fake the LED Hardware Response
  if (topic == topic_sub_living_color) {
    Serial.print(">>> ACTUATOR: Living Room Color LED changed to: ");
    Serial.println(payload);
  } 
  else if (topic == topic_sub_living_white) {
    Serial.print(">>> ACTUATOR: Living Room White LED changed to: ");
    Serial.println(payload);
  }
  else if (topic == topic_sub_bed_light) {
    Serial.print(">>> ACTUATOR: Bedroom Bedside Light changed to: ");
    Serial.println(payload);
  }
  Serial.println("--------------------------------\n");
}
// ------------------- SETUP -------------------
void setup() {
  Serial.begin(115200);
  while (!Serial);

  // 1. Connect to Wi-Fi
  Serial.print("Attempting to connect to WPA SSID: ");
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);

  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
  
  delay(500);
  
  Serial.print(".");
  
  }

  Serial.println("You're connected to the network");
  Serial.println();
  // Connect to MQTT Broker
  Serial.print("Attempting to connect to MQTT broker: ");
  Serial.println(broker);
  mqttClient.setUsernamePassword("myuser", "mypassword");
  if (!mqttClient.connect(broker, port)) {
    Serial.print("MQTT connection failed! Error code = ");
    Serial.println(mqttClient.connectError());
    while (1); // Stop here if we can't connect
  }

  Serial.println("You're connected to the MQTT broker!");
  Serial.println();
  mqttClient.onMessage(onMqttMessage);

  // Subscribe with QoS 1
  Serial.print("Subscribing to topics with QoS 1... ");
  
  mqttClient.subscribe(topic_sub_living_color, 1);
  mqttClient.subscribe(topic_sub_living_white, 1);
  mqttClient.subscribe(topic_sub_bed_light, 1);

  Serial.println("Done.");
  Serial.println();

}



// ------------------- MAIN LOOP -------------------
void loop() {
  mqttClient.poll();

  // Periodic Publishing (Temperature)
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    float tempLiving = 20.0 + (random(100) / 10.0);
    float tempBed    = 18.0 + (random(100) / 10.0);

    // Publish Living Room Temp (QoS 1)
    mqttClient.beginMessage(topic_pub_living_temp, false, 1);
    mqttClient.print(tempLiving);
    mqttClient.endMessage();

    // Publish Bedroom Temp (QoS 1)
    mqttClient.beginMessage(topic_pub_bed_temp, false, 1);
    mqttClient.print(tempBed);
    mqttClient.endMessage();

    Serial.print("Published Temps (QoS 1): ");
    Serial.print(tempLiving);
    Serial.print(" / ");
    Serial.println(tempBed);
  }
}