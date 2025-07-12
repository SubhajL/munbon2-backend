/**
 * Moisture Sensor Gateway for Munbon Irrigation System
 * Device: ESP8266/ESP32 as Gateway
 * Manufacturer: M2M
 * Sensors: Multiple moisture sensors connected via RS485 or analog
 * 
 * This gateway collects data from multiple M2M moisture sensors
 * and sends to AWS API Gateway
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <NTPClient.h>
#include <WiFiUdp.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// Configuration
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// AWS API Gateway endpoint
const char* apiEndpoint = "https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/dev";
const char* deviceToken = "munbon-m2m-moisture";  // M2M moisture token for Munbon
const String gatewayID = "m2m-gw-001";

// GPS coordinates of gateway
const float latitude = 13.12345;
const float longitude = 100.54621;

// Sensor configuration
const int NUM_SENSORS = 2;
const int moisturePins[NUM_SENSORS] = {A0, A1}; // Analog pins for moisture
const int tempDataPin = D4; // OneWire for temperature sensors

// Flood detection pins
const int floodPins[NUM_SENSORS] = {D5, D6};

// Battery monitoring
const int batteryPin = A2;

// OneWire setup for temperature
OneWire oneWire(tempDataPin);
DallasTemperature tempSensors(&oneWire);

// NTP Client
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org");

void setup() {
  Serial.begin(115200);
  
  // Initialize pins
  for (int i = 0; i < NUM_SENSORS; i++) {
    pinMode(floodPins[i], INPUT_PULLUP);
  }
  
  // Initialize temperature sensors
  tempSensors.begin();
  
  // Connect to WiFi
  connectWiFi();
  
  // Initialize NTP
  timeClient.begin();
  timeClient.setTimeOffset(25200); // GMT+7 for Thailand
}

void loop() {
  // Update time
  timeClient.update();
  
  // Collect sensor data
  StaticJsonDocument<1024> doc;
  
  // Gateway information
  doc["gateway_id"] = gatewayID;
  doc["msg_type"] = "interval";
  doc["date"] = getCurrentDate();
  doc["time"] = getCurrentTime();
  doc["latitude"] = String(latitude, 5);
  doc["longitude"] = String(longitude, 5);
  doc["gw_batt"] = String(readBatteryVoltage());
  
  // Create sensor array
  JsonArray sensorArray = doc.createNestedArray("sensor");
  
  // Read each sensor
  for (int i = 0; i < NUM_SENSORS; i++) {
    JsonObject sensor = sensorArray.createNestedObject();
    
    sensor["sensor_id"] = String(i + 1, DEC).padLeft(5, '0');
    sensor["flood"] = digitalRead(floodPins[i]) == LOW ? "yes" : "no";
    
    // Read moisture at two depths
    MoistureData moisture = readMoisture(i);
    sensor["humid_hi"] = String(moisture.surfaceMoisture);
    sensor["humid_low"] = String(moisture.deepMoisture);
    
    // Read temperatures
    TemperatureData temps = readTemperatures(i);
    sensor["amb_humid"] = String(temps.ambientHumidity);
    sensor["amb_temp"] = String(temps.ambientTemp, 2);
    sensor["temp_hi"] = String(temps.surfaceTemp, 2);
    sensor["temp_low"] = String(temps.deepTemp, 2);
    
    // Sensor battery (if separate from gateway)
    sensor["sensor_batt"] = String(400); // Example fixed value
  }
  
  // Send data
  sendTelemetry(doc);
  
  // Wait for next reading (5 minutes)
  delay(300000);
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

struct MoistureData {
  int surfaceMoisture;
  int deepMoisture;
};

MoistureData readMoisture(int sensorIndex) {
  MoistureData data;
  
  // Read analog moisture sensor
  int rawValue = analogRead(moisturePins[sensorIndex]);
  
  // Convert to percentage (calibrate these values for your sensors)
  // Dry = 1023 (0%), Wet = 0 (100%)
  int moisturePercent = map(rawValue, 1023, 0, 0, 100);
  moisturePercent = constrain(moisturePercent, 0, 100);
  
  // Simulate two depths (in real implementation, use two sensors)
  data.surfaceMoisture = moisturePercent;
  data.deepMoisture = moisturePercent - random(5, 15); // Deeper soil typically retains more moisture
  data.deepMoisture = constrain(data.deepMoisture, 0, 100);
  
  return data;
}

struct TemperatureData {
  float ambientTemp;
  float ambientHumidity;
  float surfaceTemp;
  float deepTemp;
};

TemperatureData readTemperatures(int sensorIndex) {
  TemperatureData data;
  
  // Request temperatures
  tempSensors.requestTemperatures();
  
  // Read temperature sensors (assuming 2 sensors per moisture sensor)
  int baseSensorIndex = sensorIndex * 2;
  data.surfaceTemp = tempSensors.getTempCByIndex(baseSensorIndex);
  data.deepTemp = tempSensors.getTempCByIndex(baseSensorIndex + 1);
  
  // Simulate ambient conditions (in real implementation, use DHT22 or similar)
  data.ambientTemp = data.surfaceTemp + random(-5, 5);
  data.ambientHumidity = 60 + random(-10, 10);
  
  // Validate readings
  if (data.surfaceTemp == DEVICE_DISCONNECTED_C) {
    data.surfaceTemp = 25.0; // Default value
  }
  if (data.deepTemp == DEVICE_DISCONNECTED_C) {
    data.deepTemp = 24.0; // Default value
  }
  
  return data;
}

int readBatteryVoltage() {
  // Read ADC value
  int adcValue = analogRead(batteryPin);
  
  // Convert to voltage (assuming voltage divider)
  float voltage = (adcValue / 1024.0) * 5.0 * 2; // 2:1 voltage divider
  
  // Return in expected format (multiply by 100)
  return (int)(voltage * 100);
}

String getCurrentDate() {
  time_t epochTime = timeClient.getEpochTime();
  struct tm *ptm = gmtime(&epochTime);
  
  char dateBuffer[11];
  sprintf(dateBuffer, "%04d/%02d/%02d", 
    ptm->tm_year + 1900,
    ptm->tm_mon + 1,
    ptm->tm_mday
  );
  
  return String(dateBuffer);
}

String getCurrentTime() {
  // Return time in UTC (service will handle timezone)
  return timeClient.getFormattedTime();
}

void sendTelemetry(StaticJsonDocument<1024>& doc) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, reconnecting...");
    connectWiFi();
    return;
  }
  
  HTTPClient http;
  WiFiClient client;
  
  // Construct URL
  String url = String(apiEndpoint) + "/api/v1/" + deviceToken + "/telemetry";
  
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  
  // Serialize JSON
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

// Get configuration from server
void getConfiguration() {
  HTTPClient http;
  WiFiClient client;
  
  String url = String(apiEndpoint) + "/api/v1/" + deviceToken + "/attributes?sharedKeys=interval";
  
  http.begin(client, url);
  
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String response = http.getString();
    Serial.println("Configuration: " + response);
    
    // Parse and apply configuration
    StaticJsonDocument<200> config;
    deserializeJson(config, response);
    
    // Example: Update reading interval
    int interval = config["moisture"] | 300; // Default 300 seconds
    Serial.print("Update interval: ");
    Serial.println(interval);
  }
  
  http.end();
}