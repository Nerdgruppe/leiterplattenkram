#include <Arduino.h>
#include <WebServer.h>
#include <WiFi.h>

// Falls ENV-Variablen nicht gesetzt sind, nicht crashen:
#ifndef WIFI_SSID
#error "WIFI_SSID must be present"
#endif

#ifndef WIFI_PASSWORD
#error "WIFI_PASSWORD must be present"
#endif

const char *ssid = WIFI_SSID;
const char *password = WIFI_PASSWORD;

// HTTP-Server auf Port 80
WebServer server(80);

extern const char script_js_start[] asm("_binary_src_script_js_start");
extern const char script_js_end[] asm("_binary_src_script_js_end");

extern const char style_css_start[] asm("_binary_src_style_css_start");
extern const char style_css_end[] asm("_binary_src_style_css_end");

enum class Mode : int {
  continuous = 0,
  pulse = 1,
  pulse_reverse = 2,
};

struct Settings {
  Mode mode;
  int duration_s;
  bool current_control;
  int current_target_mA;
};

struct Status {
  bool enabled;
  float temperature_dC;
  float voltage_V;
  int current_mA;
  int duration_s;
};

namespace emsys {
static Settings settings = {
    .mode = Mode::continuous,
    .duration_s = 600,
    .current_control = false,
    .current_target_mA = 500,
};

static Status status = {
    .enabled = false,
    .temperature_dC = 23.1f,
    .voltage_V = 1.2,
    .current_mA = 500,
    .duration_s = 140,
};

} // namespace emsys

template <typename T, typename... TRest>
static void appendString(String &str, T const &arg, TRest &&...args) {
  str.concat(arg);
  if constexpr (sizeof...(args) > 0) {
    appendString<TRest...>(str, args...);
  }
}

template <typename T, typename... TRest>
static void formatString(String &str, T const &arg, TRest &&...args) {
  str.clear();
  appendString(str, arg, args...);
}

template <typename TValue>
static void appendRow(String &str, char const *title, TValue value,
                      char const *unit) {
  appendString(str, "<tr><td>", title, "</td><td>", value, "</td><td>", unit,
               "</td></tr>");
}

static void appendSetting(String &str, char const *title, String const &value) {
  appendString(str, "<tr><td>", title, "</td><td>", value, "</td></tr>");
}

static void renderStatus(String &body) {
  appendRow<float>(body, "Temperature", emsys::status.temperature_dC, "°C");
  appendRow<float>(body, "Voltage", emsys::status.voltage_V, "V");
  appendRow<int>(body, "Current", emsys::status.current_mA, "mA");
  if (emsys::status.enabled) {
    appendRow<int>(body, "Duration", emsys::status.duration_s, "s");
  } else {
    appendRow<char const *>(body, "Duration", "stopped", "");
  }
}

// Handler für GET /
void handleRoot() {
  static String body;
  body.clear();

  body.concat(R"html(<!DOCTYPE html>
<html lang="en">
<head>
  <title>EtchMaster</title>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>EtchMaster</h1>)html");
  if (!emsys::status.enabled) {

    body.concat(R"html(
<form method="POST" class="settings">
  <table>
    <thead>
      <tr><th>Setting</th><th>Value</th></tr>
    </thead>
    <tbody>)html");

    static String setting;
    {
      setting.clear();

      struct Prop {
        char const *title;
        Mode mode;
      };

      static const Prop props[] = {
          {"Continuous", Mode::continuous},
          {"Pulse", Mode::pulse},
          {"Pulse Reverse", Mode::pulse_reverse},
      };

      for (auto const &prop : props) {
        appendString(setting,
                     "<label class=\"line\">"
                     "<input type=\"radio\" name=\"mode\" value=\"",
                     static_cast<int>(prop.mode), "\"");
        if (emsys::settings.mode == prop.mode) {
          setting.concat(" checked");
        }
        appendString(setting, ">", prop.title, "</label>");
      }

      appendSetting(body, "Mode", setting);
    }

    {
      formatString(setting,
                   "<input type=\"number\" min=\"0\" max=\"7200\" "
                   "name=\"duration\" value=\"",
                   emsys::settings.duration_s, "\"> s");
      appendSetting(body, "Duration", setting);
    }

    {
      setting.clear();
      formatString(setting,
                   "<label><input type=\"checkbox\" name=\"current-control\"",
                   emsys::settings.current_control ? " checked" : "",
                   ">Enabled</label>");
      appendSetting(body, "Current Control", setting);
    }

    {
      formatString(setting,
                   "<input type=\"number\" min=\"0\" max=\"2500\" "
                   "name=\"current-target\" value=\"",
                   emsys::settings.current_target_mA, "\"> MA");
      appendSetting(body, "Current Target", setting);
    }

    body.concat(R"html(</tbody>
    <tfoot>
      <tr>
        <td colspan="2" class="controls">
          <button type="reset">Revert</button>
          <button type="submit" name="action" value="update">Save</button>
        </td>
      </tr>
    </tfoot>
  </table>
</form>)html");
  }

  body.concat(R"html(<table>
			<thead>
				<tr><th>Measurement</th><th>Value</th><th>Unit</th></tr>
			</thead>
			<tbody id="statusbody">)html");
  renderStatus(body);
  body.concat(R"html(</tbody>
  </table>
  <form method="POST" class="controls">
    <button type="submit" name="action" value="start">Start</button>
    <button type="submit" name="action" value="stop">Stop</button>
  </form>
  <script src="script.js"></script>
</body>
</html>
)html");

  server.send(200, "text/html", body);
}

void handleAction() {
  String action = server.arg("action");
  if (action == "start") {
    emsys::status.enabled = true;

  } else if (action == "stop") {
    emsys::status.enabled = false;
    //
  } else if (action == "update") {
    if (emsys::status.enabled) {
      server.send(409, "text/plain",
                  "no config changes allowed. system is running.\r\n");
      return;
    }
  } else {

    Serial.printf("action? '%s'\n", action.c_str());
  }

  Serial.printf("method: %d\n", static_cast<int>(server.method()));
  Serial.printf("uri:  %s\n", server.uri().c_str());
  Serial.printf("args: %d\n", server.args());

  for (int i = 0; i < server.args(); i++) {
    Serial.printf("  [%d]: %s = '%s'\n", i, server.argName(i).c_str(),
                  server.arg(i).c_str());
  }

  handleRoot();
}

void handleStatus() {
  static String body;
  body.clear();
  renderStatus(body);
  server.send(200, "text/html", body);
}

template <char const head[], char const tail[]>
void sendFile(char const *contentType) {
  server.send_P(200, contentType, head, (tail - head) - 1U);
}

void handleScriptJs() {
  sendFile<script_js_start, script_js_end>("application/javascript");
}

void handleStyleCss() { sendFile<style_css_start, style_css_end>("text/css"); }

// Optional: 404-Handler
void handleNotFound() {
  String message = "File Not Found\n\n";
  message += "URI: ";
  message += server.uri();
  message += "\nMethod: ";
  message += (server.method() == HTTP_GET) ? "GET" : "POST";
  message += "\n";
  server.send(404, "text/plain", message);
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("Starte ESP32 HTTP-Server...");

  if (strlen(ssid) == 0) {
    Serial.println("WARNUNG: WIFI_SSID ist leer. Bitte ENV-Variablen setzen!");
  }

  // WLAN im Station-Mode
  WiFi.mode(WIFI_STA);
  WiFi.setHostname("etchmaster");
  WiFi.begin(ssid, password);

  Serial.printf("Verbinde mit WLAN '%s' ...\n", ssid);

  // Auf Verbindung warten (max. ca. 30 Sek.)
  uint8_t retries = 60;
  while (WiFi.status() != WL_CONNECTED && retries--) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WLAN verbunden!");
    Serial.print("IP-Adresse: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WLAN-Verbindung fehlgeschlagen. HTTP-Server startet "
                   "trotzdem, aber ist natürlich nicht erreichbar.");
  }

  // HTTP-Routen registrieren
  server.on("/", HTTP_GET, handleRoot);
  server.on("/", HTTP_POST, handleAction);
  server.on("/status.html", HTTP_GET, handleStatus);
  server.on("/script.js", HTTP_GET, handleScriptJs);
  server.on("/style.css", HTTP_GET, handleStyleCss);
  server.onNotFound(handleNotFound);

  // Server starten
  server.begin();
  Serial.println("HTTP-Server läuft auf Port 80.");
}

void loop() { server.handleClient(); }