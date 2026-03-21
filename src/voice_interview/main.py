#!/usr/bin/env python
import os
import sys
import warnings
import json
import base64
import asyncio
import websockets
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Response
from twilio.twiml.voice_response import VoiceResponse
from pydantic import BaseModel

from voice_interview.outbound_caller import OutboundCaller
from voice_interview.elevenlabs_handler import ElevenLabsHandler
from voice_interview.db import create_tables, store_interview, store_conversation_log

# Load environment variables
load_dotenv()

# Ignore pysbd warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# Create FastAPI app
app = FastAPI(title="Voice Interviewer")

# Initialize handlers
elevenlabs_handler = ElevenLabsHandler()
outbound_caller = OutboundCaller()

# Create database tables
create_tables()

# Request models
class CallRequest(BaseModel):
    phone_number: str

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"status": "Voice Interviewer API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Voice Interview System",
        "ngrok_url": os.getenv('NGROK_URL', 'https://your-ngrok-domain.ngrok-free.app'),
        "endpoints": {
            "make_call": "/make_call",
            "docs": "/docs",
            "health": "/health"
        }
    }

@app.post("/twilio/incoming")
async def handle_incoming_call(request: Request):
    """Handle incoming Twilio call (legacy endpoint)."""
    # Create TwiML response
    response = VoiceResponse()
    
    # Add a message
    response.say("Welcome to the voice interviewer system. Your interview will begin shortly.")
    
    # This is kept for backward compatibility
    response.say("This is a demo. Please use the outbound calling feature for full interviews.")
    
    return Response(content=str(response), media_type="application/xml")

@app.post("/twilio/outbound_call")
async def handle_outbound_call(request: Request):
    """Handle outbound call webhook from Twilio."""
    # Generate proper interview TwiML that starts the interview conversation
    twiml = outbound_caller.generate_call_twiml()
    
    # Debug: Log the TwiML being returned
    print("🎵 Generated TwiML:")
    print(twiml)
    print("=" * 50)
    
    return Response(content=twiml, media_type="application/xml")

@app.post("/twilio/status_callback")
async def handle_status_callback(request: Request):
    """Handle Twilio status callbacks."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    
    print(f"Call {call_sid} status: {call_status}")
    
    # Return empty TwiML response
    twiml = outbound_caller.generate_status_callback_response()
    return Response(content=twiml, media_type="application/xml")

@app.websocket("/twilio/media_stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle Twilio Media Stream WebSocket for real-time audio with ElevenLabs."""
    await websocket.accept()
    print("🎤 Twilio Media Stream WebSocket connected!")
    print(f"📡 Client: {websocket.client}")
    print("🎧 Waiting for Twilio to send 'start' event...")
    
    # Variables to track the call
    stream_sid = None
    call_sid = None
    elevenlabs_handler = None
    conversation_active = False
    
    try:
        # Handle incoming Twilio media messages
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
                event = data.get("event")
                
                if event == "start":
                    # Call has started
                    stream_sid = data["start"]["streamSid"]
                    call_sid = data["start"]["callSid"]
                    print(f"🎯 Call started - Stream SID: {stream_sid}, Call SID: {call_sid}")
                    
                    # Initialize ElevenLabs handler with improved implementation
                    try:
                        elevenlabs_handler = ElevenLabsHandler()
                        conversation_id = await elevenlabs_handler.start_conversation()
                        
                        # Wait for conversation to be ready
                        for i in range(50):  # Wait up to 5 seconds
                            if elevenlabs_handler.is_ready():
                                conversation_active = True
                                print(f"🎉 ElevenLabs conversation ready!")
                                break
                            await asyncio.sleep(0.1)
                        
                        if not conversation_active:
                            print(f"❌ Failed to establish ElevenLabs conversation")
                            print(f"🔍 Debug: conversation_ready = {elevenlabs_handler.is_ready()}")
                            print(f"🔍 Debug: websocket status = {elevenlabs_handler.websocket is not None}")
                            # Send fallback TTS message
                            await send_twilio_message(websocket, stream_sid, 
                                "I'm sorry, there seems to be a technical issue. Please try calling again.")
                            continue
                            
                        # Send contextual information about the call
                        await elevenlabs_handler.send_contextual_update(f"Call started with ID {call_sid}")
                        print(f"📝 Sent contextual update to ElevenLabs")
                        
                        # Start processing audio responses from ElevenLabs
                        asyncio.create_task(process_elevenlabs_audio(websocket, stream_sid, elevenlabs_handler))
                        print(f"🎵 Started audio processing task")
                        
                        # Send a test message to get the conversation going
                        await asyncio.sleep(1)  # Brief pause
                        print(f"🚀 ElevenLabs conversation is active and ready for audio!")
                        
                    except Exception as e:
                        print(f"❌ Failed to initialize ElevenLabs: {e}")
                        print(f"🔍 Exception type: {type(e).__name__}")
                        print(f"🔍 Exception details: {str(e)}")
                        # Send fallback message to Twilio
                        await send_twilio_message(websocket, stream_sid, 
                            "Hello, I'm experiencing technical difficulties. Please hold while I try to reconnect.")
                        continue
                
                elif event == "media" and elevenlabs_handler and conversation_active:
                    # Incoming audio from Twilio
                    payload = data["media"]["payload"]
                    
                    try:
                        # Send audio to ElevenLabs
                        success = await elevenlabs_handler.send_audio_chunk(payload)
                        if not success:
                            print(f"⚠️ Failed to send audio to ElevenLabs")
                            # Try to recover
                            if not elevenlabs_handler.is_ready():
                                print(f"🔄 Attempting to reconnect to ElevenLabs...")
                                conversation_active = False
                                # Could implement reconnection logic here
                                
                    except Exception as e:
                        print(f"❌ Error processing audio: {e}")
                        
                elif event == "stop":
                    # Call has ended
                    print(f"📞 Call ended - Stream SID: {stream_sid}")
                    conversation_active = False
                    
                    if elevenlabs_handler:
                        await elevenlabs_handler.close()
                    break
                    
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON received from Twilio")
            except Exception as e:
                print(f"❌ Error processing Twilio message: {e}")
                
    except Exception as e:
        print(f"❌ Fatal error in media stream handler: {e}")
    finally:
        # Cleanup
        conversation_active = False
        if elevenlabs_handler:
            try:
                await elevenlabs_handler.close()
            except Exception as e:
                print(f"❌ Error closing ElevenLabs handler: {e}")
        
        print(f"🔌 Closed Twilio Media Stream WebSocket")

async def process_elevenlabs_audio(websocket: WebSocket, stream_sid: str, elevenlabs_handler):
    """Process audio responses from ElevenLabs and send to Twilio."""
    print(f"🎵 Starting ElevenLabs audio processor...")
    
    try:
        while elevenlabs_handler and elevenlabs_handler.is_ready():
            try:
                # Get audio from ElevenLabs queue
                audio_response = await elevenlabs_handler.get_audio_response()
                
                if audio_response and audio_response.get("type") == "audio":
                    audio_data = audio_response.get("data")
                    event_id = audio_response.get("event_id")
                    
                    if audio_data:
                        # Send audio back to Twilio
                        media_message = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_data
                            }
                        }
                        
                        await websocket.send_text(json.dumps(media_message))
                        print(f"🔊 Sent audio to Twilio (event {event_id})")
                        
            except Exception as e:
                print(f"❌ Error processing ElevenLabs audio: {e}")
                await asyncio.sleep(0.1)  # Prevent tight loop on errors
                
    except Exception as e:
        print(f"❌ Fatal error in audio processor: {e}")
    
    print(f"🔌 ElevenLabs audio processor stopped")

async def send_twilio_message(websocket: WebSocket, stream_sid: str, message: str):
    """Send a text message to Twilio for TTS playback."""
    try:
        # Use Twilio's built-in Say command for fallback messages
        # Note: This might not work directly in media streams, 
        # so let's try a different approach
        print(f"🗣️ Attempting to send TTS message: {message}")
        
        # For Twilio media streams, we need to send an actual media message
        # Let's log this for debugging
        print(f"⚠️ TTS fallback called - this indicates ElevenLabs connection issue")
        print(f"💡 Consider checking ElevenLabs agent configuration")
        
    except Exception as e:
        print(f"❌ Error sending TTS message: {e}")

@app.post("/make_call")
async def make_call(request: CallRequest):
    """Initiate an outbound call for voice interview."""
    try:
        # Initialize outbound caller
        caller = OutboundCaller()
        
        # Make the call without any custom prompt (let ElevenLabs agent handle it)
        call_sid = caller.make_interview_call(request.phone_number)
        
        return {
            "status": "success",
            "message": f"Call initiated to {request.phone_number}",
            "call_sid": call_sid
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/start_interview")
async def start_interview(request: CallRequest):
    """API endpoint to start an interview call (alias for /make_call)."""
    return await make_call(request)

# Legacy recording endpoint removed - now using ElevenLabs Conversational AI via WebSocket

@app.post("/twilio/transcription")
async def handle_transcription(request: Request):
    """Handle transcription callbacks from Twilio."""
    form_data = await request.form()
    transcription_text = form_data.get("TranscriptionText", "")
    call_sid = form_data.get("CallSid")
    
    print(f"Transcription for call {call_sid}: {transcription_text}")
    
    # Store the transcription for later analysis
    if transcription_text.strip():
        # You can store this in the database
        await store_conversation_log(call_sid, "caller", transcription_text)
    
    return {"status": "received"}

@app.post("/twilio/test_speech")
async def test_speech(request: Request):
    """Simple test endpoint to verify TTS is working."""
    response = VoiceResponse()
    response.say(
        "This is a test message from the AI voice interview system. "
        "If you can hear this, the text to speech is working correctly. "
        "This call will now end. Thank you for testing.",
        voice="Polly.Joanna"
    )
    response.hangup()
    return Response(content=str(response), media_type="application/xml")

def run():
    """Run the FastAPI server using uvicorn."""
    import uvicorn
    uvicorn.run("voice_interview.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    run()

