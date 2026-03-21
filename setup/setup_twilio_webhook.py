#!/usr/bin/env python3
"""
One-time Twilio Webhook Setup
Configure Twilio phone number to use static ngrok domain
Only needs to be run once!
"""

import os
from twilio.rest import Client
from dotenv import load_dotenv

def print_status(message, color='\033[92m'):
    """Print status message with color"""
    print(f"{color}[INFO]{'\033[0m'} {message}")

def print_error(message):
    """Print error message in red"""
    print(f"\033[91m[ERROR]\033[0m {message}")

def setup_twilio_webhook():
    """One-time setup of Twilio webhook with static ngrok domain"""
    load_dotenv()
    
    # Static ngrok domain - never changes!
    static_url = "https://your-ngrok-domain.ngrok-free.app"
    webhook_url = f"{static_url}/twilio/outbound_call"
    
    # Get Twilio credentials
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN') 
    phone_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, phone_number]):
        print_error("Missing Twilio credentials in .env file")
        print("Required variables:")
        print("- TWILIO_ACCOUNT_SID")
        print("- TWILIO_AUTH_TOKEN") 
        print("- TWILIO_PHONE_NUMBER")
        return False
        
    try:
        print_status("🔧 Setting up Twilio webhook (one-time only)...")
        client = Client(account_sid, auth_token)
        
        # Find the phone number
        phone_numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if not phone_numbers:
            print_error(f"Phone number {phone_number} not found in your Twilio account")
            return False
            
        phone_number_resource = phone_numbers[0]
        
        # Update webhook URLs for all voice events
        phone_number_resource.update(
            voice_url=webhook_url,
            voice_method='POST',
            status_callback=f"{static_url}/twilio/status_callback",
            status_callback_method='POST'
        )
        
        print_status(f"✅ Twilio webhook configured!")
        print_status(f"📞 Phone number: {phone_number}")
        print_status(f"🌐 Webhook URL: {webhook_url}")
        print_status(f"📊 Status callback: {static_url}/twilio/status_callback")
        print("")
        print_status("🎉 Setup complete! You can now use the startup script.")
        print_status("💡 This webhook configuration is permanent - no need to run this again!")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to setup Twilio webhook: {e}")
        return False

def main():
    print_status("🚀 Twilio Webhook One-Time Setup")
    print_status("Static Domain: https://your-ngrok-domain.ngrok-free.app")
    print("=" * 60)
    
    if setup_twilio_webhook():
        print("\n" + "=" * 60)
        print_status("Next steps:")
        print("1. Run: python start_voice_system.py")
        print("2. Make calls via: POST http://localhost:8000/make_call")
    else:
        print("\n" + "=" * 60)
        print_error("Setup failed. Please check your .env file and try again.")

if __name__ == "__main__":
    main() 