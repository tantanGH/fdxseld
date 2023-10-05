import os
import argparse
import sys
import signal
import subprocess
import socketserver
import http.server

from urllib.parse import urlparse
from urllib.parse import parse_qs

#
#  Custom Exception class
#
class HttpException(Exception):
  def __init__(self, code):
    self.code = code
  def __str__(self):
    return repr(self.code)

#
#  Custom HTTP Request Handler class
#
class FDX68SelectorHTTPRequestHandler(http.server.BaseHTTPRequestHandler):

  #
  #  GET handler
  #
  def do_GET(self):

    try:
  
      parsed = urlparse(self.path)
      params = parse_qs(parsed.query)
      cmd_error = ""
  
      if parsed.path == "/insert":
        if 'drive_id' not in params or 'image_path' not in params:
          cmd_error = "insert parameter error."
        else:
          drive_id = params['drive_id'][0]
          image_path = params['image_path'][0]
          child = subprocess.run([self.server.fddctl_cmd, '-i', drive_id, '-c', 'insert', image_path])
          rc = child.returncode
          if rc != 0:
            cmd_error = "insert failed."
      elif parsed.path == "/eject":
        if 'drive_id' not in params:
          cmd_error = "eject parameter error."
        else:
          drive_id = params['drive_id'][0]
          child = subprocess.run([self.server.fddctl_cmd, '-i', drive_id, '-c', 'eject'])
          rc = child.returncode
          if rc != 0:
            cmd_error = "eject failed."
      elif parsed.path == "/protect":
        if 'drive_id' not in params:
          cmd_error = "protect parameter error."
        else:
          drive_id = params['drive_id'][0]
          child = subprocess.run([self.server.fddctl_cmd, '-i', drive_id, '-c', 'protect'])
          rc = child.returncode
          if rc != 0:
            cmd_error = "protect failed."

      current_date = subprocess.run(['date'], capture_output=True, text=True)
      #uptime = subprocess.run(['uptime'], capture_output=True, text=True)
      system_model = subprocess.run(['cat', '/proc/device-tree/model'], capture_output=True, text=True)
      measure_temp = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
      measure_clock_arm = subprocess.run(['vcgencmd', 'measure_clock', 'arm'], capture_output=True, text=True)
      measure_clock_core = subprocess.run(['vcgencmd', 'measure_clock', 'core'], capture_output=True, text=True)
      measure_clock_arm_mhz = float(measure_clock_arm.stdout.split('=')[1]) / 1000000.0
      measure_clock_core_mhz = float(measure_clock_core.stdout.split('=')[1]) / 1000000.0

      fddctl_list = subprocess.run([self.server.fddctl_cmd, '-l'], capture_output=True, text=True)
      info_lines = fddctl_list.stdout.splitlines()
      dr0 = info_lines[3].split('|')
      dr1 = info_lines[4].split('|')
      dr0_id = dr0[0].strip()
      dr1_id = dr1[0].strip()

      if dr0[3].strip() == "EMPTY":
        dr0_ops = "&nbsp;"
      else:
        dr0_ops = f"<a href='/eject?drive_id={dr0_id}'>EJECT</a> <a href='/protect?drive_id={dr0_id}'>PROTECT ON/OFF"

      if dr1[3].strip() == "EMPTY":
        dr1_ops = "&nbsp;"
      else:
        dr1_ops = f"<a href='/eject?drive_id={dr1_id}'>EJECT</a> <a href='/protect?drive_id={dr1_id}'>PROTECT ON/OFF"

      image_entries = []
      for image_dir in sorted(self.server.image_dirs):
        for file_name in sorted(os.listdir(image_dir), key=str.lower):
          file_ext = file_name[-4:].lower()
          if file_ext == ".fdx" or file_ext == ".xdf" or file_ext == ".dim":
            image_entries.append(f"<tr><td>{image_dir}</td><td>{file_name}</td><td><a href='/insert?drive_id={dr0_id}&image_path={image_dir}/{file_name}'>INSERT(DRIVE{dr0_id})</a> <a href='/insert?drive_id={dr1_id}&image_path={image_dir}/{file_name}'>INSERT(DRIVE{dr1_id})</a></td>")

      image_entries_list = "\n".join(image_entries)

      content_text = f"""
<html>
  <head>
    <title>FDX68 Selector Service</title>
  </head>
  <body bgcolor='#000055' text='#ffffff' link='#ffff99' alink='#ffff99' vlink='#ffff99'>
    <h1>FDX68 Image Selector Service</h1>
    <div>
      <a href='/'>REFRESH PAGE</a>
    </div>
    <h3>System Information</h3>
    <div>
      Date/Time: {current_date.stdout}<br>
      Model: {system_model.stdout}<br>
      CPU Clock: {measure_clock_arm_mhz:.2f}MHz<br>
      Core Clock: {measure_clock_core_mhz:.2f}MHz<br>
      SoC Temp: {measure_temp.stdout.split('=')[1]}<br>
    </div>
    <h3>Current Drive Status</h3>
    <div>
      <table border='1'>
        <tr><th>ID</th><th>WP</th><th>CL</th><th>DISK IMAGE</th><th>OPERATION</th>
        <tr><td>{dr0[0].strip()}</td><td>{dr0[1].strip()}</td><td>{dr0[2].strip()}</td><td>{dr0[3].strip()}</td><td>{dr0_ops}</td></tr>
        <tr><td>{dr1[0].strip()}</td><td>{dr1[1].strip()}</td><td>{dr1[2].strip()}</td><td>{dr1[3].strip()}</td><td>{dr1_ops}</td></tr>
      </table>
    </div>
    <div>
      <font color='red'><b>{cmd_error}</b></font>
    </div>
    <h3>Image List</h3>
    <div>
      <table border='1'>
        <tr><th>IMAGE DIR</th><th>IMAGE FILE</th><th>OPERATION</th></tr>
        {image_entries_list}
      </table>
    </div>
  </body>
</html>
"""

      content = content_text.encode('cp932', 'ignore')

      self.send_response(200)
      self.send_header('Content-Type', 'text/html')
      self.end_headers()
      self.wfile.write(content)

    except HttpException as e:
      self.send_response(e.code)
      self.send_header('Content-Type', 'text/plain')
      self.end_headers()
      self.wfile.write(b'error')

#
#  Server class
#
class StoppableServer(socketserver.TCPServer):

  # sigterm handler
  def sigterm_handler(self, signum, frame):
    print("Received SIGTERM. Stopping the service.")
    os.kill(os.getpid(), signal.SIGINT)   # emulate CTRL+C

  # service loop
  def run(self, fddctl_cmd, image_dirs):
    
    self.fddctl_cmd = fddctl_cmd
    self.image_dirs = image_dirs

    signal.signal(signal.SIGTERM, self.sigterm_handler)

    try:
      self.serve_forever()
    except KeyboardInterrupt:
      pass
    finally:
      self.server_close()
      print("Stopped.")

# main
def main():

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="service port number", type=int, default=6860)
    parser.add_argument("-c", "--fddctl_cmd", help="fddctl command path", default="/home/pi/fdx68/bin/fddctl")
    parser.add_argument("-i", "--image_dir_list", help="FD image dir list", default="/home/pi/fdx68/dump,/home/pi/fdx68/xdf")
    args = parser.parse_args()

    if os.path.isfile(args.fddctl_cmd) is False:
      print(f"fddctl command cannot be found at {args.fddctl_cmd}.")
      sys.exit(1)
    
    image_dirs = args.image_dir_list.split(",")
    for ip in image_dirs:
      if os.path.isdir(ip) is False:
        print(f"FD image directory {ip} does not exist.")
        sys.exit(1)

    # start service
    socketserver.TCPServer.allow_reuse_address = True
    with StoppableServer(("0.0.0.0", args.port), FDX68SelectorHTTPRequestHandler) as server:
      print(f"Started at port {args.port}")
      server.run(args.fddctl_cmd, image_dirs)

if __name__ == "__main__":
    main()
