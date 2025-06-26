import network
import socket
import time
import machine

led = machine.Pin("LED", machine.Pin.OUT)

ssid = 'name' #change to your wi-fi's name
password = 'passwd' #change to your wi-fi's password 

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

print("Connecting to Wi-Fi...")
max_wait = 10
while max_wait > 0:
    if wlan.status() >= 3:
        break
    max_wait -= 1
    time.sleep(1)

if wlan.status() != 3:
    raise RuntimeError('Network connection failed')
else:
    ip = wlan.ifconfig()[0]
    print('Connected, IP address:', ip)

html = """\
HTTP/1.1 200 OK
Content-Type: text/html 


<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>LED Control with MediaPipe</title>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-core"></script>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-converter"></script>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-backend-webgl"></script>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/hand-pose-detection"></script>
  <style>
    body {
      margin: 0;
      background: #fff;
      font-family: Arial, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    h1 {
      margin: 20px 0 10px;
      color: #333;
    }

    h2 {
      margin: 0 0 20px;
      font-weight: normal;
      color: #555;
      font-size: 18px;
    }

    #video-container {
      position: relative;
      width: 640px;
      height: 480px;
    }

    video, canvas {
      position: absolute;
      top: 0;
      left: 0;
      transform: scaleX(-1);
    }

    #video {
      z-index: 1;
    }

    #canvas {
      z-index: 2;
    }

    #status {
      position: absolute;
      top: 10px;
      left: 10px;
      background: rgba(0, 0, 0, 0.6);
      color: white;
      padding: 8px;
      font-size: 16px;
      z-index: 10;
    }

    #log {
      margin-top: 20px;
      width: 640px;
      background: #f9f9f9;
      border: 1px solid #ccc;
      padding: 10px;
      font-size: 14px;
      color: #333;
      max-height: 200px;
      overflow-y: auto;
    }

    .log-entry {
      margin-bottom: 5px;
    }
  </style>
</head>
<body>
  <h1>Gesture LED Control</h1>
  <h2>Quickly touch your thumb and middle finger twice to turn the LED on or off</h2>

  <div id="video-container">
    <video id="video" width="640" height="480" autoplay muted playsinline></video>
    <canvas id="canvas" width="640" height="480"></canvas>
    <div id="status">Loading...</div>
  </div>

  <div id="log"><strong>Log :</strong></div>

  <script>
    const LED_URL = "/led?cmd=";
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const statusBox = document.getElementById('status');
    const logBox = document.getElementById('log');

    let ledState = false;
    let clickCount = 0;
    let cooldown = false;

    function addLogEntry(action) {
      const time = new Date().toLocaleTimeString();
      const entry = document.createElement("div");
      entry.className = "log-entry";
      entry.textContent = `[${time}] Detected gesture → LED ${action.toUpperCase()}`;
      logBox.appendChild(entry);
      logBox.scrollTop = logBox.scrollHeight;
    }

    async function setupCamera() {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: false
      });
      video.srcObject = stream;
      return new Promise(resolve => video.onloadedmetadata = () => resolve(video));
    }

    async function main() {
      await tf.setBackend('webgl');
      await setupCamera();
      video.play();

      const detector = await handPoseDetection.createDetector(
        handPoseDetection.SupportedModels.MediaPipeHands,
        { runtime: 'tfjs', modelType: 'lite', maxHands: 1 }
      );

      statusBox.innerText = "Please show your hand";

      setInterval(async () => {
        const hands = await detector.estimateHands(video, { flipHorizontal: true });
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (hands.length > 0) {
          const keypoints = hands[0].keypoints;

          keypoints.forEach(pt => {
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 5, 0, 2 * Math.PI);
            ctx.fillStyle = "lime";
            ctx.fill();
          });

          const thumb = keypoints[4];
          const middle = keypoints[12];
          const dx = thumb.x - middle.x;
          const dy = thumb.y - middle.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 40 && !cooldown) {
            clickCount++;
            cooldown = true;
            setTimeout(() => { cooldown = false; }, 500);

            if (clickCount === 2) {
              ledState = !ledState;
              const cmd = ledState ? "on" : "off";
              fetch(LED_URL + cmd).then(() => console.log("Command sent:", cmd));
              statusBox.innerText = `Gesture : ${cmd.toUpperCase()}`;
              addLogEntry(cmd);
              clickCount = 0;
            }
          } else if (clickCount === 0) {
            statusBox.innerText = "Hand detected - waiting for gesture...";
          }

        } else {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          statusBox.innerText = "No hands detected";
          clickCount = 0;
        }
      }, 300);
    }

    main();
  </script>
</body>
</html>
"""

addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)
print("Server is running on", ip)

while True:
    try:
        cl, addr = s.accept()
        print('Client connected from', addr)
        request = cl.recv(1024).decode()
        print("Request:", request)

        if "GET /led?cmd=on" in request:
            led.on()
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nLED ON"
        elif "GET /led?cmd=off" in request:
            led.off()
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nLED OFF"
        else:
            response = "HTTP/1.1 404 Not Found\r\n\r\n"

        cl.send(response)
        cl.close()
    except OSError as e:
        print("Error:", e)
        cl.close()