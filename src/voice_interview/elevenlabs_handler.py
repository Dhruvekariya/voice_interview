import os
import uuid
import asyncio
import json
import websockets
import requests
import base64
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ElevenLabsHandler:
    """Handler for ElevenLabs Conversational AI WebSocket following official best practices."""
    
    def __init__(self):
        """Initialize the ElevenLabs handler."""
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.agent_id = os.getenv("ELEVENLABS_AGENT_ID")
        self.websocket = None
        self.conversation_id = None
        self.conversation_ready = False
        self.audio_queue = asyncio.Queue()
        self.ping_task = None
    
    async def get_signed_url(self):
        """Get a signed URL for ElevenLabs Conversational AI."""
        try:
            url = f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url"
            params = {"agent_id": self.agent_id}
            headers = {"xi-api-key": self.api_key}
            
            print(f"🔍 Getting signed URL for agent: {self.agent_id}")
            response = requests.get(url, params=params, headers=headers)
            
            print(f"📡 Signed URL response: {response.status_code}")
            if response.status_code != 200:
                print(f"❌ Error response: {response.text}")
                raise Exception(f"Failed to get signed URL: {response.status_code} - {response.text}")
            
            data = response.json()
            signed_url = data.get('signed_url')
            print(f"✅ Got signed URL: {signed_url[:50]}...")
            return signed_url
            
        except Exception as e:
            print(f"❌ Error getting signed URL: {e}")
            raise
    
    async def start_conversation(self):
        """Start a new conversation with ElevenLabs following official protocol."""
        # Generate a unique conversation ID
        self.conversation_id = str(uuid.uuid4())
        
        # Connect to ElevenLabs WebSocket
        await self.connect_websocket()
        
        # Send conversation initiation message as per documentation
        await self.initiate_conversation()
        
        # Start listening for responses
        asyncio.create_task(self.listen_for_responses())
        
        print(f"🎯 Started ElevenLabs conversation: {self.conversation_id}")
        return self.conversation_id
    
    async def connect_websocket(self):
        """Connect to ElevenLabs Conversational AI WebSocket."""
        if not self.api_key or not self.agent_id:
            raise ValueError("ElevenLabs API key and Agent ID are required")
        
        # Get signed URL for conversational AI
        signed_url = await self.get_signed_url()
        
        try:
            self.websocket = await websockets.connect(signed_url)
            print(f"🔗 Connected to ElevenLabs Conversational AI")
        except Exception as e:
            print(f"❌ Failed to connect to ElevenLabs: {e}")
            raise
    
    async def initiate_conversation(self):
        """Send conversation initiation message as per ElevenLabs documentation."""
        if not self.websocket:
            raise ConnectionError("WebSocket not connected")
        
        # Send conversation initiation client data - MINIMAL APPROACH
        # Let ElevenLabs dashboard configuration handle everything
        initiation_message = {
            "type": "conversation_initiation_client_data"
            # No overrides - use pure dashboard configuration
        }
        
        try:
            await self.websocket.send(json.dumps(initiation_message))
            print(f"🚀 Sent conversation initiation (pure dashboard config)")
            
            # Wait for conversation initiation metadata response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
            data = json.loads(response)
            
            if data.get("type") == "conversation_initiation_metadata":
                self.conversation_ready = True
                conversation_id = data.get("conversation_initiation_metadata_event", {}).get("conversation_id")
                print(f"✅ Conversation initiated! ID: {conversation_id}")
                print(f"🎤 Waiting for agent to start speaking...")
                
                # Let the agent start naturally based on dashboard configuration
                return True
            else:
                print(f"⚠️ Unexpected response: {data}")
                return False
                
        except asyncio.TimeoutError:
            print(f"❌ Timeout waiting for conversation initiation")
            return False
        except Exception as e:
            print(f"❌ Error initiating conversation: {e}")
            return False
    
    async def listen_for_responses(self):
        """Listen for responses from ElevenLabs WebSocket."""
        try:
            while self.websocket:
                # Check if connection is still open
                if self.websocket.close_code is not None:
                    print("🔌 ElevenLabs WebSocket connection closed")
                    break
                    
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    await self.handle_websocket_message(data)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 ElevenLabs WebSocket connection closed")
                    break
                except Exception as e:
                    print(f"❌ Error listening to ElevenLabs: {e}")
                    break
        except Exception as e:
            print(f"❌ Fatal error in listen_for_responses: {e}")
        finally:
            self.conversation_ready = False
    
    async def handle_websocket_message(self, data):
        """Handle different types of messages from ElevenLabs."""
        message_type = data.get("type")
        
        if message_type == "ping":
            # Handle ping/pong as per documentation
            ping_event = data.get("ping_event", {})
            event_id = ping_event.get("event_id")
            ping_ms = ping_event.get("ping_ms", 0)
            
            # Respond with pong after the specified delay
            if ping_ms and ping_ms > 0:
                await asyncio.sleep(ping_ms / 1000.0)
            
            pong_message = {
                "type": "pong",
                "event_id": event_id
            }
            await self.websocket.send(json.dumps(pong_message))
            print(f"🏓 Sent pong response for event {event_id}")
            
        elif message_type == "audio":
            # Audio response from agent
            audio_event = data.get("audio_event", {})
            audio_base64 = audio_event.get("audio_base_64")
            event_id = audio_event.get("event_id")
            
            if audio_base64:
                await self.audio_queue.put({
                    "type": "audio",
                    "data": audio_base64,
                    "event_id": event_id
                })
                print(f"🎵 Received audio chunk (event {event_id})")
                
        elif message_type == "user_transcript":
            # User speech transcription
            transcript_event = data.get("user_transcription_event", {})
            transcript = transcript_event.get("user_transcript", "")
            print(f"🎤 User said: {transcript}")
            
        elif message_type == "agent_response":
            # Agent text response
            response_event = data.get("agent_response_event", {})
            response_text = response_event.get("agent_response", "")
            print(f"🤖 Agent response: {response_text}")
            
        elif message_type == "interruption":
            # Handle interruption
            interruption_event = data.get("interruption_event", {})
            reason = interruption_event.get("reason", "unknown")
            print(f"⚠️ Conversation interrupted: {reason}")
            
        else:
            print(f"📨 Other message type: {message_type}")
    
    async def send_audio_chunk(self, audio_base64):
        """Send audio chunk to ElevenLabs for processing."""
        if not self.websocket or not self.conversation_ready:
            print(f"⚠️ Cannot send audio - WebSocket not ready")
            return False
        
        message_data = {
            "user_audio_chunk": audio_base64
        }
        
        try:
            await self.websocket.send(json.dumps(message_data))
            return True
        except websockets.exceptions.ConnectionClosed:
            print(f"❌ ElevenLabs WebSocket closed while sending audio")
            self.conversation_ready = False
            return False
        except Exception as e:
            print(f"❌ Error sending audio to ElevenLabs: {e}")
            return False
    
    async def get_audio_response(self):
        """Get audio response from ElevenLabs queue."""
        try:
            # Wait for audio with timeout
            audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
            return audio_data
        except asyncio.TimeoutError:
            return None
    
    async def send_contextual_update(self, text):
        """Send contextual update to ElevenLabs without interrupting conversation."""
        if not self.websocket or not self.conversation_ready:
            return False
        
        contextual_message = {
            "type": "contextual_update",
            "text": text
        }
        
        try:
            await self.websocket.send(json.dumps(contextual_message))
            print(f"📝 Sent contextual update: {text}")
            return True
        except Exception as e:
            print(f"❌ Error sending contextual update: {e}")
            return False
    
    async def close(self):
        """Close the WebSocket connection gracefully."""
        self.conversation_ready = False
        
        if self.ping_task:
            self.ping_task.cancel()
            
        if self.websocket:
            try:
                # Send close message if still connected
                if self.websocket.close_code is None:
                    await self.websocket.close()
            except Exception as e:
                print(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None
                print("🔌 Closed ElevenLabs WebSocket connection")
    
    def is_ready(self):
        """Check if the handler is ready for conversation."""
        return (self.websocket and 
                self.websocket.close_code is None and 
                self.conversation_ready) 