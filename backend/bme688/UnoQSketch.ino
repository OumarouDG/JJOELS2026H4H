#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>
#include <Arduino_RouterBridge.h>

Adafruit_BME680 bme;

// I2C address (switch is usually 0x77 by default; flip to 0x76 if needed)
#define BME_ADDR 0x77

unsigned long last_ms = 0;
const unsigned long PERIOD_MS = 200; // 5 Hz

bool streaming = false;
bool header_sent = false;

// ===============================
// Rolling buffer for "capture"
// ===============================
static const int BUF_MAX = 300; // 60s @ 5Hz = 300 samples
float bufTemp[BUF_MAX];
float bufHum[BUF_MAX];
float bufPres[BUF_MAX];
uint32_t bufGas[BUF_MAX];
unsigned long bufMs[BUF_MAX];

int bufCount = 0;
int bufHead = 0;

// Capture window length (seconds) used for prediction
static const float CAPTURE_S = 10.0f;

// ===============================
// Helper: push sample into buffer
// ===============================
void pushSample(float t, float h, float p, uint32_t g) {
  bufTemp[bufHead] = t;
  bufHum[bufHead] = h;
  bufPres[bufHead] = p;
  bufGas[bufHead] = g;
  bufMs[bufHead] = millis();

  bufHead = (bufHead + 1) % BUF_MAX;
  if (bufCount < BUF_MAX) bufCount++;
}

// ===============================
// Compute capture stats over last N seconds
// ===============================
bool computeCaptureStats(float &gasMean, float &gasMin, float &gasMax, float &gasDelta) {
  if (bufCount < 5) return false;

  unsigned long now = millis();
  unsigned long windowMs = (unsigned long)(CAPTURE_S * 1000.0f);
  unsigned long cutoff = (now > windowMs) ? (now - windowMs) : 0;

  // Walk backwards through buffer and include samples within cutoff
  int used = 0;
  double sum = 0.0;
  gasMin = 1e30f;
  gasMax = -1e30f;

  // newest index is bufHead - 1
  int idx = bufHead - 1;
  if (idx < 0) idx += BUF_MAX;

  // Track oldest gas in window for delta
  uint32_t oldestGas = 0;
  uint32_t newestGas = bufGas[idx];

  for (int k = 0; k < bufCount; k++) {
    unsigned long tms = bufMs[idx];
    if (tms < cutoff) break;

    float g = (float)bufGas[idx];
    sum += g;
    if (g < gasMin) gasMin = g;
    if (g > gasMax) gasMax = g;
    oldestGas = bufGas[idx];

    used++;

    idx--;
    if (idx < 0) idx += BUF_MAX;
  }

  if (used < 5) return false;

  gasMean = (float)(sum / used);
  gasDelta = (float)newestGas - (float)oldestGas;
  return true;
}

// ===============================
// SUPER SIMPLE "MODEL" PLACEHOLDER
// Replace this later with real on-device model
// ===============================
void predictAndPrint() {
  float gasMean, gasMin, gasMax, gasDelta;
  if (!computeCaptureStats(gasMean, gasMin, gasMax, gasDelta)) {
    Monitor.println("PRED,UNKNOWN,0.00");
    return;
  }

  // --- Placeholder logic (adjust these thresholds based on your data) ---
  // Example: say "POSITIVE" if gasMean is low OR gasDelta drops sharply.
  // (This is just to prove the pipeline works end-to-end.)
  const float GAS_MEAN_THRESHOLD = 90000.0f;   // tune for your environment
  const float GAS_DELTA_THRESHOLD = -2000.0f;  // tune for your environment

  const char *label = "NEGATIVE";
  float confidence = 0.60f;

  if (gasMean < GAS_MEAN_THRESHOLD || gasDelta < GAS_DELTA_THRESHOLD) {
    label = "POSITIVE";
    confidence = 0.87f;
  } else {
    label = "NEGATIVE";
    confidence = 0.83f;
  }

  // Output format for collector:
  // PRED,<LABEL>,<CONF>,gas_mean=...,gas_delta=...
  Monitor.print("PRED,");
  Monitor.print(label);
  Monitor.print(",");
  Monitor.print(confidence, 2);
  Monitor.print(",gas_mean=");
  Monitor.print(gasMean, 0);
  Monitor.print(",gas_delta=");
  Monitor.println(gasDelta, 0);
}

// ===============================
// Existing UI helpers
// ===============================
void printHelp() {
  Monitor.println("Commands:");
  Monitor.println("  s = start streaming");
  Monitor.println("  p = pause/stop streaming");
  Monitor.println("  r = read once");
  Monitor.println("  c = capture + predict (prints PRED,...)");
  Monitor.println("  h = help");
}

void printHeader() {
  // Keep it clean: plotter labels are fragile.
  Monitor.println("tempC,humidity,pressure_hPa,gas_ohms");
}

bool readSensor(float &tempC, float &hum, float &pres_hPa, uint32_t &gas) {
  if (!bme.performReading()) return false;

  tempC = bme.temperature;
  hum = bme.humidity;
  pres_hPa = bme.pressure / 100.0f;
  gas = bme.gas_resistance;

  // Save to rolling buffer for later capture/predict
  pushSample(tempC, hum, pres_hPa, gas);
  return true;
}

void printReading() {
  float tempC, hum, pres_hPa;
  uint32_t gas;

  if (!readSensor(tempC, hum, pres_hPa, gas)) return;

  Monitor.print(tempC, 2);    Monitor.print(",");
  Monitor.print(hum, 2);      Monitor.print(",");
  Monitor.print(pres_hPa, 2); Monitor.print(",");
  Monitor.println(gas);
}

void handleCommands() {
  while (Monitor.available()) {
    char c = (char)Monitor.read();
    if (c == '\n' || c == '\r' || c == ' ') continue;

    if (c == 's') {
      streaming = true;
      header_sent = false; // re-send header on next stream start
      Monitor.println("OK: streaming ON");
    } else if (c == 'p') {
      streaming = false;
      Monitor.println("OK: streaming OFF");
    } else if (c == 'r') {
      if (!header_sent) { printHeader(); header_sent = true; }
      printReading();
    } else if (c == 'c') {
      // Capture + predict (does NOT require streaming to be ON)
      // But it works best after ~10 seconds of data have been collected.
      predictAndPrint();
    } else if (c == 'h') {
      printHelp();
    } else {
      Monitor.println("Unknown command. Type 'h'.");
    }
  }
}

void setup() {
  Bridge.begin();
  Monitor.begin();
  delay(500);

  Wire.begin();

  if (!bme.begin(BME_ADDR)) {
    Monitor.print("BME688 not found at 0x");
    Monitor.println(BME_ADDR, HEX);
    while (1) delay(1000);
  }

  bme.setTemperatureOversampling(BME680_OS_8X);
  bme.setHumidityOversampling(BME680_OS_2X);
  bme.setPressureOversampling(BME680_OS_4X);
  bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
  bme.setGasHeater(320, 150);

  Monitor.println("BME688 ready. Type 'h' for commands.");
  Monitor.println("Tip: send 's' to stream, then 'c' to print a PRED line.");
}

void loop() {
  handleCommands();

  if (!streaming) return;

  if (!header_sent) {
    // For best label behavior: open Serial Plotter, then send 's'
    printHeader();
    header_sent = true;
    last_ms = millis();
  }

  if (millis() - last_ms < PERIOD_MS) return;
  last_ms += PERIOD_MS;

  printReading();
}