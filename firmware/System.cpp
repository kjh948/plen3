/*
        Copyright (c) 2015,
        - Kazuyuki TAKASE - https://github.com/Guvalif
        - PLEN Project Company Inc. - https://plen.jp

        This software is released under the MIT License.
        (See also : http://opensource.org/licenses/mit-license.php)
*/
#include "System.h"
#include "Arduino.h"
#include "ExternalFs.h"
#include "JointController.h"
#include "MotionController.h"
#include "Pin.h"
#include "Profiler.h"
#include <ESP8266HTTPUpdateServer.h>
#include <ESP8266WebServer.h>
#include <ESP8266WiFi.h>
#include <ESP8266mDNS.h>
#include <Ticker.h>
#include <WiFiClient.h>
#include <WiFiUDP.h>


extern PLEN2::JointController joint_ctrl;
extern PLEN2::MotionController motion_ctrl;

#define PLEN2_SYSTEM_SERIAL Serial

#define CONNECT_TIMEOUT_CNT 100

IPAddress broadcastIp(255, 255, 255, 255);
#define BROADCAST_PORT 6000
WiFiUDP udp;

ESP8266WebServer httpServer(80);
ESP8266HTTPUpdateServer httpUpdater;
static bool servers_started = false;

WiFiServer tcp_server(23);
WiFiClient serverClient;
Ticker smartconfig_tricker;

String robot_name = "ViVi-" + String(ESP.getChipId(), HEX);
const char *wifi_psd = "12345678xyz";

volatile bool update_cfg;

extern File fp_motion;
extern File fp_config;
extern File fp_syscfg;
File fsUploadFile;
// 启动ao模式
void PLEN2::System::StartAp() {
#if CLOCK_WISE
  String ap_name = "ViVi-M-" + String(ESP.getChipId(), HEX);
#else
  String ap_name = "ViVi-N-" + String(ESP.getChipId(), HEX);
#endif
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ap_name.c_str(), wifi_psd);

  IPAddress my_ip = WiFi.softAPIP();
  outputSerial().print("start AP! SSID:");
  outputSerial().print(ap_name);
  outputSerial().print("PSWD:");
  outputSerial().println(wifi_psd);
}
// 启用sta模式
PLEN2::System::System() {
  PLEN2_SYSTEM_SERIAL.begin(SERIAL_BAUDRATE());
  //	WiFi.mode(WIFI_STA);
}

// 配置wiif信息和存储
void PLEN2::System::setup_smartconfig() {
  WiFi.mode(WIFI_STA);
  WiFi.begin("your_ssid", "your_password");

  unsigned char cnt = 0;
  while (WiFi.status() != WL_CONNECTED && cnt < 20) {
    delay(500);
    outputSerial().print(".");
    cnt++;
  }

  smartconfig_tricker.attach_ms(1024, PLEN2::System::smart_config);
}

// format bytes换算
String formatBytes(size_t bytes) {
  if (bytes < 1024) {
    return String(bytes) + "B";
  } else if (bytes < (1024 * 1024)) {
    return String(bytes / 1024.0) + "KB";
  } else if (bytes < (1024 * 1024 * 1024)) {
    return String(bytes / 1024.0 / 1024.0) + "MB";
  } else {
    return String(bytes / 1024.0 / 1024.0 / 1024.0) + "GB";
  }
}

String getContentType(String filename) {
  if (httpServer.hasArg("download"))
    return "application/octet-stream";
  else if (filename.endsWith(".htm"))
    return "text/html";
  else if (filename.endsWith(".html"))
    return "text/html";
  else if (filename.endsWith(".css"))
    return "text/css";
  else if (filename.endsWith(".js"))
    return "application/javascript";
  else if (filename.endsWith(".png"))
    return "image/png";
  else if (filename.endsWith(".gif"))
    return "image/gif";
  else if (filename.endsWith(".jpg"))
    return "image/jpeg";
  else if (filename.endsWith(".ico"))
    return "image/x-icon";
  else if (filename.endsWith(".xml"))
    return "text/xml";
  else if (filename.endsWith(".pdf"))
    return "application/x-pdf";
  else if (filename.endsWith(".zip"))
    return "application/x-zip";
  else if (filename.endsWith(".gz"))
    return "application/x-gzip";
  return "text/plain";
}

bool handleFileRead(String path) {
  PLEN2_SYSTEM_SERIAL.println("handleFileRead: " + path);
  if (path.endsWith("/"))
    path += "index.htm";
  String contentType = getContentType(path);
  String pathWithGz = path + ".gz";
  if (SPIFFS.exists(pathWithGz) || SPIFFS.exists(path)) {
    if (SPIFFS.exists(pathWithGz))
      path += ".gz";
    File file = SPIFFS.open(path, "r");
    size_t sent = httpServer.streamFile(file, contentType);
    file.close();
    return true;
  }
  return false;
}

void handleFileUpload() {
  if (httpServer.uri() != "/edit")
    return;
  HTTPUpload &upload = httpServer.upload();
  if (upload.status == UPLOAD_FILE_START) {
    String filename = upload.filename;
    if (!filename.startsWith("/"))
      filename = "/" + filename;
    PLEN2_SYSTEM_SERIAL.print("handleFileUpload Name: ");
    PLEN2_SYSTEM_SERIAL.println(filename);
    fsUploadFile = SPIFFS.open(filename, "w");
    filename = String();
  } else if (upload.status == UPLOAD_FILE_WRITE) {
    // PLEN2_SYSTEM_SERIAL.print("handleFileUpload Data: ");
    // PLEN2_SYSTEM_SERIAL.println(upload.currentSize);
    if (fsUploadFile)
      fsUploadFile.write(upload.buf, upload.currentSize);
  } else if (upload.status == UPLOAD_FILE_END) {
    if (fsUploadFile)
      fsUploadFile.close();
    PLEN2_SYSTEM_SERIAL.print("handleFileUpload Size: ");
    PLEN2_SYSTEM_SERIAL.println(upload.totalSize);
  }
}

void handleFileDelete() {
  if (httpServer.args() == 0)
    return httpServer.send(500, "text/plain", "BAD ARGS");
  String path = httpServer.arg(0);
  PLEN2_SYSTEM_SERIAL.println("handleFileDelete: " + path);
  if (path == "/")
    return httpServer.send(500, "text/plain", "BAD PATH");
  if (!SPIFFS.exists(path))
    return httpServer.send(404, "text/plain", "FileNotFound");
  SPIFFS.remove(path);
  httpServer.send(200, "text/plain", "");
  path = String();
}

void handleFileCreate() {
  if (httpServer.args() == 0)
    return httpServer.send(500, "text/plain", "BAD ARGS");
  String path = httpServer.arg(0);
  PLEN2_SYSTEM_SERIAL.println("handleFileCreate: " + path);
  if (path == "/")
    return httpServer.send(500, "text/plain", "BAD PATH");
  if (SPIFFS.exists(path))
    return httpServer.send(500, "text/plain", "FILE EXISTS");
  File file = SPIFFS.open(path, "w");
  if (file)
    file.close();
  else
    return httpServer.send(500, "text/plain", "CREATE FAILED");
  httpServer.send(200, "text/plain", "");
  path = String();
}

void handleFileList() {
  if (!httpServer.hasArg("dir")) {
    httpServer.send(500, "text/plain", "BAD ARGS");
    return;
  }

  String path = httpServer.arg("dir");
  PLEN2_SYSTEM_SERIAL.println("handleFileList: " + path);
  Dir dir = SPIFFS.openDir(path);
  path = String();

  String output = "[";
  while (dir.next()) {
    File entry = dir.openFile("r");
    if (output != "[")
      output += ',';
    bool isDir = false;
    output += "{\"type\":\"";
    output += (isDir) ? "dir" : "file";
    output += "\",\"name\":\"";
    output += String(entry.name()).substring(1);
    output += "\"}";
    entry.close();
  }

  output += "]";
  httpServer.send(200, "text/json", output);
}

void PLEN2::System::smart_config() {
  static int cnt = 0;
  static int timeout = 30;

  if (!update_cfg &&
      ((WiFi.status() == WL_CONNECTED) || WiFi.softAPgetStationNum())) {
    if (!servers_started) {
      // list directory
      httpServer.on("/list", HTTP_GET, handleFileList);
      // load editor
      httpServer.on("/edit", HTTP_GET, []() {
        if (!handleFileRead("/edit.htm"))
          httpServer.send(404, "text/plain", "FileNotFound");
      });
      // create file
      httpServer.on("/edit", HTTP_PUT, handleFileCreate);
      // delete file
      httpServer.on("/edit", HTTP_DELETE, handleFileDelete);
      // first callback is called after the request has ended with all parsed
      // arguments second callback handles file uploads at that location
      httpServer.on(
          "/edit", HTTP_POST, []() { httpServer.send(200, "text/plain", ""); },
          handleFileUpload);

      // called when the url is not defined here
      // use it to load content from SPIFFS
      httpServer.onNotFound([]() {
        if (!handleFileRead(httpServer.uri()))
          httpServer.send(404, "text/plain", "FileNotFound");
      });

      // get heap status, analog input value and all GPIO statuses in one json
      // call
      httpServer.on("/all", HTTP_GET, []() {
        String json = "{";
        json += "\"heap\":" + String(ESP.getFreeHeap());
        json += ", \"analog\":" + String(analogRead(A0));
        json += ", \"gpio\":" + String((uint32_t)(((GPI | GPO) & 0xFFFF) |
                                                  ((GP16I & 0x01) << 16)));
        json += "}";
        httpServer.send(200, "text/json", json);
        json = String();
        json += "}";
        httpServer.send(200, "text/json", json);
        json = String();
      });

      // API: List Joints
      httpServer.on("/api/joints", HTTP_GET, []() {
        String json = "[";
        for (int i = 0; i < PLEN2::JointController::SUM; i++) {
          if (i > 0)
            json += ",";
          json += "{\"id\":" + String(i);
          json += ",\"min\":" + String(joint_ctrl.getMinAngle(i));
          json += ",\"max\":" + String(joint_ctrl.getMaxAngle(i));
          json += ",\"home\":" + String(joint_ctrl.getHomeAngle(i));
          json += "}";
        }
        json += "]";
        httpServer.send(200, "text/json", json);
      });

      // API: Set Joint Home (Calibration)
      httpServer.on("/api/set_home", HTTP_POST, []() {
        if (!httpServer.hasArg("id") || !httpServer.hasArg("value")) {
          httpServer.send(400, "text/plain", "Missing id or value");
          return;
        }
        int id = httpServer.arg("id").toInt();
        int val = httpServer.arg("value").toInt();
        if (joint_ctrl.setHomeAngle(id, val)) {
          httpServer.send(200, "text/plain", "OK");
        } else {
          httpServer.send(500, "text/plain", "Failed");
        }
      });

      // API: Move Joint (Check position)
      httpServer.on("/api/move_joint", HTTP_POST, []() {
        if (!httpServer.hasArg("id") || !httpServer.hasArg("value")) {
          httpServer.send(400, "text/plain", "Missing id or value");
          return;
        }
        int id = httpServer.arg("id").toInt();
        int val = httpServer.arg("value").toInt();
        // To move reliably, we might need to use setAngleDiff or just setAngle.
        // setAngle takes raw angle. For calibration context, user might want to
        // set 'Home' then see result. Or set angle to see result, then set
        // Home. Here we simply expose setAngle.
        if (joint_ctrl.setAngle(id, val)) {
          joint_ctrl.updateAngle(); // Force update if needed, though loop
                                    // handles PWM.
          httpServer.send(200, "text/plain", "OK");
        } else {
          httpServer.send(500, "text/plain", "Failed");
        }
      });

      // API: Play Motion
      httpServer.on("/api/play_motion", HTTP_POST, []() {
        if (!httpServer.hasArg("slot")) {
          httpServer.send(400, "text/plain", "Missing slot");
          return;
        }
        int slot = httpServer.arg("slot").toInt();
        motion_ctrl.play(slot);
        httpServer.send(200, "text/plain", "OK");
      });

      // API: Set Motion Speed
      httpServer.on("/api/set_speed", HTTP_POST, []() {
        if (!httpServer.hasArg("value")) {
          httpServer.send(400, "text/plain", "Missing value");
          return;
        }
        int val = httpServer.arg("value").toInt(); // 50, 100, 200
        motion_ctrl.setSpeed(val);
        httpServer.send(200, "text/plain", "OK");
      });

      httpUpdater.setup(&httpServer);
      httpServer.begin();
      servers_started = true;
      outputSerial().println("HTTPUpdateServer ready! Open "
                             "http://192.168.4.1/update in your browser\n");
      tcp_server.begin();
      tcp_server.setNoDelay(true);
    }
    udp.beginPacketMulticast(broadcastIp, BROADCAST_PORT, WiFi.localIP());
    udp.write(robot_name.c_str(), robot_name.length());
    udp.endPacket();
  }

  if (update_cfg && WiFi.smartConfigDone()) {
    outputSerial().println("smartConfigDone!\n");
    outputSerial().printf("SSID:%s\r\n", WiFi.SSID().c_str());
    outputSerial().printf("PSW:%s\r\n", WiFi.psk().c_str());

    if (fp_syscfg) {
      fp_syscfg.close();
      fp_syscfg = SPIFFS.open(SYSCFG_FILE, "w");
      fp_syscfg.println(WiFi.SSID().c_str());
      fp_syscfg.println(WiFi.psk().c_str());
      fp_syscfg.close();
      fp_syscfg = SPIFFS.open(SYSCFG_FILE, "r");
    }
    update_cfg = false;
  }
  if (update_cfg) {
    WiFi.stopSmartConfig();
    StartAp();
    update_cfg = false;
  }
}

void PLEN2::System::handleClient() {
  if (servers_started) {
    httpServer.handleClient();
  }
}

bool PLEN2::System::tcp_available() {
  if (tcp_server.hasClient()) {
    serverClient = tcp_server.available();
    if (!serverClient || !serverClient.connected()) {
      if (serverClient) {
        serverClient.stop();
      }
      serverClient = tcp_server.available();
    }
  }
  if (serverClient && serverClient.connected()) {
    return serverClient.available();
  }
  return false;
}

bool PLEN2::System::tcp_connected() {
  return serverClient && serverClient.connected();
}

char PLEN2::System::tcp_read() { return serverClient.read(); }

Stream &PLEN2::System::SystemSerial() { return PLEN2_SYSTEM_SERIAL; }

Stream &PLEN2::System::inputSerial() { return PLEN2_SYSTEM_SERIAL; }

Stream &PLEN2::System::outputSerial() { return PLEN2_SYSTEM_SERIAL; }

Stream &PLEN2::System::debugSerial() { return PLEN2_SYSTEM_SERIAL; }

void PLEN2::System::dump() {
#if DEBUG
  volatile Utility::Profiler p(F("System::dump()"));
#endif

  outputSerial().println(F("{"));

  outputSerial().print(F("\t\"device\": \""));
  outputSerial().print(DEVICE_NAME);
  outputSerial().println(F("\","));

  outputSerial().print(F("\t\"codename\": \""));
  outputSerial().print(CODE_NAME);
  outputSerial().println(F("\","));

  outputSerial().print(F("\t\"version\": \""));
  outputSerial().print(VERSION);
  outputSerial().println(F("\""));

  outputSerial().println(F("}"));
}
