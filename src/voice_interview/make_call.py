from twilio.rest import Client
import os

# Twilio credentials (corrected format)
account_sid = ""  # Starts with AC
auth_token = ""     # The auth token
twilio_phone_number = "+"  # Your Twilio phone number

# Your Indian number in E.164 format
your_number = ""  # The number you want to call

# Initialize Twilio client
client = Client(account_sid, auth_token)

# Make the call
try:
    call = client.calls.create(
        twiml="<Response><Say>Hello, this is a test call from your voice interview system.</Say></Response>",
        to=your_number,  # Your Indian mobile number
        from_=twilio_phone_number  # The Twilio phone number
    )
    print(f"Call initiated! Call SID: {call.sid}")
    
except Exception as e:
    print(f"Error making call: {e}")
