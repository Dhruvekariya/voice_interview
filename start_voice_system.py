#!/usr/bin/env python3
"""
Voice Interview System Startup Script
Starts all required services:
- ngrok tunnel with static domain
- FastAPI server on localhost:8000
- Connects everything together

Usage: python start_voice_system.py
"""

import os
import sys
import time
import signal
import subprocess
import threading
from dotenv import load_dotenv

def print_status(message, color='\033[92m'):
    """Print status message with color"""
    print(f"{color}[SYSTEM]{'\033[0m'} {message}")

def print_error(message):
    """Print error message in red"""
    print(f"\033[91m[ERROR]\033[0m {message}")

def print_ngrok(message):
    """Print ngrok message in blue"""
    print(f"\033[94m[NGROK]\033[0m {message}")

def print_fastapi(message):
    """Print FastAPI message in yellow"""
    print(f"\033[93m[FASTAPI]\033[0m {message}")

class VoiceSystemManager:
    def __init__(self):
        self.ngrok_process = None
        self.fastapi_process = None
        self.static_url = "https://your-ngrok-domain.ngrok-free.app"
        
    def check_prerequisites(self):
        """Check if all prerequisites are met"""
        print_status("🔍 Checking prerequisites...")
        
        # Check ngrok
        try:
            result = subprocess.run(['ngrok', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            print_status(f"✅ ngrok: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print_error("❌ ngrok not found. Install it first:")
            print("  Visit: https://ngrok.com/download")
            return False
        
        # Check Python
        python_version = sys.version.split()[0]
        print_status(f"✅ Python: {python_version}")
        
        # Check .env file
        if not os.path.exists('.env'):
            print_error("❌ .env file not found")
            print("Create .env file with required variables")
            return False
        else:
            print_status("✅ .env file found")
        
        # Check if webhook is configured
        load_dotenv()
        if not os.getenv('TWILIO_ACCOUNT_SID'):
            print_error("❌ Missing Twilio credentials")
            print("Run: python setup_twilio_webhook.py first")
            return False
        
        print_status("✅ All prerequisites met!")
        return True
    
    def start_ngrok(self):
        """Start ngrok tunnel with static domain"""
        print_status("🌐 Starting ngrok tunnel...")
        
        try:
            # Start ngrok with static domain
            self.ngrok_process = subprocess.Popen(
                ['ngrok', 'http', '--url', self.static_url, '8000'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitor ngrok output in separate thread
            def monitor_ngrok():
                for line in iter(self.ngrok_process.stdout.readline, ''):
                    if line.strip():
                        print_ngrok(line.strip())
            
            threading.Thread(target=monitor_ngrok, daemon=True).start()
            
            # Give ngrok time to start
            time.sleep(3)
            
            if self.ngrok_process.poll() is None:
                print_status(f"✅ ngrok tunnel active: {self.static_url}")
                return True
            else:
                print_error("❌ ngrok failed to start")
                return False
                
        except Exception as e:
            print_error(f"Failed to start ngrok: {e}")
            return False
    
    def start_fastapi(self):
        """Start FastAPI server"""
        print_status("🚀 Starting FastAPI server...")
        
        try:
            # Start FastAPI server (without reload for stable calls)
            self.fastapi_process = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'src.voice_interview.main:app', 
                 '--host', '0.0.0.0', '--port', '8000'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitor FastAPI output in separate thread
            def monitor_fastapi():
                for line in iter(self.fastapi_process.stdout.readline, ''):
                    if line.strip():
                        print_fastapi(line.strip())
            
            threading.Thread(target=monitor_fastapi, daemon=True).start()
            
            # Give FastAPI time to start
            time.sleep(5)
            
            if self.fastapi_process.poll() is None:
                print_status("✅ FastAPI server running on http://localhost:8000")
                return True
            else:
                print_error("❌ FastAPI failed to start")
                return False
                
        except Exception as e:
            print_error(f"Failed to start FastAPI: {e}")
            return False
    
    def display_status(self):
        """Display system status and usage information"""
        print("\n" + "=" * 60)
        print_status("🎉 Voice Interview System Ready!")
        print("=" * 60)
        print(f"📞 Static ngrok URL: {self.static_url}")
        print(f"🏠 Local FastAPI: http://localhost:8000")
        print(f"📋 API Docs: http://localhost:8000/docs")
        print(f"🔍 Health Check: http://localhost:8000/health")
        print("")
        print_status("💡 How to make a call:")
        print("curl -X POST http://localhost:8000/make_call \\")
        print('  -H "Content-Type: application/json" \\')
        print('  -d \'{"phone_number": "+1234567890"}\'')
        print("")
        print_status("🛑 Press Ctrl+C to stop all services")
        print("=" * 60)
    
    def start_system(self):
        """Start the complete voice system"""
        if not self.check_prerequisites():
            sys.exit(1)
        
        print_status("🚀 Starting Voice Interview System...")
        print_status(f"Static Domain: {self.static_url}")
        print("")
        
        # Start ngrok tunnel
        if not self.start_ngrok():
            print_error("Failed to start ngrok tunnel")
            sys.exit(1)
        
        # Start FastAPI server
        if not self.start_fastapi():
            print_error("Failed to start FastAPI server")
            self.cleanup()
            sys.exit(1)
        
        # Display status
        self.display_status()
        
        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print_status("\n🛑 Shutting down system...")
            self.cleanup()
    
    def cleanup(self):
        """Clean up processes"""
        if self.ngrok_process:
            print_status("Stopping ngrok...")
            self.ngrok_process.terminate()
            self.ngrok_process.wait()
        
        if self.fastapi_process:
            print_status("Stopping FastAPI...")
            self.fastapi_process.terminate()
            self.fastapi_process.wait()
        
        print_status("✅ All services stopped")

def main():
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print_status("\n🛑 Received interrupt signal...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start the system
    manager = VoiceSystemManager()
    manager.start_system()

if __name__ == "__main__":
    main() 