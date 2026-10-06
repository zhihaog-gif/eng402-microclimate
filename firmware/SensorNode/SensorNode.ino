#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <painlessMesh.h>

// Node label
#define SENSOR_NAME "Sensor_A"

// Mesh settings
#define MESH_PREFIX   "ENG402_MESH"
#define MESH_PASSWORD "YOUR_MESH_PASSWORD"
#define MESH_PORT     5555

// I2C pins
#define I2C_SDA 21
#define I2C_SCL 22

#define SEND_INTERVAL 5000
#define BMP_RETRY_INTERVAL 10000

Scheduler userScheduler;
painlessMesh mesh;
Adafruit_BMP280 bmp;

bool bmpAvailable = false;
uint8_t bmpAddress = 0;
unsigned long lastBmpRetry = 0;
unsigned long messageSequence = 0;

void sendSensorData();
void receivedCallback(uint32_t from, String &msg);
void newConnectionCallback(uint32_t nodeId);
void changedConnectionCallback();
void nodeTimeAdjustedCallback(int32_t offset);
bool initialiseBMP280();

Task taskSendSensorData(
  SEND_INTERVAL,
  TASK_FOREVER,
  &sendSensorData
);

bool initialiseBMP280() {
  Serial.println("[BMP280] Searching for sensor...");

  if (bmp.begin(0x76)) {
    bmpAddress = 0x76;
    bmpAvailable = true;
    Serial.println("[BMP280] Sensor found at address 0x76");
  }
  else if (bmp.begin(0x77)) {
    bmpAddress = 0x77;
    bmpAvailable = true;
    Serial.println("[BMP280] Sensor found at address 0x77");
  }
  else {
    bmpAddress = 0;
    bmpAvailable = false;
    Serial.println("[BMP280] Sensor not found.");
    Serial.println("[BMP280] Mesh will continue running.");
    Serial.println("[BMP280] The program will try again automatically.");
    return false;
  }

  bmp.setSampling(
    Adafruit_BMP280::MODE_NORMAL,
    Adafruit_BMP280::SAMPLING_X2,
    Adafruit_BMP280::SAMPLING_X16,
    Adafruit_BMP280::FILTER_X16,
    Adafruit_BMP280::STANDBY_MS_500
  );

  return true;
}

void sendSensorData() {
  if (!bmpAvailable) {
    if (millis() - lastBmpRetry >= BMP_RETRY_INTERVAL) {
      lastBmpRetry = millis();
      initialiseBMP280();
    }
  }

  messageSequence++;

  String message = "{";
  message += "\"type\":\"sensor_data\",";
  message += "\"sensor_name\":\"";
  message += SENSOR_NAME;
  message += "\",";
  message += "\"node_id\":";
  message += String(mesh.getNodeId());
  message += ",";
  message += "\"sequence\":";
  message += String(messageSequence);
  message += ",";
  message += "\"mesh_time_us\":";
  message += String(mesh.getNodeTime());
  message += ",";
  message += "\"uptime_ms\":";
  message += String(millis());
  message += ",";
  message += "\"bmp280_connected\":";
  message += bmpAvailable ? "true" : "false";

  if (bmpAvailable) {
    float temperature = bmp.readTemperature();
    float pressurePa = bmp.readPressure();
    float pressureHpa = pressurePa / 100.0F;

    if (isnan(temperature) || isnan(pressureHpa)) {
      Serial.println("[BMP280] Invalid sensor reading.");
      bmpAvailable = false;
      message += ",";
      message += "\"temperature_c\":null,";
      message += "\"pressure_hpa\":null,";
      message += "\"error\":\"invalid_sensor_reading\"";
    }
    else {
      message += ",";
      message += "\"temperature_c\":";
      message += String(temperature, 2);
      message += ",";
      message += "\"pressure_hpa\":";
      message += String(pressureHpa, 2);
      message += ",";
      message += "\"bmp280_address\":\"0x";
      message += String(bmpAddress, HEX);
      message += "\"";
    }
  }
  else {
    message += ",";
    message += "\"temperature_c\":null,";
    message += "\"pressure_hpa\":null,";
    message += "\"error\":\"bmp280_not_connected\"";
  }

  message += "}";

  bool sentSuccessfully = mesh.sendBroadcast(message);

  Serial.println();
  Serial.println("========== SENSOR TRANSMISSION ==========");
  Serial.print("Sensor: ");
  Serial.println(SENSOR_NAME);
  Serial.print("ESP32 Node ID: ");
  Serial.println(mesh.getNodeId());
  Serial.print("Connected mesh nodes: ");
  Serial.println(mesh.getNodeList().size());
  Serial.print("Message: ");
  Serial.println(message);
  Serial.print("Broadcast result: ");
  Serial.println(sentSuccessfully ? "SUCCESS" : "FAILED");
  Serial.println("=========================================");
}

void receivedCallback(uint32_t from, String &msg) {
  Serial.println();
  Serial.println("[Mesh] Message received by sensor node");
  Serial.print("[Mesh] From node: ");
  Serial.println(from);
  Serial.print("[Mesh] Message: ");
  Serial.println(msg);
}

void newConnectionCallback(uint32_t nodeId) {
  Serial.println();
  Serial.print("[Mesh] New connection: ");
  Serial.println(nodeId);
}

void changedConnectionCallback() {
  Serial.println();
  Serial.println("[Mesh] Connection topology changed.");
  Serial.print("[Mesh] Current connected nodes: ");
  Serial.println(mesh.getNodeList().size());
  Serial.print("[Mesh] Node list: ");

  SimpleList<uint32_t> nodes = mesh.getNodeList();
  for (auto node : nodes) {
    Serial.print(node);
    Serial.print(" ");
  }

  Serial.println();
}

void nodeTimeAdjustedCallback(int32_t offset) {
  Serial.print("[Mesh] Time adjusted. Offset: ");
  Serial.println(offset);
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);

  Serial.println();
  Serial.println("=========================================");
  Serial.println("ENG402 SENSOR NODE STARTING");
  Serial.print("Sensor name: ");
  Serial.println(SENSOR_NAME);
  Serial.println("=========================================");

  Wire.begin(I2C_SDA, I2C_SCL);
  initialiseBMP280();
  mesh.setDebugMsgTypes(ERROR | STARTUP);
  mesh.init(
    MESH_PREFIX,
    MESH_PASSWORD,
    &userScheduler,
    MESH_PORT
  );

  mesh.setContainsRoot(true);
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionCallback);
  mesh.onNodeTimeAdjusted(&nodeTimeAdjustedCallback);
  userScheduler.addTask(taskSendSensorData);
  taskSendSensorData.enable();

  Serial.print("[Mesh] Sensor node started. Node ID: ");
  Serial.println(mesh.getNodeId());
}

void loop() {
  mesh.update();
}
