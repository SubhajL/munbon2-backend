/**
 * Water Level Sensor for Munbon Irrigation System
 * Device: ESP8266/ESP32
 * Manufacturer: RID-R
 * Sensor: Ultrasonic HC-SR04 or similar
 * 
 * This code sends water level data to AWS API Gateway
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <NTPClient.h>
#include <WiFiUdp.h>

// Configuration
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// AWS API Gateway endpoint (replace with your actual endpoint)
const char* apiEndpoint = "https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/dev";
const char* deviceToken = "munbon-ridr-water-level";  // RID-R water level token for Munbon
const char* deviceID = "ridr-water-01";  // Unique device ID

// Sensor pins
const int trigPin = D1;
const int echoPin = D2;
const int batteryPin = A0;

// Tank configuration
const float TANK_HEIGHT_CM = 200.0;  // Total tank height in cm
const float SENSOR_OFFSET_CM = 10.0; // Distance from sensor to max water level

// GPS coordinates (fixed for stationary sensors)
const float latitude = 13.7563;
const float longitude = 100.5018;

// NTP Client for timestamp
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org");

// MAC Address
String macAddress;

void setup() {
  Serial.begin(115200);
  
  // Initialize pins
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  
  // Connect to WiFi
  connectWiFi();
  
  // Get MAC address
  macAddress = WiFi.macAddress();
  macAddress.replace(":", "");
  
  // Initialize NTP
  timeClient.begin();
  timeClient.setTimeOffset(25200); // GMT+7 for Thailand
}

void loop() {
  // Update time
  timeClient.update();
  
  // Read sensor data
  float waterLevel = readWaterLevel();
  int voltage = readBatteryVoltage();
  int rssi = WiFi.RSSI();
  
  // Send data
  sendTelemetry(waterLevel, voltage, rssi);
  
  // Wait for next reading (1 minute)
  delay(60000);
}

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

float readWaterLevel() {
  // Send ultrasonic pulse
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  // Read echo time
  long duration = pulseIn(echoPin, HIGH);
  
  // Calculate distance in cm
  float distanceCm = duration * 0.034 / 2;
  
  // Calculate water level (distance from bottom of tank)
  float waterLevel = TANK_HEIGHT_CM - (distanceCm - SENSOR_OFFSET_CM);
  
  // Constrain to valid range
  waterLevel = constrain(waterLevel, 0, 30);
  
  Serial.print("Water level: ");
  Serial.print(waterLevel);
  Serial.println(" cm");
  
  return waterLevel;
}

int readBatteryVoltage() {
  // Read ADC value
  int adcValue = analogRead(batteryPin);
  
  // Convert to voltage (assuming voltage divider)
  // Adjust these values based on your voltage divider
  float voltage = (adcValue / 1024.0) * 5.0 * 2; // Assuming 2:1 voltage divider
  
  // Convert to expected format (multiply by 100)
  int voltageInt = (int)(voltage * 100);
  
  return voltageInt;
}

void sendTelemetry(float waterLevel, int voltage, int rssi) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, reconnecting...");
    connectWiFi();
    return;
  }
  
  HTTPClient http;
  WiFiClient client;
  
  // Construct URL with token
  String url = String(apiEndpoint) + "/api/v1/" + deviceToken + "/telemetry";
  
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  
  // Create JSON payload
  StaticJsonDocument<300> doc;
  doc["deviceID"] = deviceID;
  doc["macAddress"] = macAddress;
  doc["latitude"] = latitude;
  doc["longitude"] = longitude;
  doc["RSSI"] = rssi;
  doc["voltage"] = voltage;
  doc["level"] = (int)waterLevel;
  doc["timestamp"] = timeClient.getEpochTime() * 1000L; // Convert to milliseconds
  
  String payload;
  serializeJson(doc, payload);
  
  Serial.print("Sending data: ");
  Serial.println(payload);
  
  // Send POST request
  int httpCode = http.POST(payload);
  
  if (httpCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpCode);
    
    if (httpCode == HTTP_CODE_OK) {
      String response = http.getString();
      Serial.println("Response: " + response);
    }
  } else {
    Serial.print("HTTP POST failed, error: ");
    Serial.println(http.errorToString(httpCode));
  }
  
  http.end();
}

// Optional: OTA update support
void checkForUpdates() {
  // Implement OTA update check
  // This allows remote firmware updates
}