import time
import network
import socket
import ntptime
import machine
from machine import Pin, ADC
import utime

led = Pin("LED", Pin.OUT)
sensor_temp = ADC(4)
conversion_factor = 3.3 / 65535

ssid = 'name'
password = 'passwd'

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

max_wait = 10
while max_wait > 0:
    if wlan.status() >= 3:
        break
    max_wait -= 1
    time.sleep(1)

if wlan.status() != 3:
    raise RuntimeError('network connection failed')
else:
    print('Connected')
    print('IP:', wlan.ifconfig()[0])

try:
    print("Synchronizing time with NTP...")
    ntptime.settime()
    print("Time synchronized.")
except:
    print("NTP sync failed.")

html = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        html { font-family: Helvetica; text-align: center; }
        .buttonGreen { background-color: #4CAF50; padding: 15px 32px; color: white; font-size: 16px; margin: 10px; border: none; }
        .buttonRed { background-color: #D11D53; padding: 15px 32px; color: white; font-size: 16px; margin: 10px; border: none; }
    </style>
</head>
<body>
    <h1>Raspberry Pi Pico W</h1>
    <form>
        <button class="buttonGreen" name="led" value="on" type="submit">LED ON</button>
        <button class="buttonRed" name="led" value="off" type="submit">LED OFF</button>
    </form>
    <p>LED State: %s</p>
    <p>Temperature: %s &deg;C</p>
    <p>Measured at (JST): %s</p>
</body>
</html>
"""

addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)
print('Listening on', addr)

while True:
    try:
        cl, addr = s.accept()
        print('Client connected from', addr)
        request = cl.recv(1024)
        #request = str(request)
        request = request.decode('utf-8')
        print(request)

        if 'led=on' in request:
            led.value(1)
        elif 'led=off' in request:
            led.value(0)

        reading = sensor_temp.read_u16() * conversion_factor
        temperature = round(27 - (reading - 0.706) / 0.001721, 2)

        now_jst = utime.localtime(utime.time() + 9 * 3600)
        date_str = "{:02d}/{:02d}/{} {:02d}:{:02d}:{:02d}".format(
            now_jst[2], now_jst[1], now_jst[0], now_jst[3], now_jst[4], now_jst[5]) #jour, mois, année, heure, minute, seconde

        led_state = "ON" if led.value() else "OFF"
        response = html % (led_state, temperature, date_str)

        cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        cl.send(response)
        cl.close()

    except OSError:
        cl.close()
        print('Connection closed')
