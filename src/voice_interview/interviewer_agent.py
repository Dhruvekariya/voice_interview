import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from voice_interview.db import get_interview_transcript

# Load environment variables
load_dotenv()

class InterviewFlow:
    """Handles the interview flow using CrewAI."""
    
    def __init__(self):
        """Initialize the interview flow."""
        self.current_stage = "introduction"
        self.interview_stages = [
            "introduction",
            "background",
            "experience",
            "skills",
            "questions",
            "conclusion"
        ]
        self.interviewer_agent = self._create_interviewer_agent()
        self.analyst_agent = self._create_analyst_agent()
    
    def _create_interviewer_agent(self):
        """Create the interviewer agent."""
        return Agent(
            role="Voice Interviewer",
            goal="Conduct engaging and insightful interviews with candidates",
            backstory="You are an experienced interviewer who puts candidates at ease while gathering valuable information.",
            verbose=True,
            allow_delegation=False
        )
    
    def _create_analyst_agent(self):
        """Create the analyst agent for post-interview analysis."""
        return Agent(
            role="Interview Analyst",
            goal="Analyze interview transcripts and provide insights",
            backstory="You are an expert at analyzing conversations and extracting valuable information from interviews.",
            verbose=True,
            allow_delegation=False
        )
    
    def _get_interview_task(self, caller_message):
        """Create the interview task based on the current stage."""
        task_description = f"""
        Conduct the {self.current_stage} stage of the interview.
        
        The candidate just said: "{caller_message}"
        
        You are in the {self.current_stage} stage of the interview.
        
        For introduction: Welcome the candidate and explain the interview process.
        For background: Ask about their professional background and education.
        For experience: Ask about relevant work experience and projects.
        For skills: Ask about specific skills relevant to the position.
        For questions: Ask if they have any questions about the position or company.
        For conclusion: Thank the candidate for their time and explain next steps.
        
        Respond in a conversational and natural way. Keep responses concise and suitable for speech.
        If appropriate, advance to the next stage of the interview.
        """
        
        return Task(
            description=task_description,
            expected_output="A natural and engaging response to the candidate",
            agent=self.interviewer_agent
        )
    
    def _get_analysis_task(self, transcript):
        """Create the analysis task for post-interview analysis."""
        task_description = f"""
        Analyze the following interview transcript:
        
        {transcript}
        
        Provide a detailed analysis including:
        1. Overall impression of the candidate
        2. Key strengths and potential areas of concern
        3. Assessment of their experience and skills
        4. Cultural fit considerations
        5. Recommendations for next steps
        
        Be objective and focus on the content of their responses.
        """
        
        return Task(
            description=task_description,
            expected_output="A detailed analysis of the interview with recommendations",
            agent=self.analyst_agent
        )
    
    def _advance_stage(self):
        """Advance to the next interview stage."""
        current_index = self.interview_stages.index(self.current_stage)
        if current_index < len(self.interview_stages) - 1:
            self.current_stage = self.interview_stages[current_index + 1]
            print(f"Advanced to interview stage: {self.current_stage}")
    
    async def conduct_interview(self, caller_message):
        """Process the caller's message and generate a response."""
        # Create the interview task
        interview_task = self._get_interview_task(caller_message)
        
        # Create the crew with just the interviewer agent
        crew = Crew(
            agents=[self.interviewer_agent],
            tasks=[interview_task],
            process=Process.sequential,
            verbose=True
        )
        
        # Run the crew
        result = crew.kickoff()
        
        # Get the text output from the CrewOutput object
        # In newer versions of CrewAI, the result is directly accessible as a string
        response_text = str(result)
        
        # Check if we should advance to the next stage
        # This is a simple logic - in a real implementation, 
        # you would use more sophisticated logic to determine when to advance
        if "next stage" in response_text.lower() or "next step" in response_text.lower():
            self._advance_stage()
        
        return response_text
    
    async def generate_analysis(self, interview_id=None):
        """Generate analysis for the interview."""
        # Get the interview transcript
        transcript = "Sample interview transcript for testing."
        if interview_id:
            transcript = await get_interview_transcript(interview_id)
        
        # Create the analysis task
        analysis_task = self._get_analysis_task(transcript)
        
        # Create the crew with just the analyst agent
        crew = Crew(
            agents=[self.analyst_agent],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True
        )
        
        # Run the crew
        result = crew.kickoff()
        
        # Get the text output from the CrewOutput object
        # In newer versions of CrewAI, the result is directly accessible as a string
        response_text = str(result)
        
        return response_text 