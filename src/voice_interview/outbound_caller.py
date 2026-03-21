import os
import asyncio
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class OutboundCaller:
    """Handles outbound calls with voice conversation."""
    
    def __init__(self):
        """Initialize the outbound caller."""
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.ngrok_url = os.getenv("NGROK_URL", "https://your-ngrok-domain.ngrok-free.app")
        
        if not all([self.account_sid, self.auth_token, self.twilio_phone_number]):
            raise ValueError("Twilio credentials are required")
        
        self.client = Client(self.account_sid, self.auth_token)
    
    def make_interview_call(self, phone_number):
        """
        Initiate an outbound call for voice interview.
        
        Args:
            phone_number: Phone number to call (in E.164 format)
        """
        # The webhook URL that will handle the call
        webhook_url = f"{self.ngrok_url}/twilio/outbound_call"
        
        try:
            call = self.client.calls.create(
                to=phone_number,
                from_=self.twilio_phone_number,
                url=webhook_url,
                method="POST",
                status_callback=f"{self.ngrok_url}/twilio/status_callback",
                status_callback_event=["initiated", "ringing", "answered", "completed"]
            )
            
            print(f"Outbound call initiated! Call SID: {call.sid}")
            print(f"Calling {phone_number} from {self.twilio_phone_number}")
            return call.sid
            
        except Exception as e:
            print(f"Error making outbound call: {e}")
            raise
    
    def generate_call_twiml(self):
        """
        Generate TwiML to directly connect to WebSocket streaming.
        Professional greeting with smooth handoff to ElevenLabs agent.
        """
        response = VoiceResponse()
        
        # Professional greeting with smooth handoff
        response.say(
            "Hello! Thank you for taking the time to speak with us today. "
            "I'm connecting you now to Alex, your AI interviewer, who will be conducting "
            "your screening interview. Please hold for just a moment.",
            voice="Polly.Joanna",
            rate="medium"
        )
        
        # Connect directly to WebSocket for real-time streaming
        connect = Connect()
        ws_url = self.ngrok_url.replace('https://', 'wss://') + '/twilio/media_stream'
        connect.stream(url=ws_url)
        response.append(connect)
        
        print(f"🎯 Generated TwiML with WebSocket URL: {ws_url}")
        return str(response)
    
    def generate_status_callback_response(self):
        """Generate response for status callbacks."""
        response = VoiceResponse()
        return str(response)

    def generate_simple_test_twiml(self):
        """
        Generate simple TwiML for testing TTS functionality.
        """
        response = VoiceResponse()
        
        # Simple test message
        response.say(
            "Hello! This is a test call from your AI voice interview system. "
            "If you can hear this clearly, your text to speech is working perfectly. "
            "The system is ready for interviews. This test call will now end. "
            "Thank you!",
            voice="Polly.Joanna"
        )
        
        # Hang up the call
        response.hangup()
        
        return str(response)

# Example usage function
async def start_interview_call(phone_number):
    """Start an interview call to the specified phone number."""
    caller = OutboundCaller()
    
    # Initiate the call
    call_sid = caller.make_interview_call(phone_number)
    
    print(f"Interview call started with SID: {call_sid}")
    return call_sid

if __name__ == "__main__":
    # Test the outbound caller
    test_phone_number = "+1234567890"  # Your phone number
    asyncio.run(start_interview_call(test_phone_number)) 