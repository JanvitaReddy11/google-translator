import os
import signal
import psutil
from fastapi import FastAPI

app = FastAPI()

PORT = 8000  # Change this if using a different port

def kill_process_using_port(port):
    """Find and kill process using the given port."""
    for proc in psutil.process_iter(['pid', 'name', 'connections']):
        try:
            for conn in proc.info['connections']:
                if conn.laddr.port == port:
                    print(f"Killing process {proc.info['name']} (PID: {proc.info['pid']}) using port {port}")
                    os.kill(proc.info['pid'], signal.SIGKILL)
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

@app.post("/kill_port/")
async def kill_port():
    """Kill the process using port 8000 before handling any requests."""
    killed = kill_process_using_port(PORT)
    return {"message": "Process killed" if killed else "No process found"}

