import network
import socket
import time
import machine

led = machine.Pin("LED", machine.Pin.OUT)

html = """\
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>LED control with MediaPipe</title>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-core"></script>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-converter"></script>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-backend-webgl"></script>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/hand-pose-detection"></script>
  <style>
    body { margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; background: #000; }
    video, canvas { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) scaleX(-1); }
    #status { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.6); color: white; padding: 8px; font-size: 20px; z-index: 10; }
  </style>
</head>
<body>
  <video id="video" width="640" height="480" autoplay muted playsinline></video>
  <canvas id="canvas" width="640" height="480"></canvas>
  <div id="status">Loading...</div>

  <script>
    const LED_URL = "http://172.20.10.12/led?cmd="; //change the ip address to your microcontroller's ip address 
    let gestureBuffer = [];
    const gestureThreshold = 3;
    let lastCmd = null;
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const statusBox = document.getElementById('status');

    async function setupCamera() {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
      video.srcObject = stream;
      return new Promise(resolve => video.onloadedmetadata = () => resolve(video));
    }

    async function main() {
      await tf.setBackend('webgl');
      await setupCamera();
      video.play();

      const detector = await handPoseDetection.createDetector(handPoseDetection.SupportedModels.MediaPipeHands, {
        runtime: 'tfjs', modelType: 'lite', maxHands: 1
      });

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

          const dx = keypoints[4].x - keypoints[8].x;
          const dy = keypoints[4].y - keypoints[8].y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          let cmd = null;
          if (distance < 40) { cmd = "off"; statusBox.innerText = "Gesture : OFF"; }
          else if (distance < 80) { cmd = "blink"; statusBox.innerText = "Gesture : BLINK"; }
          else { cmd = "on"; statusBox.innerText = "Gesture : ON"; }

          if (cmd) {
            gestureBuffer.push(cmd);
            if (gestureBuffer.length > gestureThreshold) gestureBuffer.shift();
            if (gestureBuffer.length === gestureThreshold && gestureBuffer.every(c => c === cmd) && cmd !== lastCmd) {
              lastCmd = cmd;
              fetch(LED_URL + cmd).then(() => console.log("Command sent :", cmd));
            }
          }
        } else {
          statusBox.innerText = "No hands detected";
          gestureBuffer = [];
        }
      }, 300);
    }
    main();
  </script>
</body>
</html>
"""

ssid = 'name' #change to wi-fi's name
password = 'passwd' #change to wi-fi's password

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

addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)
print("Server is running on", ip)

def blink():
    for _ in range(3):
        led.on()
        time.sleep(0.3)
        led.off()
        time.sleep(0.3)

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
        elif "GET /led?cmd=blink" in request:
            blink()
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nLED BLINK"
        else:
            response = html

        cl.send(response)
        cl.close()
    except OSError as e:
        print("Error:", e)
        cl.close()