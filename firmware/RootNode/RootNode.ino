#include <Arduino.h>
#include <painlessMesh.h>

// Mesh settings
#define MESH_PREFIX   "ENG402_MESH"
#define MESH_PASSWORD "YOUR_MESH_PASSWORD"
#define MESH_PORT     5555

Scheduler userScheduler;
painlessMesh mesh;

void sendRootStatus();
void receivedCallback(uint32_t from, String &msg);
void newConnectionCallback(uint32_t nodeId);
void changedConnectionCallback();
void nodeTimeAdjustedCallback(int32_t offset);

Task taskRootStatus(
  30000,
  TASK_FOREVER,
  &sendRootStatus
);

void receivedCallback(uint32_t from, String &msg) {
  Serial.print("DATA:");
  Serial.println(msg);
}

void newConnectionCallback(uint32_t nodeId) {
  Serial.print("STATUS:{");
  Serial.print("\"event\":\"new_connection\",");
  Serial.print("\"node_id\":");
  Serial.print(nodeId);
  Serial.print(",");
  Serial.print("\"connected_nodes\":");
  Serial.print(mesh.getNodeList().size());
  Serial.println("}");
}

void changedConnectionCallback() {
  Serial.print("STATUS:{");
  Serial.print("\"event\":\"connections_changed\",");
  Serial.print("\"connected_nodes\":");
  Serial.print(mesh.getNodeList().size());
  Serial.print(",");
  Serial.print("\"root_node_id\":");
  Serial.print(mesh.getNodeId());
  Serial.println("}");
}

void nodeTimeAdjustedCallback(int32_t offset) {
  Serial.print("STATUS:{");
  Serial.print("\"event\":\"time_adjusted\",");
  Serial.print("\"offset\":");
  Serial.print(offset);
  Serial.println("}");
}

void sendRootStatus() {
  String status = "STATUS:{";
  status += "\"event\":\"root_status\",";
  status += "\"root_node_id\":";
  status += String(mesh.getNodeId());
  status += ",";
  status += "\"connected_nodes\":";
  status += String(mesh.getNodeList().size());
  status += ",";
  status += "\"mesh_time_us\":";
  status += String(mesh.getNodeTime());
  status += ",";
  status += "\"uptime_ms\":";
  status += String(millis());
  status += "}";
  Serial.println(status);
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println();
  Serial.println("STATUS:{\"event\":\"root_starting\"}");

  mesh.setDebugMsgTypes(ERROR | STARTUP);
  mesh.init(
    MESH_PREFIX,
    MESH_PASSWORD,
    &userScheduler,
    MESH_PORT
  );

  mesh.setRoot(true);
  mesh.setContainsRoot(true);
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionCallback);
  mesh.onNodeTimeAdjusted(&nodeTimeAdjustedCallback);
  userScheduler.addTask(taskRootStatus);
  taskRootStatus.enable();

  Serial.print("STATUS:{");
  Serial.print("\"event\":\"root_started\",");
  Serial.print("\"root_node_id\":");
  Serial.print(mesh.getNodeId());
  Serial.println("}");
}

void loop() {
  mesh.update();
}
